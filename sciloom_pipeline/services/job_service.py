import os
import shutil
import zipfile
import subprocess
import asyncio
import json
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from sciloom_pipeline.config import settings
from sciloom_pipeline.db.database import SessionLocal
from sciloom_pipeline.db import models
from sciloom_pipeline.document_processing.pdf_extractor import PDFExtractor

class JobService:
    async def add_log(self, job_id: str, level: str, message: str, db: Optional[Session] = None) -> None:
        """Saves a log to the database and broadcasts it in real-time."""
        timestamp = datetime.now().strftime("%I:%M:%S %p")
        
        def _save():
            # Always use a fresh session to ensure thread-safety and avoid polluting
            # the caller's transaction state in background threads.
            local_db = SessionLocal()
            try:
                log_entry = models.Log(
                    job_id=job_id,
                    level=level,
                    message=message,
                    timestamp=timestamp
                )
                local_db.add(log_entry)
                local_db.commit()
            finally:
                local_db.close()

        await asyncio.to_thread(_save)
        
        # Broadcast via queue service notifications
        from sciloom_pipeline.services.queue_service import queue_service
        await queue_service.broadcast_log(job_id, level, message, timestamp)

    async def get_all_jobs(self, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns all jobs from the database."""
        local_db = db or SessionLocal()
        try:
            jobs = local_db.query(models.Job).order_by(models.Job.created_at.desc()).all()
            return [self._format_job(j) for j in jobs]
        finally:
            if db is None:
                local_db.close()

    async def get_job_by_id(self, job_id: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """Returns details for a single job."""
        local_db = db or SessionLocal()
        try:
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            return self._format_job(job) if job else None
        finally:
            if db is None:
                local_db.close()

    async def get_stages_for_job(self, job_id: str, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns all stages for a job."""
        local_db = db or SessionLocal()
        try:
            stages = local_db.query(models.Stage).filter(models.Stage.job_id == job_id).order_by(models.Stage.id).all()
            return [self._format_stage(s) for s in stages]
        finally:
            if db is None:
                local_db.close()

    async def get_claims_for_job(self, job_id: str, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns all claims for a job."""
        local_db = db or SessionLocal()
        try:
            claims = local_db.query(models.Claim).filter(models.Claim.job_id == job_id).order_by(models.Claim.created_at.asc()).all()
            return [self._format_claim(c) for c in claims]
        finally:
            if db is None:
                local_db.close()

    async def get_logs_for_job(self, job_id: str, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns all logs for a job."""
        local_db = db or SessionLocal()
        try:
            logs = local_db.query(models.Log).filter(models.Log.job_id == job_id).order_by(models.Log.id.asc()).all()
            return [
                {
                    "id": l.id,
                    "job_id": l.job_id,
                    "level": l.level,
                    "message": l.message,
                    "timestamp": l.timestamp
                } for l in logs
            ]
        finally:
            if db is None:
                local_db.close()

    async def get_ocr_markdown(self, job_id: str) -> str:
        """Reads and returns the OCR RESEARCH_PAPER.md content if it exists."""
        job_dir = settings.jobs_dir / f"job_{job_id}"
        md_file = job_dir / "RESEARCH_PAPER.md"
        if not md_file.is_file():
            raise FileNotFoundError("OCR markdown file not found. Ensure Stage 1 has completed.")
        
        def _read():
            return md_file.read_text(encoding="utf-8")
        
        return await asyncio.to_thread(_read)

    async def get_repo_files(self, job_id: str) -> List[Dict[str, Any]]:
        """Returns a recursive file structure representing the REPO folder."""
        repo_dir = settings.jobs_dir / f"job_{job_id}" / "REPO"
        if not repo_dir.is_dir():
            return []

        def _get_tree(path: Path) -> List[Dict[str, Any]]:
            items = []
            for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                # Skip hidden files/directories (like .git)
                if child.name.startswith("."):
                    continue
                
                is_dir = child.is_dir()
                item: Dict[str, Any] = {
                    "name": child.name,
                    "isDir": is_dir
                }
                
                if is_dir:
                    item["children"] = _get_tree(child)
                else:
                    item["size"] = child.stat().st_size
                
                items.append(item)
            return items

        return await asyncio.to_thread(_get_tree, repo_dir)

    async def create_job_record(
        self,
        job_id: str,
        title: str,
        pdf_name: str,
        repo_source: str,
        repo_url: Optional[str],
        repo_file_name: Optional[str],
        data_source: str,
        data_file_name: Optional[str],
        manual_claims: List[str],
        db: Optional[Session] = None
    ) -> None:
        """Creates the initial database records for a new job, its stages, and its manual claims."""
        pdf_path = f"jobs/{job_id}/paper.pdf"
        stage_names = ["PROVISIONING", "CLAIM_EXTRACTION", "CODE_EXECUTION", "CLAIM_REPLICATION", "DTREG_GENERATION"]
        
        local_db = db or SessionLocal()
        try:
            # 1. Create Job ORM object
            job = models.Job(
                id=job_id,
                title=title,
                pdf_path=pdf_path,
                repo_source=repo_source,
                repo_url=repo_url,
                data_source=data_source,
                status="CREATED",
                current_stage="PROVISIONING"
            )
            local_db.add(job)
            
            # 2. Add Stages
            for stage_name in stage_names:
                stage = models.Stage(
                    job_id=job_id,
                    stage_name=stage_name,
                    status="pending"
                )
                local_db.add(stage)
                
            # 3. Add Claims
            for idx, claim_text in enumerate(manual_claims):
                claim = models.Claim(
                    id=f"{job_id}_claim_{idx+1}",
                    job_id=job_id,
                    claim_text=claim_text,
                    source="user"
                )
                local_db.add(claim)
                
            local_db.commit()
        except Exception as e:
            local_db.rollback()
            raise e
        finally:
            if db is None:
                local_db.close()

    async def mark_stage_failed(self, job_id: str, stage_name: str, error_msg: str, db: Optional[Session] = None) -> None:
        """Helper to mark a stage as failed and update the job status."""
        local_db = db or SessionLocal()
        try:
            # Update job status
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.updated_at = datetime.now(timezone.utc)
            
            # Update stage status
            stage = local_db.query(models.Stage).filter(
                models.Stage.job_id == job_id,
                models.Stage.stage_name == stage_name
            ).first()
            if stage:
                stage.status = "failed"
                stage.error_log = error_msg
                stage.completed_at = datetime.now().isoformat()
                stage.sandbox_info = json.dumps({
                    "sandboxId": f"sbx-{job_id}",
                    "connectionCommand": f"sbx exec -j {job_id} -- bash"
                })
                stage.updated_at = datetime.now(timezone.utc)
                
            local_db.commit()
        except Exception as e:
            local_db.rollback()
            raise e
        finally:
            if db is None:
                local_db.close()

        await self.add_log(job_id, "ERROR", f"Stage {stage_name} failed: {error_msg}", db=db)

    async def run_provisioning(self, job_id: str, db: Optional[Session] = None) -> None:
        """Executes Stage 1: Provisioning (Job Setup)."""
        local_db = db or SessionLocal()
        try:
            # Fetch job via Session
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found in database.")

            # Update statuses
            job.status = "PROVISIONING"
            job.updated_at = datetime.now(timezone.utc)
            
            stage = local_db.query(models.Stage).filter(
                models.Stage.job_id == job_id,
                models.Stage.stage_name == "PROVISIONING"
            ).first()
            if stage:
                stage.status = "running"
                stage.started_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)
            
            local_db.commit()

            # Files setup
            job_dir = settings.jobs_dir / f"job_{job_id}"
            repo_dir = job_dir / "REPO"
            
            await self.add_log(job_id, "INFO", f"Initializing provisioning for job {job_id}...", db=local_db)
            await self.add_log(job_id, "INFO", f"Creating workspace folder: jobs/job_{job_id}/", db=local_db)
            job_dir.mkdir(parents=True, exist_ok=True)
            
            # Repo Setup
            repo_source = job.repo_source
            if repo_source == "github":
                repo_url = job.repo_url
                if not repo_url:
                    raise ValueError("Repository source is github, but repoUrl is missing.")
                
                parsed_url = urllib.parse.urlparse(repo_url)
                if parsed_url.scheme not in ("http", "https"):
                    raise ValueError("Invalid repository URL scheme. Only HTTP and HTTPS are supported.")

                await self.add_log(job_id, "INFO", f"Cloning code repository from GitHub URL: {repo_url}...", db=local_db)
                
                def _clone():
                    subprocess.run(
                        ["git", "clone", "--", repo_url, str(repo_dir)],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                await asyncio.to_thread(_clone)
                await self.add_log(job_id, "INFO", "Repository cloned successfully.", db=local_db)
            
            elif repo_source == "zip":
                repo_zip = job_dir / "repo_temp.zip"
                if not repo_zip.is_file():
                    raise FileNotFoundError("Uploaded repository zip file not found in job workspace.")
                
                await self.add_log(job_id, "INFO", f"Extracting repository archive: {repo_zip.name}...", db=local_db)
                
                def _extract_repo():
                    repo_dir.mkdir(parents=True, exist_ok=True)
                    with zipfile.ZipFile(repo_zip, 'r') as zip_ref:
                        for member in zip_ref.infolist():
                            target_path = repo_dir / member.filename
                            if not target_path.resolve().is_relative_to(repo_dir.resolve()):
                                raise PermissionError(f"Directory traversal detected in ZIP: {member.filename}")
                        zip_ref.extractall(repo_dir)
                    repo_zip.unlink()
                await asyncio.to_thread(_extract_repo)
                await self.add_log(job_id, "INFO", f"Repository successfully setup at jobs/job_{job_id}/REPO/", db=local_db)

            # Data Setup
            data_source = job.data_source
            if data_source == "zip":
                data_zip = job_dir / "data_temp.zip"
                if data_zip.is_file():
                    await self.add_log(job_id, "INFO", f"Extracting additional dataset archive: {data_zip.name}...", db=local_db)
                    
                    def _extract_data():
                        with zipfile.ZipFile(data_zip, 'r') as zip_ref:
                            for member in zip_ref.infolist():
                                target_path = repo_dir / member.filename
                                if not target_path.resolve().is_relative_to(repo_dir.resolve()):
                                    raise PermissionError(f"Directory traversal detected in ZIP: {member.filename}")
                            zip_ref.extractall(repo_dir)
                        data_zip.unlink()
                    await asyncio.to_thread(_extract_data)
                    await self.add_log(job_id, "INFO", "Dataset extracted into repository folder.", db=local_db)
                else:
                    await self.add_log(job_id, "INFO", "Dataset marked as zip but file not found; skipping.", db=local_db)
            else:
                await self.add_log(job_id, "INFO", "Dataset marked as present in code repository workspace.", db=local_db)

            # OCR Extraction
            pdf_file = job_dir / "paper.pdf"
            if not pdf_file.is_file():
                raise FileNotFoundError("Source PDF paper.pdf is missing.")

            await self.add_log(job_id, "INFO", "Starting Gemini Vision API OCR extraction on paper PDF...", db=local_db)
            await self.add_log(job_id, "INFO", "Analyzing document formatting, images, tables and equations...", db=local_db)
            
            extractor = PDFExtractor(gemini_api_key=settings.gemini_api_key)
            _md_path, char_counts = await extractor.extract(pdf_path=pdf_file, output_dir=job_dir)

            # Persist per-page character counts to ocr_logs table
            await self._save_ocr_logs(job_id, char_counts, db=local_db)

            # Log summary of page character counts
            empty_pages = [i + 1 for i, c in enumerate(char_counts) if c == 0]
            await self.add_log(job_id, "INFO", f"Gemini Vision OCR successfully parsed all sections ({len(char_counts)} pages).", db=local_db)
            if empty_pages:
                await self.add_log(job_id, "WARN", f"Pages with 0 characters after retry: {empty_pages}. Consider using 'Retry OCR' to re-extract.", db=local_db)
            await self.add_log(job_id, "INFO", "Saving parsed content to markdown file: RESEARCH_PAPER.md", db=local_db)
            
            # Finalize success status
            job.status = "PROVISIONED"
            job.updated_at = datetime.now(timezone.utc)
            if stage:
                stage.status = "completed"
                stage.completed_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)
            local_db.commit()
            
            await self.add_log(job_id, "INFO", "Job setup completed. Directory structure finalized.", db=local_db)
            await self.add_log(job_id, "INFO", "SQLite database updated: job status = PROVISIONED", db=local_db)

        except Exception as e:
            local_db.rollback()
            await self.mark_stage_failed(job_id, "PROVISIONING", str(e), db=local_db)
            raise e
        finally:
            if db is None:
                local_db.close()

    # --- Helper: save OCR page character counts to the database ---
    async def _save_ocr_logs(self, job_id: str, char_counts: list[int], db: Optional[Session] = None) -> None:
        """Clears existing OcrLog rows for the job and saves fresh per-page counts."""
        def _write():
            # Always use a fresh session to ensure thread-safety in the background thread.
            local_db = SessionLocal()
            try:
                # Remove old rows for this job
                local_db.query(models.OcrLog).filter(models.OcrLog.job_id == job_id).delete(synchronize_session=False)
                for page_num, count in enumerate(char_counts, start=1):
                    local_db.add(models.OcrLog(job_id=job_id, page_number=page_num, char_count=count))
                local_db.commit()
            finally:
                local_db.close()
        await asyncio.to_thread(_write)

    # --- OCR Retry: re-run only the OCR step on an already-provisioned job ---
    async def run_ocr_retry(self, job_id: str, db: Optional[Session] = None) -> None:
        """Re-runs only the PDF OCR step, preserving the existing repo/dataset workspace."""
        local_db = db or SessionLocal()
        try:
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found.")

            # Update status to running/PROVISIONING
            job.status = "PROVISIONING"
            job.updated_at = datetime.now(timezone.utc)
            
            stage = local_db.query(models.Stage).filter(
                models.Stage.job_id == job_id,
                models.Stage.stage_name == "PROVISIONING"
            ).first()
            if stage:
                stage.status = "running"
                stage.started_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)
            
            local_db.commit()

            job_dir = settings.jobs_dir / f"job_{job_id}"
            pdf_file = job_dir / "paper.pdf"
            if not pdf_file.is_file():
                raise FileNotFoundError("Source PDF paper.pdf is missing from workspace.")

            await self.add_log(job_id, "INFO", "Starting OCR retry — re-extracting paper PDF...", db=local_db)
            extractor = PDFExtractor(gemini_api_key=settings.gemini_api_key)
            _md_path, char_counts = await extractor.extract(pdf_path=pdf_file, output_dir=job_dir)

            await self._save_ocr_logs(job_id, char_counts, db=local_db)

            empty_pages = [i + 1 for i, c in enumerate(char_counts) if c == 0]
            await self.add_log(job_id, "INFO", f"OCR retry complete ({len(char_counts)} pages).", db=local_db)
            if empty_pages:
                await self.add_log(job_id, "WARN", f"Still empty after retry: pages {empty_pages}", db=local_db)
                
            # Restore status to PROVISIONED
            job.status = "PROVISIONED"
            job.updated_at = datetime.now(timezone.utc)
            if stage:
                stage.status = "completed"
                stage.completed_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)
            local_db.commit()
            
        except Exception as e:
            local_db.rollback()
            await self.mark_stage_failed(job_id, "PROVISIONING", str(e), db=local_db)
            raise
        finally:
            if db is None:
                local_db.close()

    # --- Claim Extraction: execute Stage 2 claim extraction ---
    async def run_claim_extraction(self, job_id: str, db: Optional[Session] = None) -> None:
        """Executes Stage 2: Claim Extraction (automated via OpenCode agent)."""
        local_db = db or SessionLocal()
        try:
            # Fetch job via Session
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found in database.")

            # Update statuses
            job.status = "CLAIM_EXTRACTION"
            job.updated_at = datetime.now(timezone.utc)
            
            stage = local_db.query(models.Stage).filter(
                models.Stage.job_id == job_id,
                models.Stage.stage_name == "CLAIM_EXTRACTION"
            ).first()
            if stage:
                stage.status = "running"
                stage.started_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)
            
            local_db.commit()

            await self.add_log(job_id, "INFO", f"Starting Stage 2 claim extraction for job {job_id}...", db=local_db)
            
            job_dir = settings.jobs_dir / f"job_{job_id}"
            
            # Helper log callback
            async def log_callback(message: str, level: str = "INFO"):
                await self.add_log(job_id, level, message, db=local_db)
            
            # Invoke agent_service to run the subprocess
            from sciloom_pipeline.services.agent_service import agent_service
            await agent_service.extract_claims(job_id, job_dir, log_callback)
            
            # Read and parse generated CLAIMS.json
            json_file = job_dir / "CLAIMS.json"
            if not json_file.is_file():
                raise FileNotFoundError("CLAIMS.json was not generated by the claim extraction agent.")
            
            def _read_claims():
                return json.loads(json_file.read_text(encoding="utf-8"))
            
            claims_data = await asyncio.to_thread(_read_claims)
            if not isinstance(claims_data, list):
                raise ValueError("CLAIMS.json must contain a list of claim objects.")
            
            await self.add_log(job_id, "INFO", f"Parsing and storing {len(claims_data)} claims into the database...", db=local_db)
            
            # Delete any existing agent claims for this job to prevent duplicates on retry
            local_db.query(models.Claim).filter(
                models.Claim.job_id == job_id,
                models.Claim.source == "agent"
            ).delete(synchronize_session=False)
            
            for idx, item in enumerate(claims_data):
                # Map fields safely
                claim_text = item.get("claim_text") or item.get("quantitative_claim") or ""
                metrics = item.get("metrics") or item.get("specific_data_metrics") or ""
                evidence = item.get("evidence") or item.get("grounding_evidence") or ""
                
                # Check for required fields
                if not claim_text.strip():
                    await self.add_log(job_id, "WARN", f"Skipping empty claim at index {idx}.", db=local_db)
                    continue
                
                claim_id = f"{job_id}_claim_{idx + 1}"
                new_claim = models.Claim(
                    id=claim_id,
                    job_id=job_id,
                    claim_text=claim_text,
                    metrics=metrics,
                    evidence=evidence,
                    source="agent",
                    replicated=False
                )
                local_db.add(new_claim)
            
            # Update stage and job status on success
            job.status = "CLAIM_EXTRACTION"
            if stage:
                stage.status = "completed"
                stage.completed_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)
            
            local_db.commit()
            await self.add_log(job_id, "INFO", f"Stage 2 claim extraction successfully completed. {len(claims_data)} claims stored.", db=local_db)
            
        except Exception as e:
            local_db.rollback()
            await self.mark_stage_failed(job_id, "CLAIM_EXTRACTION", str(e), db=local_db)
            raise e
        finally:
            if db is None:
                local_db.close()

    # --- Update OCR Markdown: save edited content and recalculate page counts ---
    async def update_ocr_markdown(self, job_id: str, markdown: str, db: Optional[Session] = None) -> None:
        """Overwrites RESEARCH_PAPER.md with the provided markdown and recalculates OCR page counts."""
        job_dir = settings.jobs_dir / f"job_{job_id}"
        md_file = job_dir / "RESEARCH_PAPER.md"

        # Write the new content to disk
        def _write_file():
            md_file.write_text(markdown, encoding="utf-8")
        await asyncio.to_thread(_write_file)

        # Recalculate per-page character counts by splitting on horizontal rules
        pages = markdown.split("\n\n---\n\n")
        char_counts = [len(p) for p in pages]
        await self._save_ocr_logs(job_id, char_counts, db=db)

    # --- Helper formatting methods ---
    def _format_job(self, job: models.Job) -> Dict[str, Any]:
        pdf_path = job.pdf_path
        pdf_name = Path(pdf_path).name if pdf_path else ""
        # Build ordered list of per-page char counts from the ocr_logs relationship
        ocr_counts: list[int] | None = None
        if job.ocr_logs:
            ocr_counts = [ol.char_count for ol in sorted(job.ocr_logs, key=lambda x: x.page_number)]
        return {
            "id": job.id,
            "title": job.title,
            "pdfPath": pdf_path,
            "pdfName": pdf_name,
            "repoSource": job.repo_source,
            "repoUrl": job.repo_url,
            "repoFileName": f"{job.id}_repo.zip" if job.repo_source == "zip" else None,
            "dataSource": job.data_source,
            "dataFileName": f"{job.id}_data.zip" if job.data_source == "zip" else None,
            "status": job.status,
            "currentStage": job.current_stage,
            "createdAt": job.created_at.isoformat() if job.created_at else "",
            "updatedAt": job.updated_at.isoformat() if job.updated_at else "",
            "ocrPageCharCounts": ocr_counts
        }

    def _format_stage(self, stage: models.Stage) -> Dict[str, Any]:
        sandbox_info_raw = stage.sandbox_info
        sandbox_info = json_loads(sandbox_info_raw) if sandbox_info_raw else None
        
        return {
            "id": f"{stage.job_id}_stage_{stage.id}",
            "jobId": stage.job_id,
            "stageName": stage.stage_name,
            "status": stage.status,
            "errorLog": stage.error_log,
            "sandboxInfo": sandbox_info,
            "startedAt": stage.started_at,
            "completedAt": stage.completed_at
        }

    def _format_claim(self, claim: models.Claim) -> Dict[str, Any]:
        screenshots_raw = claim.user_screenshots
        screenshots = json_loads(screenshots_raw) if screenshots_raw else []
        return {
            "id": claim.id,
            "jobId": claim.job_id,
            "claimText": claim.claim_text,
            "metrics": claim.metrics,
            "evidence": claim.evidence,
            "source": claim.source,
            "replicated": claim.replicated,
            "replicationError": claim.replication_error,
            "userInstructions": claim.user_instructions,
            "userScreenshots": screenshots,
            "createdAt": claim.created_at.isoformat() if claim.created_at else ""
        }

def json_loads(val: str) -> Any:
    try:
        return json.loads(val)
    except Exception:
        return None

job_service = JobService()

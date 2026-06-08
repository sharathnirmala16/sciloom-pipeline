import os
import re
import shutil
import zipfile
import subprocess
import asyncio
import json
import urllib.parse
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from sciloom_pipeline.config import settings, REPO_ROOT
from sciloom_pipeline.db.database import SessionLocal
from sciloom_pipeline.db import models

logger = logging.getLogger("sciloom.job")

SCILOOM_DIR_NAME = ".sciloom"


class JobService:
    def _get_sciloom_dir(self, job_id: str) -> Path:
        """Returns the .sciloom directory path for a job."""
        return settings.jobs_dir / job_id / "REPO" / SCILOOM_DIR_NAME

    def _ensure_sciloom_dir(self, job_id: str) -> Path:
        """Ensures the .sciloom directory exists and returns its path."""
        sciloom_dir = self._get_sciloom_dir(job_id)
        sciloom_dir.mkdir(parents=True, exist_ok=True)
        return sciloom_dir

    # --- Logging delegation ---
    async def add_log(
        self,
        job_id: str,
        stage_name_or_level: str,
        level_or_message: str,
        message: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> None:
        """Delegates logging to the file-based LogService."""
        if message is None:
            # Called as add_log(job_id, level, message, db=db)
            level = stage_name_or_level
            msg = level_or_message
            stage_name = "general"
            if db:
                try:
                    job = db.query(models.Job).filter(models.Job.id == job_id).first()
                    if job and job.current_stage:
                        stage_name = job.current_stage
                except Exception:
                    pass
        else:
            # Called as add_log(job_id, stage_name, level, message)
            stage_name = stage_name_or_level
            level = level_or_message
            msg = message

        from sciloom_pipeline.services.log_service import log_service

        await log_service.add_log(job_id, stage_name, level, msg)

    # --- Job CRUD ---
    async def get_all_jobs(self, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Returns all jobs from the database."""
        local_db = db or SessionLocal()
        try:
            jobs = (
                local_db.query(models.Job).order_by(models.Job.created_at.desc()).all()
            )
            return [self._format_job(j) for j in jobs]
        finally:
            if db is None:
                local_db.close()

    async def get_job_by_id(
        self, job_id: str, db: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """Returns details for a single job."""
        local_db = db or SessionLocal()
        try:
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            return self._format_job(job) if job else None
        finally:
            if db is None:
                local_db.close()

    async def get_stages_for_job(
        self, job_id: str, db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Returns all stages for a job."""
        local_db = db or SessionLocal()
        try:
            stages = (
                local_db.query(models.Stage)
                .filter(models.Stage.job_id == job_id)
                .order_by(models.Stage.id)
                .all()
            )
            return [self._format_stage(s) for s in stages]
        finally:
            if db is None:
                local_db.close()

    # --- Claims (file-based) ---
    async def get_claims_for_job(
        self, job_id: str, db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Reads claims from .sciloom/CLAIMS.json and injects jobId/createdAt metadata."""
        claims_path = self._get_sciloom_dir(job_id) / "CLAIMS.json"
        if not claims_path.is_file():
            return []

        def _read():
            return json.loads(claims_path.read_text(encoding="utf-8"))

        data = await asyncio.to_thread(_read)
        if not isinstance(data, list):
            return []
        for c in data:
            c["jobId"] = job_id
            c["job_id"] = job_id
            if "createdAt" not in c and "created_at" not in c:
                c["createdAt"] = datetime.now().isoformat()
        return data

    async def save_claims_to_file(
        self, job_id: str, claims: List[Dict[str, Any]]
    ) -> None:
        """Writes claims to .sciloom/CLAIMS.json."""
        sciloom_dir = self._ensure_sciloom_dir(job_id)
        claims_path = sciloom_dir / "CLAIMS.json"

        def _write():
            claims_path.write_text(
                json.dumps(claims, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        await asyncio.to_thread(_write)

    # --- Logs (file-based) ---
    async def get_logs_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        """Returns all logs for a job by reading all stage log files."""
        from sciloom_pipeline.services.log_service import log_service

        return await log_service.get_all_logs(job_id)

    # --- OCR Markdown ---
    async def get_ocr_markdown(self, job_id: str) -> str:
        """Reads and returns the OCR RESEARCH_PAPER.md content from .sciloom/."""
        md_file = self._get_sciloom_dir(job_id) / "RESEARCH_PAPER.md"
        if not md_file.is_file():
            raise FileNotFoundError(
                "OCR markdown file not found. Ensure Stage 1 has completed."
            )

        def _read():
            return md_file.read_text(encoding="utf-8")

        return await asyncio.to_thread(_read)

    # --- Repo files ---
    async def get_repo_files(self, job_id: str) -> List[Dict[str, Any]]:
        """Returns a recursive file structure representing the REPO folder."""
        repo_dir = settings.jobs_dir / job_id / "REPO"
        if not repo_dir.is_dir():
            return []

        def _get_tree(path: Path) -> List[Dict[str, Any]]:
            items = []
            for child in sorted(
                path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            ):
                # Skip hidden files/directories (like .git, .sciloom)
                if child.name.startswith("."):
                    continue

                is_dir = child.is_dir()
                item: Dict[str, Any] = {"name": child.name, "isDir": is_dir}

                if is_dir:
                    item["children"] = _get_tree(child)
                else:
                    item["size"] = child.stat().st_size

                items.append(item)
            return items

        return await asyncio.to_thread(_get_tree, repo_dir)

    # --- Job creation ---
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
        db: Optional[Session] = None,
    ) -> None:
        """Creates the initial database records for a new job and its stages.
        Manual claims are stored in .sciloom/CLAIMS.json (written after provisioning creates the directory).
        """
        pdf_path = f"jobs/{job_id}/paper.pdf"
        stage_names = [
            "PROVISIONING",
            "CLAIM_EXTRACTION",
            "CODE_EXECUTION",
            "CLAIM_REPLICATION",
            "DTREG_GENERATION",
        ]

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
                current_stage="PROVISIONING",
            )
            local_db.add(job)

            # 2. Add Stages
            for stage_name in stage_names:
                stage = models.Stage(
                    job_id=job_id, stage_name=stage_name, status="pending"
                )
                local_db.add(stage)

            local_db.commit()

            # 3. Store manual claims temporarily — they'll be written to .sciloom/CLAIMS.json
            #    after provisioning creates the REPO directory. Store in job_dir for now.
            if manual_claims:
                job_dir = settings.jobs_dir / job_id
                job_dir.mkdir(parents=True, exist_ok=True)
                pending_claims = [
                    {
                        "id": f"{job_id}_claim_{idx + 1}",
                        "jobId": job_id,
                        "claimText": claim_text,
                        "source": "user",
                        "replicated": False,
                        "createdAt": datetime.now().isoformat(),
                    }
                    for idx, claim_text in enumerate(manual_claims)
                ]
                pending_path = job_dir / "_pending_claims.json"
                pending_path.write_text(
                    json.dumps(pending_claims, indent=2), encoding="utf-8"
                )

        except Exception as e:
            local_db.rollback()
            raise e
        finally:
            if db is None:
                local_db.close()

    # --- Stage failure ---
    async def mark_stage_failed(
        self, job_id: str, stage_name: str, error_msg: str, db: Optional[Session] = None
    ) -> None:
        """Helper to mark a stage as failed and update the job status."""
        local_db = db or SessionLocal()
        try:
            # Update job status
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.updated_at = datetime.now(timezone.utc)

            # Update stage status
            stage = (
                local_db.query(models.Stage)
                .filter(
                    models.Stage.job_id == job_id, models.Stage.stage_name == stage_name
                )
                .first()
            )
            if stage:
                stage.status = "failed"
                stage.error_log = error_msg
                stage.completed_at = datetime.now().isoformat()
                if stage_name not in ("PROVISIONING", "CLAIM_EXTRACTION"):
                    sanitized_name = re.sub(r"_", "-", f"sbx-{job_id}")
                    stage.sandbox_info = json.dumps(
                        {
                            "sandboxId": sanitized_name,
                            "connectionCommand": f"sbx exec {sanitized_name} -- bash",
                        }
                    )
                else:
                    stage.sandbox_info = None
                stage.updated_at = datetime.now(timezone.utc)

            local_db.commit()
        except Exception as e:
            local_db.rollback()
            raise e
        finally:
            if db is None:
                local_db.close()

        await self.add_log(
            job_id, stage_name, "ERROR", f"Stage {stage_name} failed: {error_msg}"
        )

    # --- Stage 1: Provisioning ---
    async def run_provisioning(self, job_id: str, db: Optional[Session] = None) -> None:
        """Executes Stage 1: Provisioning (Job Setup)."""
        local_db = db or SessionLocal()
        stage_name = "PROVISIONING"
        try:
            # Fetch job via Session
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found in database.")

            # Update statuses
            job.status = "PROVISIONING"
            job.updated_at = datetime.now(timezone.utc)

            stage = (
                local_db.query(models.Stage)
                .filter(
                    models.Stage.job_id == job_id, models.Stage.stage_name == stage_name
                )
                .first()
            )
            if stage:
                stage.status = "running"
                stage.started_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)

            local_db.commit()

            # Files setup
            job_dir = settings.jobs_dir / job_id
            repo_dir = job_dir / "REPO"

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Initializing provisioning for job {job_id}...",
            )
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Creating workspace folder: jobs/job_{job_id}/",
            )
            job_dir.mkdir(parents=True, exist_ok=True)

            # Create opencode.json boundary file in job_dir to anchor the workspace root
            opencode_cfg = job_dir / "opencode.json"
            opencode_cfg.write_text("{}", encoding="utf-8")

            # Repo Setup
            repo_source = job.repo_source
            if repo_source == "github":
                repo_url = job.repo_url
                if not repo_url:
                    raise ValueError(
                        "Repository source is github, but repoUrl is missing."
                    )

                parsed_url = urllib.parse.urlparse(repo_url)
                if parsed_url.scheme not in ("http", "https"):
                    raise ValueError(
                        "Invalid repository URL scheme. Only HTTP and HTTPS are supported."
                    )

                await self.add_log(
                    job_id,
                    stage_name,
                    "INFO",
                    f"Cloning code repository from GitHub URL: {repo_url}...",
                )

                temp_repo_dir = job_dir / "REPO_temp"

                def _clone():
                    subprocess.run(
                        ["git", "clone", "--", repo_url, str(temp_repo_dir)],
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                await asyncio.to_thread(_clone)

                def _move_files():
                    repo_dir.mkdir(parents=True, exist_ok=True)
                    for item in temp_repo_dir.iterdir():
                        shutil.move(str(item), str(repo_dir / item.name))
                    shutil.rmtree(temp_repo_dir)

                await asyncio.to_thread(_move_files)
                await self.add_log(
                    job_id, stage_name, "INFO", "Repository cloned successfully."
                )

            elif repo_source == "zip":
                repo_zip = job_dir / "repo_temp.zip"
                if not repo_zip.is_file():
                    raise FileNotFoundError(
                        "Uploaded repository zip file not found in job workspace."
                    )

                await self.add_log(
                    job_id,
                    stage_name,
                    "INFO",
                    f"Extracting repository archive: {repo_zip.name}...",
                )

                def _extract_repo():
                    repo_dir.mkdir(parents=True, exist_ok=True)
                    with zipfile.ZipFile(repo_zip, "r") as zip_ref:
                        for member in zip_ref.infolist():
                            target_path = repo_dir / member.filename
                            if not target_path.resolve().is_relative_to(
                                repo_dir.resolve()
                            ):
                                raise PermissionError(
                                    f"Directory traversal detected in ZIP: {member.filename}"
                                )
                        zip_ref.extractall(repo_dir)
                    repo_zip.unlink()

                await asyncio.to_thread(_extract_repo)
                await self.add_log(
                    job_id,
                    stage_name,
                    "INFO",
                    f"Repository successfully setup at jobs/job_{job_id}/REPO/",
                )

            # Data Setup
            data_source = job.data_source
            if data_source == "zip":
                data_zip = job_dir / "data_temp.zip"
                if data_zip.is_file():
                    await self.add_log(
                        job_id,
                        stage_name,
                        "INFO",
                        f"Extracting additional dataset archive: {data_zip.name}...",
                    )

                    def _extract_data():
                        with zipfile.ZipFile(data_zip, "r") as zip_ref:
                            for member in zip_ref.infolist():
                                target_path = repo_dir / member.filename
                                if not target_path.resolve().is_relative_to(
                                    repo_dir.resolve()
                                ):
                                    raise PermissionError(
                                        f"Directory traversal detected in ZIP: {member.filename}"
                                    )
                            zip_ref.extractall(repo_dir)
                        data_zip.unlink()

                    await asyncio.to_thread(_extract_data)
                    await self.add_log(
                        job_id,
                        stage_name,
                        "INFO",
                        "Dataset extracted into repository folder.",
                    )
                else:
                    await self.add_log(
                        job_id,
                        stage_name,
                        "INFO",
                        "Dataset marked as zip but file not found; skipping.",
                    )
            else:
                await self.add_log(
                    job_id,
                    stage_name,
                    "INFO",
                    "Dataset marked as present in code repository workspace.",
                )

            # Create .sciloom directory inside REPO
            sciloom_dir = self._ensure_sciloom_dir(job_id)
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Created .sciloom working directory inside REPO.",
            )

            # Copy .opencode/agents configuration folder to the job REPO directory so agents are accessible inside the sandbox
            opencode_agents_src = REPO_ROOT / ".opencode" / "agents"
            if opencode_agents_src.is_dir():
                await self.add_log(
                    job_id,
                    stage_name,
                    "INFO",
                    "Copying .opencode agent definitions to job REPO directory...",
                )

                def _copy_opencode():
                    opencode_agents_dst = repo_dir / ".opencode" / "agents"
                    shutil.copytree(
                        opencode_agents_src, opencode_agents_dst, dirs_exist_ok=True
                    )

                await asyncio.to_thread(_copy_opencode)

            # Move pending manual claims to .sciloom/CLAIMS.json if they exist
            pending_claims_path = job_dir / "_pending_claims.json"
            if pending_claims_path.is_file():

                def _move_claims():
                    claims_data = json.loads(
                        pending_claims_path.read_text(encoding="utf-8")
                    )
                    claims_dest = sciloom_dir / "CLAIMS.json"
                    claims_dest.write_text(
                        json.dumps(claims_data, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    pending_claims_path.unlink()

                await asyncio.to_thread(_move_claims)
                await self.add_log(
                    job_id,
                    stage_name,
                    "INFO",
                    "User-provided claims stored in .sciloom/CLAIMS.json.",
                )

            # OCR Extraction
            pdf_file = job_dir / "paper.pdf"
            if not pdf_file.is_file():
                raise FileNotFoundError("Source PDF paper.pdf is missing.")

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Starting Gemini Vision API OCR extraction on paper PDF...",
            )
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Analyzing document formatting, images, tables and equations...",
            )

            from sciloom_pipeline.document_processing.pdf_extractor import PDFExtractor

            extractor = PDFExtractor(gemini_api_key=settings.gemini_api_key)
            # Output OCR markdown to .sciloom/ directory
            _md_path, char_counts = await extractor.extract(
                pdf_path=pdf_file, output_dir=sciloom_dir
            )

            # Save OCR metadata to .sciloom/ocr_metadata.json
            await self._save_ocr_metadata(job_id, char_counts)

            # Log summary of page character counts
            empty_pages = [i + 1 for i, c in enumerate(char_counts) if c == 0]
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Gemini Vision OCR successfully parsed all sections ({len(char_counts)} pages).",
            )
            if empty_pages:
                await self.add_log(
                    job_id,
                    stage_name,
                    "WARN",
                    f"Pages with 0 characters after retry: {empty_pages}. Consider using 'Retry OCR' to re-extract.",
                )
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Saving parsed content to markdown file: .sciloom/RESEARCH_PAPER.md",
            )

            # Finalize success status
            job.status = "PROVISIONED"
            job.updated_at = datetime.now(timezone.utc)
            if stage:
                stage.status = "completed"
                stage.completed_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)
            local_db.commit()

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Job setup completed. Directory structure finalized.",
            )
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "SQLite database updated: job status = PROVISIONED",
            )

        except Exception as e:
            local_db.rollback()
            await self.mark_stage_failed(job_id, stage_name, str(e), db=local_db)
            raise e
        finally:
            if db is None:
                local_db.close()

    # --- Helper: save OCR metadata to .sciloom/ocr_metadata.json ---
    async def _save_ocr_metadata(self, job_id: str, char_counts: list[int]) -> None:
        """Saves per-page character counts to .sciloom/ocr_metadata.json."""
        sciloom_dir = self._ensure_sciloom_dir(job_id)
        metadata_path = sciloom_dir / "ocr_metadata.json"

        def _write():
            data = {
                "page_char_counts": char_counts,
                "total_pages": len(char_counts),
                "total_chars": sum(char_counts),
            }
            metadata_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        await asyncio.to_thread(_write)

    async def _load_ocr_metadata(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Loads OCR metadata from .sciloom/ocr_metadata.json."""
        metadata_path = self._get_sciloom_dir(job_id) / "ocr_metadata.json"
        if not metadata_path.is_file():
            return None

        def _read():
            return json.loads(metadata_path.read_text(encoding="utf-8"))

        return await asyncio.to_thread(_read)

    def _load_ocr_metadata_sync(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Loads OCR metadata from .sciloom/ocr_metadata.json synchronously."""
        metadata_path = self._get_sciloom_dir(job_id) / "ocr_metadata.json"
        if not metadata_path.is_file():
            return None
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    # --- OCR Retry ---
    async def run_ocr_retry(self, job_id: str, db: Optional[Session] = None) -> None:
        """Re-runs only the PDF OCR step, preserving the existing repo/dataset workspace."""
        local_db = db or SessionLocal()
        stage_name = "PROVISIONING"
        try:
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found.")

            # Update status to running/PROVISIONING
            job.status = "PROVISIONING"
            job.updated_at = datetime.now(timezone.utc)

            stage = (
                local_db.query(models.Stage)
                .filter(
                    models.Stage.job_id == job_id, models.Stage.stage_name == stage_name
                )
                .first()
            )
            if stage:
                stage.status = "running"
                stage.started_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)

            local_db.commit()

            job_dir = settings.jobs_dir / job_id
            pdf_file = job_dir / "paper.pdf"
            if not pdf_file.is_file():
                raise FileNotFoundError(
                    "Source PDF paper.pdf is missing from workspace."
                )

            sciloom_dir = self._ensure_sciloom_dir(job_id)

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Starting OCR retry — re-extracting paper PDF...",
            )

            from sciloom_pipeline.document_processing.pdf_extractor import PDFExtractor

            extractor = PDFExtractor(gemini_api_key=settings.gemini_api_key)
            _md_path, char_counts = await extractor.extract(
                pdf_path=pdf_file, output_dir=sciloom_dir
            )

            await self._save_ocr_metadata(job_id, char_counts)

            empty_pages = [i + 1 for i, c in enumerate(char_counts) if c == 0]
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"OCR retry complete ({len(char_counts)} pages).",
            )
            if empty_pages:
                await self.add_log(
                    job_id,
                    stage_name,
                    "WARN",
                    f"Still empty after retry: pages {empty_pages}",
                )

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
            await self.mark_stage_failed(job_id, stage_name, str(e), db=local_db)
            raise
        finally:
            if db is None:
                local_db.close()

    # --- Stage 2: Claim Extraction ---
    async def run_claim_extraction(
        self, job_id: str, db: Optional[Session] = None
    ) -> None:
        """Executes Stage 2: Claim Extraction (automated via OpenCode agent)."""
        local_db = db or SessionLocal()
        stage_name = "CLAIM_EXTRACTION"
        try:
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found in database.")

            # Update statuses
            job.status = "CLAIM_EXTRACTION"
            job.updated_at = datetime.now(timezone.utc)

            stage = (
                local_db.query(models.Stage)
                .filter(
                    models.Stage.job_id == job_id, models.Stage.stage_name == stage_name
                )
                .first()
            )
            if stage:
                stage.status = "running"
                stage.started_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)

            local_db.commit()

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Starting Stage 2 claim extraction for job {job_id}...",
            )

            sciloom_dir = self._get_sciloom_dir(job_id)
            job_dir = settings.jobs_dir / job_id

            paper_file = sciloom_dir / "RESEARCH_PAPER.md"
            if not paper_file.is_file():
                raise FileNotFoundError(
                    f"RESEARCH_PAPER.md not found in .sciloom/. Has Stage 1 provisioning completed?"
                )
            await self.add_log(
                job_id, stage_name, "INFO", f"Using paper at: {paper_file}"
            )

            # Helper log callback
            async def log_callback(message: str, level: str = "INFO"):
                await self.add_log(job_id, stage_name, level, message)

            # Invoke agent_service to run the subprocess
            from sciloom_pipeline.services.agent_service import agent_service

            await agent_service.extract_claims(
                job_id, job_dir, paper_file, log_callback
            )

            # Read and parse generated CLAIMS.json — agent writes to job_dir
            json_file = job_dir / "CLAIMS.json"
            if not json_file.is_file():
                raise FileNotFoundError(
                    "CLAIMS.json was not generated by the claim extraction agent."
                )

            def _read_and_move_claims():
                raw = json.loads(json_file.read_text(encoding="utf-8"))
                if not isinstance(raw, list):
                    raise ValueError(
                        "CLAIMS.json must contain a list of claim objects."
                    )

                # Normalize claims and add metadata
                claims = []
                for idx, item in enumerate(raw):
                    claim_text = (
                        item.get("claimText")
                        or item.get("claim_text")
                        or item.get("quantitative_claim")
                        or ""
                    )
                    metrics = (
                        item.get("metrics") or item.get("specific_data_metrics") or ""
                    )
                    evidence = (
                        item.get("evidence") or item.get("grounding_evidence") or ""
                    )

                    if not claim_text.strip():
                        continue

                    claim_id = (
                        item.get("id")
                        or item.get("claim_id")
                        or f"{job_id}_claim_{idx + 1}"
                    )

                    claims.append(
                        {
                            "id": claim_id,
                            "jobId": job_id,
                            "claimText": claim_text,
                            "metrics": metrics,
                            "evidence": evidence,
                            "source": "agent",
                            "replicated": False,
                            "createdAt": datetime.now().isoformat(),
                        }
                    )

                # Write to .sciloom/CLAIMS.json (merge with existing user claims)
                claims_dest = sciloom_dir / "CLAIMS.json"
                existing_claims = []
                if claims_dest.is_file():
                    existing_data = json.loads(claims_dest.read_text(encoding="utf-8"))
                    if isinstance(existing_data, list):
                        # Keep user claims, replace agent claims
                        existing_claims = [
                            c for c in existing_data if c.get("source") == "user"
                        ]

                merged = existing_claims + claims
                claims_dest.write_text(
                    json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
                )

                # Clean up the agent's output file from job_dir
                json_file.unlink()

                return len(claims)

            claim_count = await asyncio.to_thread(_read_and_move_claims)

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Parsed and stored {claim_count} claims in .sciloom/CLAIMS.json",
            )

            # Update stage and job status on success
            job.status = "CLAIM_EXTRACTION"
            if stage:
                stage.status = "completed"
                stage.completed_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)

            local_db.commit()
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Stage 2 claim extraction successfully completed. {claim_count} claims stored.",
            )

        except Exception as e:
            local_db.rollback()
            await self.mark_stage_failed(job_id, stage_name, str(e), db=local_db)
            raise e
        finally:
            if db is None:
                local_db.close()

    # --- Stage 3: Code Execution ---
    async def run_code_execution(
        self, job_id: str, db: Optional[Session] = None
    ) -> None:
        """Executes Stage 3: Code Execution (sets up Docker sandbox, runs environment configuration agent)."""
        local_db = db or SessionLocal()
        stage_name = "CODE_EXECUTION"
        try:
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found in database.")

            # Update statuses
            job.status = "CODE_EXECUTION"
            job.updated_at = datetime.now(timezone.utc)

            stage = (
                local_db.query(models.Stage)
                .filter(
                    models.Stage.job_id == job_id, models.Stage.stage_name == stage_name
                )
                .first()
            )
            if stage:
                stage.status = "running"
                stage.started_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)

            local_db.commit()

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Starting Stage 3 code execution environment configuration for job {job_id}...",
            )

            job_dir = settings.jobs_dir / job_id
            repo_dir = job_dir / "REPO"
            if not repo_dir.is_dir():
                raise FileNotFoundError(
                    f"Repository directory REPO not found in {job_dir}. Has Stage 1 provisioning completed?"
                )

            # 1. Create Docker Sandbox via sandbox_service
            await self.add_log(
                job_id, stage_name, "INFO", "Initializing Docker sandbox environment..."
            )
            from sciloom_pipeline.services.sandbox_service import sandbox_service

            sandbox_name = await sandbox_service.create_sandbox(job_id, repo_dir)

            # Store sandbox_id on Job
            job.sandbox_id = sandbox_name
            local_db.commit()

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Docker sandbox '{sandbox_name}' created successfully.",
            )

            # Helper log callback
            async def log_callback(message: str, level: str = "INFO"):
                await self.add_log(job_id, stage_name, level, message)

            # 2. Invoke agent_service to run the Code Execution Agent in sandbox
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Launching Code Execution Agent inside the sandbox...",
            )
            from sciloom_pipeline.services.agent_service import agent_service

            agent_result = await agent_service.run_code_execution_agent(
                job_id, sandbox_name, log_callback
            )

            # Store session details in stage output_json if found
            session_id = agent_result.get("session_id")
            job.opencode_session_id = session_id
            job.opencode_server_url = settings.opencode_server_url
            local_db.commit()

            if not agent_result.get("success"):
                err_msg = (
                    agent_result.get("error_details") or "Code execution agent failed."
                )
                raise RuntimeError(err_msg)

            # Update stage and job status on success
            job.status = "CODE_EXECUTION"
            if stage:
                stage.status = "completed"
                stage.completed_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)
                stage.output_json = json.dumps(
                    {
                        "status": "success",
                        "sandboxId": sandbox_name,
                        "opencodeSessionId": session_id,
                    }
                )

            local_db.commit()
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Stage 3 code execution setup successfully completed. Environment is ready.",
            )

        except Exception as e:
            local_db.rollback()
            # Store sandbox access details on failure
            stage = (
                local_db.query(models.Stage)
                .filter(
                    models.Stage.job_id == job_id, models.Stage.stage_name == stage_name
                )
                .first()
            )
            if stage:
                sanitized_name = re.sub(r"_", "-", f"sbx-{job_id}")
                stage.sandbox_info = json.dumps(
                    {
                        "sandboxId": sanitized_name,
                        "connectionCommand": f"sbx exec {sanitized_name} -- bash",
                    }
                )
                local_db.commit()

            await self.mark_stage_failed(job_id, stage_name, str(e), db=local_db)
            raise e
        finally:
            if db is None:
                local_db.close()

    # --- Sandbox management ---
    async def get_sandbox_info(
        self, job_id: str, db: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """Returns details about the sandbox container for this job."""
        local_db = db or SessionLocal()
        try:
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job or not job.sandbox_id:
                return None

            from sciloom_pipeline.services.sandbox_service import sandbox_service

            sbx_status = await sandbox_service.get_sandbox_status(job.sandbox_id)

            status = "not_found"
            if sbx_status:
                status = "running"

            return {
                "sandboxId": job.sandbox_id,
                "sandboxName": job.sandbox_id,
                "status": status,
                "connectionCommand": f"sbx exec {job.sandbox_id} -- bash",
                "opencodeSessionId": job.opencode_session_id,
                "opencodeServerUrl": job.opencode_server_url,
            }
        finally:
            if db is None:
                local_db.close()

    async def delete_sandbox(self, job_id: str, db: Optional[Session] = None) -> None:
        """Explicitly deletes the Docker sandbox for a job."""
        local_db = db or SessionLocal()
        stage_name = "CODE_EXECUTION"
        try:
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job or not job.sandbox_id:
                await self.add_log(
                    job_id, stage_name, "WARN", "No sandbox exists to delete."
                )
                return

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Deleting Docker sandbox: {job.sandbox_id}...",
            )
            from sciloom_pipeline.services.sandbox_service import sandbox_service

            try:
                await sandbox_service.remove_sandbox(job.sandbox_id)
                await self.add_log(
                    job_id,
                    stage_name,
                    "INFO",
                    f"Docker sandbox {job.sandbox_id} successfully deleted.",
                )
            except Exception as e:
                await self.add_log(
                    job_id,
                    stage_name,
                    "WARN",
                    f"Failed to delete sandbox container (it may already be removed): {e}",
                )

            # Nullify sandbox_id and session info on Job
            job.sandbox_id = None
            job.opencode_session_id = None
            job.opencode_server_url = None
            local_db.commit()

        except Exception as e:
            local_db.rollback()
            raise e
        finally:
            if db is None:
                local_db.close()

    # --- Stage 4: Claim Replication ---
    async def run_claim_replication(
        self, job_id: str, db: Optional[Session] = None
    ) -> None:
        """Executes Stage 4: Claim Replication (runs claim replication agent in sandbox)."""
        # Validate job_id to prevent any shell/path injection
        if not re.match(r"^[a-zA-Z0-9_-]+$", job_id):
            raise ValueError(f"Invalid job_id: {job_id}")

        local_db = db or SessionLocal()
        stage_name = "CLAIM_REPLICATION"
        try:
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found in database.")

            # Update statuses
            job.status = "CLAIM_REPLICATION"
            job.updated_at = datetime.now(timezone.utc)

            stage = (
                local_db.query(models.Stage)
                .filter(
                    models.Stage.job_id == job_id, models.Stage.stage_name == stage_name
                )
                .first()
            )
            if stage:
                stage.status = "running"
                stage.started_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)

            local_db.commit()

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Starting Stage 4 claim replication for job {job_id}...",
            )

            sandbox_name = job.sandbox_id
            if not sandbox_name:
                raise ValueError(
                    f"No sandbox exists for job {job_id}. Ensure Stage 3 has run successfully."
                )

            # Check if all claims are already replicated inside the sandbox (human-in-the-loop manual override)
            is_already_replicated = False
            from sciloom_pipeline.services.sandbox_service import sandbox_service

            try:
                claims_json_content = await sandbox_service.exec_in_sandbox(
                    sandbox_name, ["cat", "/home/agent/workspace/.sciloom/CLAIMS.json"]
                )
                sandbox_claims = json.loads(claims_json_content)
                if isinstance(sandbox_claims, list) and len(sandbox_claims) > 0:
                    if all(c.get("replicated") is True for c in sandbox_claims):
                        is_already_replicated = True
                        await self.add_log(
                            job_id,
                            stage_name,
                            "INFO",
                            "Detected that all claims are already successfully replicated inside the sandbox.",
                        )
            except Exception:
                pass

            if is_already_replicated:
                repo_dir = settings.jobs_dir / job_id / "REPO"
                sciloom_dir = repo_dir / ".sciloom"
                sciloom_dir.mkdir(parents=True, exist_ok=True)
                try:
                    await sandbox_service.copy_from_sandbox(
                        sandbox_name,
                        "/home/agent/workspace/.sciloom/CLAIMS.json",
                        sciloom_dir / "CLAIMS.json",
                    )
                except Exception as e:
                    await self.add_log(
                        job_id,
                        stage_name,
                        "WARN",
                        f"Failed to sync CLAIMS.json back to host: {e}",
                    )

                job.status = "CLAIM_REPLICATION"
                if stage:
                    stage.status = "completed"
                    stage.completed_at = datetime.now().isoformat()
                    stage.updated_at = datetime.now(timezone.utc)
                    stage.output_json = json.dumps(
                        {
                            "status": "success",
                            "sandboxId": sandbox_name,
                            "opencodeSessionId": job.opencode_session_id,
                        }
                    )
                local_db.commit()
                return

            # Helper log callback
            async def log_callback(message: str, level: str = "INFO"):
                await self.add_log(job_id, stage_name, level, message)

            # Generate CLAIMS.md from CLAIMS.json for the replication agent
            claims = await self.get_claims_for_job(job_id)
            if not claims:
                await self.add_log(
                    job_id, stage_name, "WARN", "No claims found to replicate."
                )

            # Format CLAIMS.md
            claims_md_lines = ["# Claims to Replicate\n"]
            for c in claims:
                claim_id = c.get("id") or "UNKNOWN"
                text = c.get("claimText") or c.get("claim_text") or ""
                metrics = c.get("metrics") or ""
                evidence = c.get("evidence") or ""
                claims_md_lines.append(f"## {claim_id}")
                claims_md_lines.append(f"- **Text**: {text}")
                claims_md_lines.append(f"- **Metrics**: {metrics}")
                claims_md_lines.append(f"- **Evidence**: {evidence}\n")
            claims_md_content = "\n".join(claims_md_lines)

            # Write CLAIMS.md on host
            repo_dir = settings.jobs_dir / job_id / "REPO"
            sciloom_dir = repo_dir / ".sciloom"

            # Make sure .sciloom dir exists on host (though it should)
            sciloom_dir.mkdir(parents=True, exist_ok=True)

            claims_md_host_path = repo_dir / "CLAIMS.md"

            def _write_claims_md():
                claims_md_host_path.write_text(claims_md_content, encoding="utf-8")
                claims_md_sciloom_path = sciloom_dir / "CLAIMS.md"
                claims_md_sciloom_path.write_text(claims_md_content, encoding="utf-8")

            await asyncio.to_thread(_write_claims_md)

            # Copy files to sandbox (sbx cp)
            from sciloom_pipeline.services.sandbox_service import sandbox_service

            # Copy RESEARCH_PAPER.md from .sciloom to REPO root on host
            paper_md_src = sciloom_dir / "RESEARCH_PAPER.md"
            if paper_md_src.is_file():
                paper_md_dst = repo_dir / "RESEARCH_PAPER.md"

                def _copy_paper():
                    shutil.copyfile(paper_md_src, paper_md_dst)

                await asyncio.to_thread(_copy_paper)
                try:
                    await sandbox_service.copy_to_sandbox(
                        sandbox_name,
                        paper_md_dst,
                        "/home/agent/workspace/RESEARCH_PAPER.md",
                    )
                    await sandbox_service.copy_to_sandbox(
                        sandbox_name,
                        paper_md_dst,
                        "/home/agent/workspace/.sciloom/RESEARCH_PAPER.md",
                    )
                except Exception as e:
                    await self.add_log(
                        job_id,
                        stage_name,
                        "WARN",
                        f"Could not copy RESEARCH_PAPER.md to sandbox: {e}",
                    )

            try:
                # Copy CLAIMS.md to sandbox
                await sandbox_service.copy_to_sandbox(
                    sandbox_name, claims_md_host_path, "/home/agent/workspace/CLAIMS.md"
                )
                await sandbox_service.copy_to_sandbox(
                    sandbox_name,
                    claims_md_host_path,
                    "/home/agent/workspace/.sciloom/CLAIMS.md",
                )
                # Copy CLAIMS.json to sandbox
                claims_json_host_path = sciloom_dir / "CLAIMS.json"
                if claims_json_host_path.is_file():
                    await sandbox_service.copy_to_sandbox(
                        sandbox_name,
                        claims_json_host_path,
                        "/home/agent/workspace/.sciloom/CLAIMS.json",
                    )
            except Exception as e:
                await self.add_log(
                    job_id,
                    stage_name,
                    "WARN",
                    f"Could not copy claim files to sandbox: {e}",
                )

            # Copy user attachments to sandbox if they exist
            user_attachments_dir = settings.jobs_dir / job_id / "user_attachments"
            if user_attachments_dir.is_dir():
                await self.add_log(
                    job_id, stage_name, "INFO", "Copying user attachments to sandbox..."
                )
                try:
                    await sandbox_service.copy_to_sandbox(
                        sandbox_name,
                        user_attachments_dir,
                        "/home/agent/workspace/user_attachments",
                    )
                    await sandbox_service.copy_to_sandbox(
                        sandbox_name,
                        user_attachments_dir,
                        "/home/agent/workspace/.sciloom/user_attachments",
                    )
                except Exception as e:
                    await self.add_log(
                        job_id,
                        stage_name,
                        "WARN",
                        f"Failed to copy user attachments: {e}",
                    )

            # 1. Run the Code Execution Agent to set up env/resolve errors
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Running Code Execution Agent to verify environment setup...",
            )
            from sciloom_pipeline.services.agent_service import agent_service

            code_exec_result = await agent_service.run_code_execution_agent(
                job_id, sandbox_name, log_callback
            )

            if not code_exec_result.get("success"):
                err_msg = (
                    code_exec_result.get("error_details")
                    or "Code execution agent failed to set up environment."
                )
                raise RuntimeError(f"Environment configuration failed: {err_msg}")

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Environment verified successfully. Handing off to Claim Replication Agent...",
            )

            # 2. Run the Claim Replication Agent
            replication_result = await agent_service.run_claim_replication_agent(
                job_id, sandbox_name, log_callback
            )

            # Store session details
            session_id = replication_result.get("session_id")
            if session_id:
                job.opencode_session_id = session_id
                local_db.commit()

            if not replication_result.get("success"):
                err_msg = (
                    replication_result.get("error_details")
                    or "Claim replication agent failed."
                )
                raise RuntimeError(err_msg)

            # Stage completed successfully
            job.status = "CLAIM_REPLICATION"
            if stage:
                stage.status = "completed"
                stage.completed_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)
                stage.output_json = json.dumps(
                    {
                        "status": "success",
                        "sandboxId": sandbox_name,
                        "opencodeSessionId": session_id,
                    }
                )

            local_db.commit()
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Stage 4 claim replication successfully completed. All quantitative claims replicated.",
            )

        except Exception as e:
            local_db.rollback()
            # Store sandbox access details on failure
            stage = (
                local_db.query(models.Stage)
                .filter(
                    models.Stage.job_id == job_id, models.Stage.stage_name == stage_name
                )
                .first()
            )
            if stage:
                sanitized_name = re.sub(r"_", "-", f"sbx-{job_id}")
                stage.sandbox_info = json.dumps(
                    {
                        "sandboxId": sanitized_name,
                        "connectionCommand": f"sbx exec {sanitized_name} -- bash",
                    }
                )
                local_db.commit()

            await self.mark_stage_failed(job_id, stage_name, str(e), db=local_db)
            raise e
        finally:
            if db is None:
                local_db.close()

    async def _detect_wsl_prefix(self, sandbox_name: str) -> Optional[str]:
        """Runs find in the container to detect any /wsl.localhost/ prefix."""
        try:
            from sciloom_pipeline.services.sandbox_service import sandbox_service

            # We list the root /wsl.localhost directory.
            # E.g. find /wsl.localhost -maxdepth 2 -type d
            # We expect a line like "/wsl.localhost/Ubuntu-22.04"
            out = await sandbox_service.exec_in_sandbox(
                sandbox_name, ["find", "/wsl.localhost", "-maxdepth", "2", "-type", "d"]
            )
            for line in out.splitlines():
                line = line.strip()
                # Check for /wsl.localhost/<distro> (must have 3 path components)
                parts = [p for p in line.split("/") if p]
                if len(parts) >= 2 and parts[0] == "wsl.localhost":
                    prefix = f"/wsl.localhost/{parts[1]}"
                    logger.info(f"Detected WSL mount prefix inside container: {prefix}")
                    return prefix
        except Exception as e:
            logger.debug(
                f"WSL prefix detection bypassed or failed (non-WSL environment): {e}"
            )
        return None

    async def sync_host_to_sandbox(self, job_id: str, sandbox_name: str) -> None:
        """Copies host files to container native workspace using container-side rsync."""
        prefix = await self._detect_wsl_prefix(sandbox_name)
        if not prefix:
            logger.info(
                "Non-WSL environment detected. Workspace syncing skipped (direct volume mount)."
            )
            return

        repo_dir = (settings.jobs_dir / job_id / "REPO").resolve()
        mount_path = f"{prefix}{repo_dir}"

        logger.info(
            f"Syncing host files into container workspace (excluding .venv, .git): {mount_path} -> /home/agent/workspace/"
        )
        from sciloom_pipeline.services.sandbox_service import sandbox_service

        try:
            cmd = [
                "rsync",
                "-a",
                "--exclude=.venv",
                "--exclude=.git",
                f"{mount_path}/",
                "/home/agent/workspace/",
            ]
            await sandbox_service.exec_in_sandbox(sandbox_name, cmd)
            logger.info("Successfully synced host files to container workspace.")
        except Exception as e:
            logger.error(f"Failed to sync host to container workspace: {e}")
            raise RuntimeError(f"Workspace sync-in failed: {e}")

    async def sync_sandbox_to_host(self, job_id: str, sandbox_name: str) -> None:
        """Copies container native workspace files back to host using container-side rsync."""
        prefix = await self._detect_wsl_prefix(sandbox_name)
        if not prefix:
            logger.info(
                "Non-WSL environment detected. Workspace syncing skipped (direct volume mount)."
            )
            return

        repo_dir = (settings.jobs_dir / job_id / "REPO").resolve()
        mount_path = f"{prefix}{repo_dir}"

        logger.info(
            f"Syncing container workspace files back to host (excluding .venv, .git): /home/agent/workspace/ -> {mount_path}"
        )
        from sciloom_pipeline.services.sandbox_service import sandbox_service

        try:
            cmd = [
                "rsync",
                "-a",
                "--exclude=.venv",
                "--exclude=.git",
                "/home/agent/workspace/",
                f"{mount_path}/",
            ]
            await sandbox_service.exec_in_sandbox(sandbox_name, cmd)
            logger.info("Successfully synced container workspace back to host.")
        except Exception as e:
            logger.error(f"Failed to sync container workspace back to host: {e}")
            raise RuntimeError(f"Workspace sync-out failed: {e}")

    # --- Stage 5: DTREG Generation ---
    async def run_dtreg_generation(
        self, job_id: str, db: Optional[Session] = None
    ) -> None:
        """Executes Stage 5: DTREG Generation (runs dtreg generation agent in sandbox)."""
        # Validate job_id to prevent any shell/path injection
        if not re.match(r"^[a-zA-Z0-9_-]+$", job_id):
            raise ValueError(f"Invalid job_id: {job_id}")

        local_db = db or SessionLocal()
        stage_name = "DTREG_GENERATION"
        try:
            job = local_db.query(models.Job).filter(models.Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found in database.")

            # Update statuses
            job.status = "DTREG_GENERATION"
            job.updated_at = datetime.now(timezone.utc)

            stage = (
                local_db.query(models.Stage)
                .filter(
                    models.Stage.job_id == job_id, models.Stage.stage_name == stage_name
                )
                .first()
            )
            if stage:
                stage.status = "running"
                stage.started_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)

            local_db.commit()

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                f"Starting Stage 5 DTREG metadata generation for job {job_id}...",
            )

            sandbox_name = job.sandbox_id
            repo_dir = settings.jobs_dir / job_id / "REPO"
            sciloom_dir = repo_dir / ".sciloom"
            sciloom_dir.mkdir(parents=True, exist_ok=True)

            # 1. First, check if sandbox is running. If so, sync the current state back to host first.
            from sciloom_pipeline.services.sandbox_service import sandbox_service

            sandbox_active = False
            if sandbox_name:
                status_info = await sandbox_service.get_sandbox_status(sandbox_name)
                if status_info:
                    sandbox_active = True
                    await self.add_log(
                        job_id,
                        stage_name,
                        "INFO",
                        f"Active sandbox '{sandbox_name}' found. Performing pre-stage workspace sync-back to host...",
                    )
                    try:
                        await self.sync_sandbox_to_host(job_id, sandbox_name)
                    except Exception as e:
                        await self.add_log(
                            job_id,
                            stage_name,
                            "WARN",
                            f"Pre-stage workspace sync-back failed: {e}",
                        )

            # Check if DTREG is already successfully generated (human-in-the-loop manual override)
            is_already_generated = False
            host_dtreg_path = sciloom_dir / "dtreg_output.jsonld"
            if host_dtreg_path.is_file():
                try:
                    json.loads(host_dtreg_path.read_text(encoding="utf-8"))
                    is_already_generated = True
                    await self.add_log(
                        job_id,
                        stage_name,
                        "INFO",
                        "Detected that DTREG metadata is already successfully generated on the host.",
                    )
                except Exception:
                    pass

            if not is_already_generated and sandbox_active:
                try:
                    dtreg_content = await sandbox_service.exec_in_sandbox(
                        sandbox_name,
                        ["cat", "/home/agent/workspace/.sciloom/dtreg_output.jsonld"],
                    )
                    json.loads(dtreg_content)
                    is_already_generated = True
                    await self.add_log(
                        job_id,
                        stage_name,
                        "INFO",
                        "Detected that DTREG metadata is already successfully generated inside the sandbox.",
                    )
                    try:
                        await self.sync_sandbox_to_host(job_id, sandbox_name)
                    except Exception as e:
                        await self.add_log(
                            job_id,
                            stage_name,
                            "WARN",
                            f"Failed to sync DTREG metadata back to host: {e}",
                        )
                except Exception:
                    pass

            if is_already_generated:
                job.status = "DTREG_GENERATION"
                if stage:
                    stage.status = "completed"
                    stage.completed_at = datetime.now().isoformat()
                    stage.updated_at = datetime.now(timezone.utc)
                    stage.output_json = json.dumps(
                        {
                            "status": "success",
                            "sandboxId": sandbox_name,
                            "opencodeSessionId": job.opencode_session_id,
                        }
                    )
                local_db.commit()
                await self.add_log(
                    job_id,
                    stage_name,
                    "INFO",
                    "Stage 5 DTREG metadata generation successfully completed (bypassed via existing output).",
                )
                return

            # 2. Recreate/create sandbox if not found or not running
            if not sandbox_active:
                await self.add_log(
                    job_id,
                    stage_name,
                    "INFO",
                    "Sandbox not active or missing. Re-initializing Docker sandbox environment...",
                )
                sandbox_name = await sandbox_service.create_sandbox(job_id, repo_dir)
                job.sandbox_id = sandbox_name
                local_db.commit()
                await self.add_log(
                    job_id,
                    stage_name,
                    "INFO",
                    f"Docker sandbox '{sandbox_name}' initialized.",
                )

            # 3. Ensure global skills and examples are copied to host job folder under .sciloom/
            # This ensures they are available to be synced into the sandbox workspace
            global_skills_src = REPO_ROOT / ".agents" / "skills"
            global_examples_src = REPO_ROOT / "examples"
            global_opencode_agents_src = REPO_ROOT / ".opencode" / "agents"

            # Host destinations
            skills_dst = sciloom_dir / "dtreg_skills"
            examples_dst = sciloom_dir / "dtreg_examples"
            opencode_dst = repo_dir / ".opencode" / "agents"

            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Copying dtreg skills, examples, and agent configurations to job REPO...",
            )

            def _copy_resources():
                if global_skills_src.is_dir():
                    shutil.copytree(global_skills_src, skills_dst, dirs_exist_ok=True)
                if global_examples_src.is_dir():
                    shutil.copytree(
                        global_examples_src, examples_dst, dirs_exist_ok=True
                    )
                if global_opencode_agents_src.is_dir():
                    shutil.copytree(
                        global_opencode_agents_src, opencode_dst, dirs_exist_ok=True
                    )

            await asyncio.to_thread(_copy_resources)

            # 4. Sync host workspace into the sandbox native container workspace
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Synchronizing files from host REPO to container native workspace...",
            )
            await self.sync_host_to_sandbox(job_id, sandbox_name)

            # Helper log callback
            async def log_callback(message: str, level: str = "INFO"):
                await self.add_log(job_id, stage_name, level, message)

            # 5. Launch the DTREG Generation Agent inside the sandbox
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Launching DTREG Generation Agent inside the sandbox...",
            )
            from sciloom_pipeline.services.agent_service import agent_service

            agent_result = await agent_service.run_dtreg_generation_agent(
                job_id, sandbox_name, log_callback
            )

            session_id = agent_result.get("session_id")
            if session_id:
                job.opencode_session_id = session_id
                local_db.commit()

            if not agent_result.get("success"):
                err_msg = (
                    agent_result.get("error_details")
                    or "DTREG generation agent failed."
                )
                raise RuntimeError(err_msg)

            # 6. Success! Sync generated metadata and scripts back to the host job folder
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Agent finished successfully. Persisting generated files back to host REPO...",
            )
            await self.sync_sandbox_to_host(job_id, sandbox_name)

            # Set status to completed
            job.status = "DTREG_GENERATION"
            if stage:
                stage.status = "completed"
                stage.completed_at = datetime.now().isoformat()
                stage.updated_at = datetime.now(timezone.utc)
                stage.output_json = json.dumps(
                    {
                        "status": "success",
                        "sandboxId": sandbox_name,
                        "opencodeSessionId": session_id,
                    }
                )

            local_db.commit()
            await self.add_log(
                job_id,
                stage_name,
                "INFO",
                "Stage 5 DTREG metadata generation successfully completed.",
            )

        except Exception as e:
            local_db.rollback()
            # Store sandbox access details on failure
            stage = (
                local_db.query(models.Stage)
                .filter(
                    models.Stage.job_id == job_id, models.Stage.stage_name == stage_name
                )
                .first()
            )
            if stage:
                sanitized_name = re.sub(r"_", "-", f"sbx-{job_id}")
                stage.sandbox_info = json.dumps(
                    {
                        "sandboxId": sanitized_name,
                        "connectionCommand": f"sbx exec {sanitized_name} -- bash",
                    }
                )
                local_db.commit()

            await self.mark_stage_failed(job_id, stage_name, str(e), db=local_db)
            raise e
        finally:
            if db is None:
                local_db.close()

    # --- Update OCR Markdown ---
    async def update_ocr_markdown(
        self, job_id: str, markdown: str, db: Optional[Session] = None
    ) -> None:
        """Overwrites RESEARCH_PAPER.md in .sciloom/ with the provided markdown and recalculates page counts."""
        sciloom_dir = self._ensure_sciloom_dir(job_id)
        md_file = sciloom_dir / "RESEARCH_PAPER.md"

        def _write_file():
            md_file.write_text(markdown, encoding="utf-8")

        await asyncio.to_thread(_write_file)

        # Recalculate per-page character counts by splitting on horizontal rules
        pages = markdown.split("\n\n---\n\n")
        char_counts = [len(p) for p in pages]
        await self._save_ocr_metadata(job_id, char_counts)

    # --- Helper formatting methods ---
    def _format_job(self, job: models.Job) -> Dict[str, Any]:
        pdf_path = job.pdf_path
        pdf_name = Path(pdf_path).name if pdf_path else ""

        ocr_counts = None
        metadata = self._load_ocr_metadata_sync(job.id)
        if metadata and "page_char_counts" in metadata:
            ocr_counts = metadata["page_char_counts"]

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
            "sandboxId": job.sandbox_id,
            "opencodeSessionId": job.opencode_session_id,
            "opencodeServerUrl": job.opencode_server_url,
            "createdAt": job.created_at.isoformat() if job.created_at else "",
            "updatedAt": job.updated_at.isoformat() if job.updated_at else "",
            "ocrPageCharCounts": ocr_counts,
        }

    def _format_stage(self, stage: models.Stage) -> Dict[str, Any]:
        sandbox_info_raw = stage.sandbox_info
        sandbox_info = _json_loads(sandbox_info_raw) if sandbox_info_raw else None

        return {
            "id": f"{stage.job_id}_stage_{stage.id}",
            "jobId": stage.job_id,
            "stageName": stage.stage_name,
            "status": stage.status,
            "errorLog": stage.error_log,
            "sandboxInfo": sandbox_info,
            "startedAt": stage.started_at,
            "completedAt": stage.completed_at,
        }


def _json_loads(val: str) -> Any:
    try:
        return json.loads(val)
    except Exception:
        return None


job_service = JobService()

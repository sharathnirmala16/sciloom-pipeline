import json
import pytest
from unittest.mock import AsyncMock, patch
from sciloom_pipeline.services.job_service import job_service
from sciloom_pipeline.config import settings
from sciloom_pipeline.db import models
from sciloom_pipeline.db.database import SessionLocal

@pytest.mark.asyncio
class TestClaimExtraction:
    
    @pytest.fixture(autouse=True)
    def setup_job(self):
        """Sets up a test job record in the database and a temporary directory."""
        self.job_id = "test_job_extraction"
        self.job_dir = settings.jobs_dir / self.job_id
        self.job_dir.mkdir(parents=True, exist_ok=True)
        
        # Write a dummy paper.pdf and RESEARCH_PAPER.md under .sciloom/ in REPO
        pdf_path = self.job_dir / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 dummy contents")
        
        sciloom_dir = self.job_dir / "REPO" / ".sciloom"
        sciloom_dir.mkdir(parents=True, exist_ok=True)
        md_path = sciloom_dir / "RESEARCH_PAPER.md"
        md_path.write_text("# Test Paper\nSome content to analyze.", encoding="utf-8")
        
        # Create DB record using SessionLocal
        with SessionLocal() as db:
            # Create Job record
            job = models.Job(
                id=self.job_id,
                title="TDD Extraction Test",
                pdf_path=f"jobs/{self.job_id}/paper.pdf",
                repo_source="zip",
                data_source="in_repo",
                status="PROVISIONED",
                current_stage="CLAIM_EXTRACTION"
            )
            db.add(job)
            
            # Create Stage records
            stage_names = ["PROVISIONING", "CLAIM_EXTRACTION", "CODE_EXECUTION", "CLAIM_REPLICATION", "DTREG_GENERATION"]
            for name in stage_names:
                stage = models.Stage(
                    job_id=self.job_id,
                    stage_name=name,
                    status="completed" if name == "PROVISIONING" else "pending"
                )
                db.add(stage)
            db.commit()
            
        yield
        
        # Clean up files
        if self.job_dir.exists():
            import shutil
            shutil.rmtree(self.job_dir, ignore_errors=True)

    @patch("asyncio.create_subprocess_exec")
    async def test_run_claim_extraction_success(self, mock_exec):
        """Positive Case: Verify claim extraction runs successfully and populates database."""
        # Mock subprocess to exit with 0
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.stdout.readline = AsyncMock(side_effect=[b"Claim extraction started...\n", b"Finished.\n", b""])
        mock_process.stderr.readline = AsyncMock(side_effect=[b""])
        mock_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = mock_process
        
        # Write mock CLAIMS.json which the agent is supposed to output
        claims_data = [
            {
                "id": "CLAIM-001",
                "claimText": "Model accuracy increased by 15%",
                "metrics": "15% increase",
                "evidence": "Section 4.2"
            },
            {
                "id": "CLAIM-002",
                "claimText": "Runtime decreased to 20ms",
                "metrics": "20ms runtime",
                "evidence": "Figure 3"
            }
        ]
        json_file = self.job_dir / "CLAIMS.json"
        json_file.write_text(json.dumps(claims_data), encoding="utf-8")
        
        # Run extraction
        await job_service.run_claim_extraction(self.job_id)
        
        # Verify job and stage status
        job = await job_service.get_job_by_id(self.job_id)
        assert job["status"] == "CLAIM_EXTRACTION"
        assert job["currentStage"] == "CLAIM_EXTRACTION"
        
        stages = await job_service.get_stages_for_job(self.job_id)
        ce_stage = next(s for s in stages if s["stageName"] == "CLAIM_EXTRACTION")
        assert ce_stage["status"] == "completed"
        
        # Verify claims were added to DB
        claims = await job_service.get_claims_for_job(self.job_id)
        assert len(claims) == 2
        assert claims[0]["claimText"] == "Model accuracy increased by 15%"
        assert claims[0]["metrics"] == "15% increase"
        assert claims[0]["evidence"] == "Section 4.2"
        assert claims[0]["source"] == "agent"
        assert claims[1]["claimText"] == "Runtime decreased to 20ms"

    @patch("asyncio.create_subprocess_exec")
    async def test_run_claim_extraction_agent_failure(self, mock_exec):
        """Negative Case: Subprocess exits with non-zero code."""
        # Mock subprocess to exit with 1
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.stdout.readline = AsyncMock(side_effect=[b"Some warning...\n", b""])
        mock_process.stderr.readline = AsyncMock(side_effect=[b"Fatal agent error!\n", b""])
        mock_process.wait = AsyncMock(return_value=1)
        mock_exec.return_value = mock_process
        
        # Run extraction and expect error
        with pytest.raises(RuntimeError) as exc:
            await job_service.run_claim_extraction(self.job_id)
            
        assert "exited with return code 1" in str(exc.value)
        
        # Verify statuses updated to FAILED / failed
        job = await job_service.get_job_by_id(self.job_id)
        assert job["status"] == "FAILED"
        
        stages = await job_service.get_stages_for_job(self.job_id)
        ce_stage = next(s for s in stages if s["stageName"] == "CLAIM_EXTRACTION")
        assert ce_stage["status"] == "failed"
        assert "exited with return code 1" in ce_stage["errorLog"]

    @patch("asyncio.create_subprocess_exec")
    async def test_run_claim_extraction_missing_claims_json(self, mock_exec):
        """Negative Case: Subprocess succeeds but CLAIMS.json is missing."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.stdout.readline = AsyncMock(side_effect=[b"Agent finished successfully.\n", b""])
        mock_process.stderr.readline = AsyncMock(side_effect=[b""])
        mock_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = mock_process
        
        # Run extraction and expect FileNotFoundError (since CLAIMS.json is not written)
        with pytest.raises(FileNotFoundError) as exc:
            await job_service.run_claim_extraction(self.job_id)
            
        assert "CLAIMS.json was not generated" in str(exc.value)
        
        job = await job_service.get_job_by_id(self.job_id)
        assert job["status"] == "FAILED"
        
        stages = await job_service.get_stages_for_job(self.job_id)
        ce_stage = next(s for s in stages if s["stageName"] == "CLAIM_EXTRACTION")
        assert ce_stage["status"] == "failed"

    @patch("asyncio.create_subprocess_exec")
    async def test_run_claim_extraction_invalid_json(self, mock_exec):
        """Negative Case: Subprocess succeeds but CLAIMS.json contains invalid JSON."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.stdout.readline = AsyncMock(side_effect=[b"Agent finished successfully.\n", b""])
        mock_process.stderr.readline = AsyncMock(side_effect=[b""])
        mock_process.wait = AsyncMock(return_value=0)
        mock_exec.return_value = mock_process
        
        # Write malformed JSON file
        json_file = self.job_dir / "CLAIMS.json"
        json_file.write_text("{malformed json", encoding="utf-8")
        
        # Run extraction and expect json decoding error
        with pytest.raises(json.JSONDecodeError):
            await job_service.run_claim_extraction(self.job_id)
            
        job = await job_service.get_job_by_id(self.job_id)
        assert job["status"] == "FAILED"
        
        stages = await job_service.get_stages_for_job(self.job_id)
        ce_stage = next(s for s in stages if s["stageName"] == "CLAIM_EXTRACTION")
        assert ce_stage["status"] == "failed"

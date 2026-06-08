import json
import shutil
import pytest
from unittest.mock import patch, AsyncMock
from sciloom_pipeline.services.job_service import job_service
from sciloom_pipeline.config import settings
from sciloom_pipeline.db import models
from sciloom_pipeline.db.database import SessionLocal

@pytest.mark.asyncio
class TestClaimReplication:
    
    @pytest.fixture(autouse=True)
    def setup_job(self):
        """Sets up a test job record in the database and a temporary directory."""
        self.job_id = "test_job_claim_rep"
        self.job_dir = settings.jobs_dir / self.job_id
        self.job_dir.mkdir(parents=True, exist_ok=True)
        
        # Create REPO and .sciloom folders
        repo_dir = self.job_dir / "REPO"
        sciloom_dir = repo_dir / ".sciloom"
        sciloom_dir.mkdir(parents=True, exist_ok=True)
        
        # Create dummy CLAIMS.json
        claims_json = [
            {
                "id": "CLAIM-001",
                "jobId": self.job_id,
                "claimText": "Test quantitative claim.",
                "metrics": "Some metrics",
                "evidence": "Some evidence",
                "source": "agent",
                "replicated": False
            }
        ]
        (sciloom_dir / "CLAIMS.json").write_text(json.dumps(claims_json), encoding="utf-8")
        
        # Create DB record
        with SessionLocal() as db:
            job = models.Job(
                id=self.job_id,
                title="TDD Claim Replication Test",
                pdf_path=f"jobs/{self.job_id}/paper.pdf",
                repo_source="zip",
                data_source="in_repo",
                status="CODE_EXECUTION",
                current_stage="CLAIM_REPLICATION",
                sandbox_id="sbx-test-job-claim-rep"
            )
            db.add(job)
            
            stage_names = ["PROVISIONING", "CLAIM_EXTRACTION", "CODE_EXECUTION", "CLAIM_REPLICATION", "DTREG_GENERATION"]
            for name in stage_names:
                stage = models.Stage(
                    job_id=self.job_id,
                    stage_name=name,
                    status="completed" if name in ["PROVISIONING", "CLAIM_EXTRACTION", "CODE_EXECUTION"] else "pending"
                )
                db.add(stage)
            db.commit()
            
        yield
        
        # Clean up files
        if self.job_dir.exists():
            shutil.rmtree(self.job_dir, ignore_errors=True)

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.copy_to_sandbox")
    @patch("sciloom_pipeline.services.agent_service.agent_service.run_code_execution_agent")
    @patch("sciloom_pipeline.services.agent_service.agent_service.run_claim_replication_agent")
    async def test_run_claim_replication_success_flow(self, mock_rep_agent, mock_exec_agent, mock_copy):
        """Positive Case: Verify that claim replication succeeds when both agents complete successfully."""
        mock_copy.return_value = None
        mock_exec_agent.return_value = {
            "success": True,
            "session_id": "mock_exec_sess",
            "error_details": None
        }
        mock_rep_agent.return_value = {
            "success": True,
            "session_id": "mock_rep_sess",
            "error_details": None
        }

        # Run Stage 4
        await job_service.run_claim_replication(self.job_id)

        # Check job and stage in database
        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            assert job.status == "CLAIM_REPLICATION"
            assert job.opencode_session_id == "mock_rep_sess"

            stage = db.query(models.Stage).filter(
                models.Stage.job_id == self.job_id,
                models.Stage.stage_name == "CLAIM_REPLICATION"
            ).first()
            assert stage.status == "completed"
            
            output = json.loads(stage.output_json)
            assert output["status"] == "success"
            assert output["sandboxId"] == "sbx-test-job-claim-rep"
            assert output["opencodeSessionId"] == "mock_rep_sess"

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.copy_to_sandbox")
    @patch("sciloom_pipeline.services.agent_service.agent_service.run_code_execution_agent")
    async def test_run_claim_replication_code_execution_fails(self, mock_exec_agent, mock_copy):
        """Negative Case: Code execution agent fails to set up environment."""
        mock_copy.return_value = None
        mock_exec_agent.return_value = {
            "success": False,
            "session_id": "mock_exec_sess_failed",
            "error_details": "Failed to install dependencies"
        }

        with pytest.raises(RuntimeError) as exc:
            await job_service.run_claim_replication(self.job_id)

        assert "Environment configuration failed" in str(exc.value)

        # Verify Stage is failed and job status is FAILED
        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            assert job.status == "FAILED"

            stage = db.query(models.Stage).filter(
                models.Stage.job_id == self.job_id,
                models.Stage.stage_name == "CLAIM_REPLICATION"
            ).first()
            assert stage.status == "failed"
            assert "Environment configuration failed" in stage.error_log
            
            sandbox_info = json.loads(stage.sandbox_info)
            assert sandbox_info["sandboxId"] == "sbx-test-job-claim-rep"

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.copy_to_sandbox")
    @patch("sciloom_pipeline.services.agent_service.agent_service.run_code_execution_agent")
    @patch("sciloom_pipeline.services.agent_service.agent_service.run_claim_replication_agent")
    async def test_run_claim_replication_agent_fails(self, mock_rep_agent, mock_exec_agent, mock_copy):
        """Negative Case: Environment sets up fine but replication agent fails validation/script execution."""
        mock_copy.return_value = None
        mock_exec_agent.return_value = {
            "success": True,
            "session_id": "mock_exec_sess",
            "error_details": None
        }
        mock_rep_agent.return_value = {
            "success": False,
            "session_id": "mock_rep_sess_failed",
            "error_details": "CLAIM-001 failed: metrics mismatch"
        }

        with pytest.raises(RuntimeError) as exc:
            await job_service.run_claim_replication(self.job_id)

        assert "CLAIM-001 failed: metrics mismatch" in str(exc.value)

        # Verify Stage is failed and job status is FAILED
        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            assert job.status == "FAILED"

            stage = db.query(models.Stage).filter(
                models.Stage.job_id == self.job_id,
                models.Stage.stage_name == "CLAIM_REPLICATION"
            ).first()
            assert stage.status == "failed"
            assert "CLAIM-001 failed: metrics mismatch" in stage.error_log

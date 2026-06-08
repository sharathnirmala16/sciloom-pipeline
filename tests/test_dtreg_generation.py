import json
import shutil
import pytest
from unittest.mock import patch, AsyncMock
from sciloom_pipeline.services.job_service import job_service
from sciloom_pipeline.config import settings
from sciloom_pipeline.db import models
from sciloom_pipeline.db.database import SessionLocal

@pytest.mark.asyncio
class TestDtregGeneration:
    
    @pytest.fixture(autouse=True)
    def setup_job(self):
        """Sets up a test job record in the database and a temporary directory."""
        self.job_id = "test_job_dtreg_gen"
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
                "replicated": True
            }
        ]
        (sciloom_dir / "CLAIMS.json").write_text(json.dumps(claims_json), encoding="utf-8")
        
        # Create DB record
        with SessionLocal() as db:
            job = models.Job(
                id=self.job_id,
                title="TDD DTREG Generation Test",
                pdf_path=f"jobs/{self.job_id}/paper.pdf",
                repo_source="zip",
                data_source="in_repo",
                status="CLAIM_REPLICATION",
                current_stage="DTREG_GENERATION",
                sandbox_id="sbx-test-job-dtreg-gen"
            )
            db.add(job)
            
            stage_names = ["PROVISIONING", "CLAIM_EXTRACTION", "CODE_EXECUTION", "CLAIM_REPLICATION", "DTREG_GENERATION"]
            for name in stage_names:
                stage = models.Stage(
                    job_id=self.job_id,
                    stage_name=name,
                    status="completed" if name != "DTREG_GENERATION" else "pending"
                )
                db.add(stage)
            db.commit()
            
        yield
        
        # Clean up files
        if self.job_dir.exists():
            shutil.rmtree(self.job_dir, ignore_errors=True)

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.get_sandbox_status")
    @patch("sciloom_pipeline.services.job_service.job_service.sync_sandbox_to_host")
    @patch("sciloom_pipeline.services.job_service.job_service.sync_host_to_sandbox")
    @patch("sciloom_pipeline.services.agent_service.agent_service.run_dtreg_generation_agent")
    async def test_run_dtreg_generation_success_flow(
        self, mock_dtreg_agent, mock_sync_in, mock_sync_out, mock_status
    ):
        """Positive Case: Verify that DTREG generation succeeds when active sandbox exists and agent runs successfully."""
        mock_status.return_value = {"name": "sbx-test-job-dtreg-gen"}
        mock_sync_out.return_value = None
        mock_sync_in.return_value = None
        mock_dtreg_agent.return_value = {
            "success": True,
            "session_id": "mock_dtreg_sess",
            "error_details": None
        }

        # Run Stage 5
        await job_service.run_dtreg_generation(self.job_id)

        # Check job and stage in database
        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            assert job.status == "DTREG_GENERATION"
            assert job.opencode_session_id == "mock_dtreg_sess"

            stage = db.query(models.Stage).filter(
                models.Stage.job_id == self.job_id,
                models.Stage.stage_name == "DTREG_GENERATION"
            ).first()
            assert stage.status == "completed"
            
            output = json.loads(stage.output_json)
            assert output["status"] == "success"
            assert output["sandboxId"] == "sbx-test-job-dtreg-gen"
            assert output["opencodeSessionId"] == "mock_dtreg_sess"

            # Check that sync methods were called
            mock_sync_out.assert_called_with(self.job_id, "sbx-test-job-dtreg-gen")
            mock_sync_in.assert_called_once_with(self.job_id, "sbx-test-job-dtreg-gen")

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.get_sandbox_status")
    @patch("sciloom_pipeline.services.job_service.job_service.sync_sandbox_to_host")
    @patch("sciloom_pipeline.services.job_service.job_service.sync_host_to_sandbox")
    @patch("sciloom_pipeline.services.agent_service.agent_service.run_dtreg_generation_agent")
    async def test_run_dtreg_generation_agent_fails(
        self, mock_dtreg_agent, mock_sync_in, mock_sync_out, mock_status
    ):
        """Negative Case: Agent fails to compile or generate json-ld."""
        mock_status.return_value = {"name": "sbx-test-job-dtreg-gen"}
        mock_sync_out.return_value = None
        mock_sync_in.return_value = None
        mock_dtreg_agent.return_value = {
            "success": False,
            "session_id": "mock_dtreg_sess_failed",
            "error_details": "SyntaxError in generate_dtreg.py"
        }

        with pytest.raises(RuntimeError) as exc:
            await job_service.run_dtreg_generation(self.job_id)

        assert "SyntaxError in generate_dtreg.py" in str(exc.value)

        # Verify Stage is failed and job status is FAILED
        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            assert job.status == "FAILED"

            stage = db.query(models.Stage).filter(
                models.Stage.job_id == self.job_id,
                models.Stage.stage_name == "DTREG_GENERATION"
            ).first()
            assert stage.status == "failed"
            assert "SyntaxError in generate_dtreg.py" in stage.error_log

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.get_sandbox_status")
    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.create_sandbox")
    @patch("sciloom_pipeline.services.job_service.job_service.sync_sandbox_to_host")
    @patch("sciloom_pipeline.services.job_service.job_service.sync_host_to_sandbox")
    @patch("sciloom_pipeline.services.agent_service.agent_service.run_dtreg_generation_agent")
    async def test_run_dtreg_generation_recreates_sandbox(
        self, mock_dtreg_agent, mock_sync_in, mock_sync_out, mock_create, mock_status
    ):
        """Positive Case: Verify that sandbox is recreated if not active/running when Stage 5 starts."""
        mock_status.return_value = None  # Sandbox is NOT active
        mock_create.return_value = "sbx-test-job-dtreg-gen-new"
        mock_sync_out.return_value = None
        mock_sync_in.return_value = None
        mock_dtreg_agent.return_value = {
            "success": True,
            "session_id": "mock_dtreg_sess_new",
            "error_details": None
        }

        # Run Stage 5
        await job_service.run_dtreg_generation(self.job_id)

        # Verify new sandbox created and stage completed
        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            assert job.sandbox_id == "sbx-test-job-dtreg-gen-new"

            stage = db.query(models.Stage).filter(
                models.Stage.job_id == self.job_id,
                models.Stage.stage_name == "DTREG_GENERATION"
            ).first()
            assert stage.status == "completed"

            # sync_sandbox_to_host is called at the end (with the new sandbox name)
            # but NOT at the beginning since sandbox was not active
            mock_sync_out.assert_called_once_with(self.job_id, "sbx-test-job-dtreg-gen-new")
            mock_sync_in.assert_called_once_with(self.job_id, "sbx-test-job-dtreg-gen-new")

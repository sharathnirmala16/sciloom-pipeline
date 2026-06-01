import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from sciloom_pipeline.services.job_service import job_service
from sciloom_pipeline.config import settings
from sciloom_pipeline.db import models
from sciloom_pipeline.db.database import SessionLocal

@pytest.mark.asyncio
class TestCodeExecution:
    
    @pytest.fixture(autouse=True)
    def setup_job(self):
        """Sets up a test job record in the database and a temporary directory."""
        self.job_id = "test_job_code_exec"
        self.job_dir = settings.jobs_dir / f"job_{self.job_id}"
        self.job_dir.mkdir(parents=True, exist_ok=True)
        
        # Create REPO folder
        (self.job_dir / "REPO").mkdir(parents=True, exist_ok=True)
        
        # Create DB record
        with SessionLocal() as db:
            job = models.Job(
                id=self.job_id,
                title="TDD Code Exec Test",
                pdf_path=f"jobs/{self.job_id}/paper.pdf",
                repo_source="zip",
                data_source="in_repo",
                status="PROVISIONED",
                current_stage="CODE_EXECUTION"
            )
            db.add(job)
            
            stage_names = ["PROVISIONING", "CLAIM_EXTRACTION", "CODE_EXECUTION", "CLAIM_REPLICATION", "DTREG_GENERATION"]
            for name in stage_names:
                stage = models.Stage(
                    job_id=self.job_id,
                    stage_name=name,
                    status="completed" if name in ["PROVISIONING", "CLAIM_EXTRACTION"] else "pending"
                )
                db.add(stage)
            db.commit()
            
        yield
        
        # Clean up files
        if self.job_dir.exists():
            import shutil
            shutil.rmtree(self.job_dir, ignore_errors=True)

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.create_sandbox")
    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.copy_to_sandbox")
    @patch("sciloom_pipeline.services.agent_service.agent_service.run_code_execution_agent")
    async def test_run_code_execution_success_flow(self, mock_agent, mock_copy, mock_create):
        """Positive Case: Verify sandbox creation and code execution agent run successfully."""
        mock_create.return_value = "sbx-test_job_code_exec"
        mock_copy.return_value = None
        mock_agent.return_value = {
            "success": True,
            "session_id": "mock_session_123",
            "error_details": None
        }

        # Run Stage 3
        await job_service.run_code_execution(self.job_id)

        # Check job in database
        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            assert job.status == "CODE_EXECUTION"
            assert job.sandbox_id == "sbx-test_job_code_exec"
            assert job.opencode_session_id == "mock_session_123"
            assert job.opencode_server_url == settings.opencode_server_url

            stage = db.query(models.Stage).filter(
                models.Stage.job_id == self.job_id,
                models.Stage.stage_name == "CODE_EXECUTION"
            ).first()
            assert stage.status == "completed"
            
            output = json.loads(stage.output_json)
            assert output["status"] == "success"
            assert output["sandboxId"] == "sbx-test_job_code_exec"
            assert output["opencodeSessionId"] == "mock_session_123"

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.create_sandbox")
    async def test_run_code_execution_sandbox_creation_fails(self, mock_create):
        """Negative Case: Sandbox creation raises an error."""
        mock_create.side_effect = RuntimeError("Docker daemon not running")

        with pytest.raises(RuntimeError) as exc:
            await job_service.run_code_execution(self.job_id)

        assert "Docker daemon not running" in str(exc.value)

        # Check stage is failed and database has logs
        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            assert job.status == "FAILED"

            stage = db.query(models.Stage).filter(
                models.Stage.job_id == self.job_id,
                models.Stage.stage_name == "CODE_EXECUTION"
            ).first()
            assert stage.status == "failed"
            assert "Docker daemon not running" in stage.error_log
            
            sandbox_info = json.loads(stage.sandbox_info)
            assert sandbox_info["sandboxId"] == "sbx-test_job_code_exec"

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.create_sandbox")
    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.copy_to_sandbox")
    @patch("sciloom_pipeline.services.agent_service.agent_service.run_code_execution_agent")
    async def test_run_code_execution_agent_fails_marks_stage_failed(self, mock_agent, mock_copy, mock_create):
        """Negative Case: Sandbox creates successfully but Agent fails execution."""
        mock_create.return_value = "sbx-test_job_code_exec"
        mock_copy.return_value = None
        mock_agent.return_value = {
            "success": False,
            "session_id": "mock_session_failed",
            "error_details": "Failed to install package 'numpy'"
        }

        with pytest.raises(RuntimeError) as exc:
            await job_service.run_code_execution(self.job_id)

        assert "Failed to install package 'numpy'" in str(exc.value)

        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            assert job.status == "FAILED"
            assert job.sandbox_id == "sbx-test_job_code_exec" # Sandbox persists!
            assert job.opencode_session_id == "mock_session_failed"

            stage = db.query(models.Stage).filter(
                models.Stage.job_id == self.job_id,
                models.Stage.stage_name == "CODE_EXECUTION"
            ).first()
            assert stage.status == "failed"
            assert "Failed to install package 'numpy'" in stage.error_log
            
            sandbox_info = json.loads(stage.sandbox_info)
            assert sandbox_info["sandboxId"] == "sbx-test_job_code_exec"
            assert "sbx exec" in sandbox_info["connectionCommand"]

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.remove_sandbox")
    async def test_delete_sandbox_success(self, mock_remove):
        """Verify that delete_sandbox calls sandbox_service.remove_sandbox and clears Job fields."""
        mock_remove.return_value = None

        # Pre-set sandbox fields on job
        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            job.sandbox_id = "sbx-test_job_code_exec"
            job.opencode_session_id = "mock_session_123"
            job.opencode_server_url = "http://localhost:4096"
            db.commit()

        await job_service.delete_sandbox(self.job_id)

        mock_remove.assert_called_once_with("sbx-test_job_code_exec")

        # Verify cleared in database
        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            assert job.sandbox_id is None
            assert job.opencode_session_id is None
            assert job.opencode_server_url is None

    @patch("sciloom_pipeline.services.sandbox_service.sandbox_service.get_sandbox_status")
    async def test_get_sandbox_info_endpoint(self, mock_status):
        """Verify get_sandbox_info gathers correct status and connection details."""
        mock_status.return_value = {"name": "sbx-test_job_code_exec"}

        with SessionLocal() as db:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            job.sandbox_id = "sbx-test_job_code_exec"
            job.opencode_session_id = "mock_session_123"
            job.opencode_server_url = "http://localhost:4096"
            db.commit()

        info = await job_service.get_sandbox_info(self.job_id)
        
        assert info["sandboxId"] == "sbx-test_job_code_exec"
        assert info["status"] == "running"
        assert "sbx exec sbx-test_job_code_exec" in info["connectionCommand"]
        assert info["opencodeSessionId"] == "mock_session_123"
        assert info["opencodeServerUrl"] == "http://localhost:4096"

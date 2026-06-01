import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from sciloom_pipeline.services.sandbox_service import sandbox_service
from sciloom_pipeline.config import settings

@pytest.mark.asyncio
class TestSandboxService:
    @patch("asyncio.create_subprocess_exec")
    async def test_create_sandbox_success(self, mock_exec):
        # Mock process
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Created", b""))
        mock_exec.return_value = mock_process

        repo_path = Path("/tmp/mock-repo")
        sandbox_name = await sandbox_service.create_sandbox("job123", repo_path)
        
        assert sandbox_name == "sbx-job123"
        mock_exec.assert_called_once_with(
            "sbx",
            "create",
            "opencode",
            str(repo_path),
            "--name",
            "sbx-job123",
            "--memory",
            settings.sandbox_memory_limit,
            stdout=-1,
            stderr=-1
        )

    @patch("asyncio.create_subprocess_exec")
    async def test_create_sandbox_failure(self, mock_exec):
        # Mock process to fail
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Docker error"))
        mock_exec.return_value = mock_process

        with pytest.raises(RuntimeError) as exc:
            await sandbox_service.create_sandbox("job123", Path("/tmp/mock-repo"))
            
        assert "Docker error" in str(exc.value)

    @patch("asyncio.create_subprocess_exec")
    async def test_copy_to_sandbox_success(self, mock_exec):
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_exec.return_value = mock_process

        src = Path("/tmp/paper.md")
        await sandbox_service.copy_to_sandbox("sbx-job123", src, "/app/paper.md")

        mock_exec.assert_called_once_with(
            "sbx",
            "cp",
            str(src),
            "sbx-job123:/app/paper.md",
            stdout=-1,
            stderr=-1
        )

    @patch("asyncio.create_subprocess_exec")
    async def test_copy_from_sandbox_success(self, mock_exec):
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_exec.return_value = mock_process

        dst = Path("/tmp/output")
        await sandbox_service.copy_from_sandbox("sbx-job123", "/app/output", dst)

        mock_exec.assert_called_once_with(
            "sbx",
            "cp",
            "sbx-job123:/app/output",
            str(dst),
            stdout=-1,
            stderr=-1
        )

    @patch("asyncio.create_subprocess_exec")
    async def test_exec_in_sandbox_success(self, mock_exec):
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"hello", b""))
        mock_exec.return_value = mock_process

        out = await sandbox_service.exec_in_sandbox("sbx-job123", ["echo", "hello"])
        
        assert out == "hello"
        mock_exec.assert_called_once_with(
            "sbx",
            "exec",
            "sbx-job123",
            "--",
            "echo",
            "hello",
            stdout=-1,
            stderr=-1
        )

    @patch("asyncio.create_subprocess_exec")
    async def test_get_sandbox_status_running(self, mock_exec):
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(
            b'{"sandboxes": [{"name": "sbx-job123", "workspaces": ["/path"]}]}', b""
        ))
        mock_exec.return_value = mock_process

        status = await sandbox_service.get_sandbox_status("sbx-job123")
        assert status is not None
        assert status["name"] == "sbx-job123"

    @patch("asyncio.create_subprocess_exec")
    async def test_get_sandbox_status_not_found(self, mock_exec):
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'{"sandboxes": []}', b""))
        mock_exec.return_value = mock_process

        status = await sandbox_service.get_sandbox_status("sbx-job123")
        assert status is None

    @patch("asyncio.create_subprocess_exec")
    async def test_remove_sandbox_success(self, mock_exec):
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_exec.return_value = mock_process

        await sandbox_service.remove_sandbox("sbx-job123")
        mock_exec.assert_called_once_with(
            "sbx",
            "rm",
            "sbx-job123",
            "--force",
            stdout=-1,
            stderr=-1
        )

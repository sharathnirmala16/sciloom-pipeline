import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Any
from sciloom_pipeline.config import settings

logger = logging.getLogger("sciloom.sandbox")

class SandboxService:
    async def create_sandbox(self, job_id: str, repo_path: Path) -> str:
        """
        Creates a Docker sandbox for the job via:
        sbx create opencode <repo_path> --name sbx-<job_id> [--cpus <cpus>] [--memory <memory>]
        Returns the sandbox name.
        """
        sandbox_name = f"sbx-{job_id}"
        
        cmd = [
            "sbx",
            "create",
            "opencode",
            str(repo_path),
            "--name",
            sandbox_name
        ]
        
        if settings.sandbox_memory_limit:
            cmd.extend(["--memory", settings.sandbox_memory_limit])
            
        if settings.sandbox_cpus > 0:
            cmd.extend(["--cpus", str(settings.sandbox_cpus)])
            
        logger.info(f"Creating sandbox {sandbox_name} with command: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error(f"Failed to create sandbox {sandbox_name}: {err_msg}")
            raise RuntimeError(f"Failed to create sandbox: {err_msg}")
            
        logger.info(f"Successfully created sandbox {sandbox_name}")
        return sandbox_name

    async def copy_to_sandbox(self, sandbox_name: str, src: Path, dst: str) -> None:
        """
        Copies a file or folder from the host into the sandbox:
        sbx cp <src> <sandbox_name>:<dst>
        """
        cmd = [
            "sbx",
            "cp",
            str(src),
            f"{sandbox_name}:{dst}"
        ]
        logger.info(f"Copying {src} to sandbox {sandbox_name}:{dst}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error(f"Failed to copy to sandbox {sandbox_name}: {err_msg}")
            raise RuntimeError(f"Failed to copy to sandbox: {err_msg}")

    async def copy_from_sandbox(self, sandbox_name: str, src: str, dst: Path) -> None:
        """
        Copies a file or folder from the sandbox to the host:
        sbx cp <sandbox_name>:<src> <dst>
        """
        cmd = [
            "sbx",
            "cp",
            f"{sandbox_name}:{src}",
            str(dst)
        ]
        logger.info(f"Copying from sandbox {sandbox_name}:{src} to host {dst}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error(f"Failed to copy from sandbox {sandbox_name}: {err_msg}")
            raise RuntimeError(f"Failed to copy from sandbox: {err_msg}")

    async def exec_in_sandbox(self, sandbox_name: str, command: list[str]) -> str:
        """
        Executes a command inside the sandbox:
        sbx exec <sandbox_name> -- <command_list>
        """
        cmd = [
            "sbx",
            "exec",
            sandbox_name,
            "--"
        ] + command
        
        logger.info(f"Executing in sandbox {sandbox_name}: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error(f"Command execution failed in sandbox {sandbox_name}: {err_msg}")
            raise RuntimeError(f"Command execution failed: {err_msg}")
            
        return stdout.decode(errors="replace").strip()

    async def get_sandbox_status(self, sandbox_name: str) -> Optional[dict[str, Any]]:
        """
        Retrieves sandbox status by parsing sbx ls --json.
        Returns the dictionary with sandbox metadata if found, else None.
        """
        cmd = ["sbx", "ls", "--json"]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Failed to list sandboxes: {stderr.decode(errors='replace')}")
                return None
                
            data = json.loads(stdout.decode(errors="replace"))
            sandboxes = data.get("sandboxes", [])
            for sbx in sandboxes:
                if sbx.get("name") == sandbox_name:
                    return sbx
            return None
        except Exception as e:
            logger.exception(f"Error checking sandbox status for {sandbox_name}")
            return None

    async def stop_sandbox(self, sandbox_name: str) -> None:
        """
        Stops a sandbox:
        sbx stop <sandbox_name>
        """
        cmd = ["sbx", "stop", sandbox_name]
        logger.info(f"Stopping sandbox {sandbox_name}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error(f"Failed to stop sandbox {sandbox_name}: {err_msg}")
            raise RuntimeError(f"Failed to stop sandbox: {err_msg}")

    async def remove_sandbox(self, sandbox_name: str) -> None:
        """
        Removes a sandbox (force-deletes):
        sbx rm <sandbox_name> --force
        """
        cmd = ["sbx", "rm", sandbox_name, "--force"]
        logger.info(f"Removing sandbox {sandbox_name}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error(f"Failed to remove sandbox {sandbox_name}: {err_msg}")
            raise RuntimeError(f"Failed to remove sandbox: {err_msg}")

sandbox_service = SandboxService()

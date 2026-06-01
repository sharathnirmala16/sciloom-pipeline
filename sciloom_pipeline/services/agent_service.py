import asyncio
import logging
from pathlib import Path

logger = logging.getLogger("sciloom.agent")

class AgentService:
    async def extract_claims(self, job_id: str, job_dir: Path, log_callback) -> None:
        """
        Runs the OpenCode claim-extraction-agent in a subprocess.
        Streams stdout and stderr via log_callback.
        """
        # Execute the agent command: opencode run --agent claim-extraction-agent "Extract the quantitative claims from this paper." -f RESEARCH_PAPER.md
        # Run in job_dir where RESEARCH_PAPER.md resides
        cmd = [
            "opencode",
            "run",
            "--agent",
            "claim-extraction-agent",
            "Extract the quantitative claims from this paper.",
            "-f",
            "RESEARCH_PAPER.md"
        ]
        
        await log_callback(f"Executing command: {' '.join(cmd)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(job_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            async def stream_output(stream, is_stderr: bool):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode(errors="replace").strip()
                    if decoded:
                        level = "ERROR" if is_stderr else "INFO"
                        await log_callback(decoded, level)
            
            # Read stdout and stderr concurrently
            await asyncio.gather(
                stream_output(process.stdout, False),
                stream_output(process.stderr, True)
            )
            
            returncode = await process.wait()
            if returncode != 0:
                raise RuntimeError(f"opencode process exited with return code {returncode}")
                
        except Exception as e:
            logger.exception(f"Failed to run claim extraction agent for job {job_id}")
            raise e

agent_service = AgentService()

import asyncio
import json
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
        paper_path = job_dir / "RESEARCH_PAPER.md"
        cmd = [
            "opencode",
            "run",
            "--agent",
            "claim-extraction-agent",
            "Extract the quantitative claims from this paper.",
            "-f",
            str(paper_path)
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

    async def run_code_execution_agent(
        self,
        job_id: str,
        sandbox_name: str,
        log_callback
    ) -> dict:
        """
        Runs the OpenCode agent 'code-execution-agent' inside the sandbox.
        Streams the agent's work in real-time.
        Returns a dict: {"success": bool, "session_id": Optional[str], "error_details": Optional[str]}
        """
        cmd = [
            "sbx",
            "run",
            sandbox_name,
            "--",
            "--agent",
            "code-execution-agent",
            "--format",
            "json",
            "Get this repository running by configuring the environment, installing dependencies with uv, and verifying the entry point."
        ]
        
        await log_callback(f"Executing sandbox agent command: {' '.join(cmd)}")
        
        session_id = None
        success = False
        error_details = None
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            async def stream_output():
                nonlocal session_id, success, error_details
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode(errors="replace").strip()
                    if not decoded:
                        continue
                    
                    try:
                        event_data = json.loads(decoded)
                        
                        if "session_id" in event_data:
                            session_id = event_data["session_id"]
                        elif "sessionId" in event_data:
                            session_id = event_data["sessionId"]
                            
                        event_type = event_data.get("event")
                        
                        if event_type == "thought":
                            thought = event_data.get("thought", "")
                            if thought:
                                await log_callback(f"[Thinking] {thought}")
                        elif event_type == "chunk":
                            chunk = event_data.get("chunk", "")
                            if chunk:
                                await log_callback(chunk)
                        elif event_type == "text":
                            text = event_data.get("text", "")
                            if text:
                                await log_callback(text)
                        elif event_type == "tool_call":
                            tool = event_data.get("tool", "")
                            args = event_data.get("arguments", "")
                            await log_callback(f"[Running Tool: {tool} with args: {args}]")
                        elif event_type == "tool_output":
                            output = event_data.get("output", "")
                            output_str = str(output)[:200] + "..." if len(str(output)) > 200 else str(output)
                            await log_callback(f"[Tool Output: {output_str}]")
                        elif event_type == "done":
                            await log_callback("[Agent Finished]")
                        else:
                            msg = event_data.get("content") or event_data.get("message")
                            if msg:
                                await log_callback(str(msg))
                            else:
                                await log_callback(f"[{event_type or 'Event'}]")
                                
                    except json.JSONDecodeError:
                        await log_callback(decoded)
                        
            async def stream_errors():
                nonlocal error_details
                err_lines = []
                while True:
                    line = await process.stderr.readline()
                    if not line:
                        break
                    decoded = line.decode(errors="replace").strip()
                    if decoded:
                        err_lines.append(decoded)
                        await log_callback(decoded, "ERROR")
                if err_lines:
                    error_details = "\n".join(err_lines)
            
            await asyncio.gather(
                stream_output(),
                stream_errors()
            )
            
            returncode = await process.wait()
            if returncode == 0:
                success = True
            else:
                success = False
                if not error_details:
                    error_details = f"sbx run process exited with code {returncode}"
                    
        except Exception as e:
            logger.exception(f"Failed to run code execution agent in sandbox {sandbox_name}")
            success = False
            error_details = str(e)
            
        return {
            "success": success,
            "session_id": session_id,
            "error_details": error_details
        }

agent_service = AgentService()


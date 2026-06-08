import asyncio
import json
import logging
import os
from pathlib import Path

from sciloom_pipeline.config import settings

logger = logging.getLogger("sciloom.agent")

class AgentService:
    async def extract_claims(self, job_id: str, job_dir: Path, paper_path: Path, log_callback) -> None:
        """
        Runs the OpenCode claim-extraction-agent in a subprocess.
        Streams stdout and stderr via log_callback.
        """
        cmd = [
            "opencode",
            "run",
            "--dir",
            str(job_dir),
            "--agent",
            "claim-extraction-agent",
            "Extract the quantitative claims from this paper.",
            "-f",
            str(paper_path)
        ]
        
        await log_callback(f"Executing command: {' '.join(cmd)}")
        
        custom_env = os.environ.copy()
        if settings.gemini_api_key:
            custom_env["GOOGLE_API_KEY"] = settings.gemini_api_key
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(job_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=custom_env
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
            "run",
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
        
        custom_env = os.environ.copy()
        if settings.gemini_api_key:
            custom_env["GOOGLE_API_KEY"] = settings.gemini_api_key
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=custom_env
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

    async def run_claim_replication_agent(
        self,
        job_id: str,
        sandbox_name: str,
        log_callback
    ) -> dict:
        """
        Runs the OpenCode agent 'claim-replication-agent' inside the sandbox.
        Streams the agent's work in real-time.
        Returns a dict: {"success": bool, "session_id": Optional[str], "error_details": Optional[str]}
        """
        cmd = [
            "sbx",
            "run",
            sandbox_name,
            "--",
            "run",
            "--agent",
            "claim-replication-agent",
            "--format",
            "json",
            "Validate and mathematically replicate the quantitative claims from .sciloom/CLAIMS.json. "
            "For each claim, write an independent Python replication script in .sciloom/scripts/ (e.g., replicate_CLAIM_001.py), "
            "run it in the virtual environment, verify the computed metrics against the claim, and update the claim's "
            "'replicated' status (and 'replicationError' if failed) in .sciloom/CLAIMS.json. "
            "If any claim fails to replicate, the run should be marked as failed or you should raise an error."
        ]

        await log_callback(f"Executing sandbox agent command: {' '.join(cmd)}")
        
        session_id = None
        success = False
        error_details = None
        
        custom_env = os.environ.copy()
        if settings.gemini_api_key:
            custom_env["GOOGLE_API_KEY"] = settings.gemini_api_key
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=custom_env
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
            logger.exception(f"Failed to run claim replication agent in sandbox {sandbox_name}")
            success = False
            error_details = str(e)
            
        return {
            "success": success,
            "session_id": session_id,
            "error_details": error_details
        }

    async def run_dtreg_generation_agent(
        self,
        job_id: str,
        sandbox_name: str,
        log_callback
    ) -> dict:
        """
        Runs the OpenCode agent 'dtreg-generation-agent' inside the sandbox.
        Streams the agent's work in real-time.
        Returns a dict: {"success": bool, "session_id": Optional[str], "error_details": Optional[str]}
        """
        cmd = [
            "sbx",
            "run",
            sandbox_name,
            "--",
            "run",
            "--agent",
            "dtreg-generation-agent",
            "--format",
            "json",
            "Generate the TIB Knowledge Loom DTREG metadata json-ld for this scientific workflow. "
            "Use the 'dtreg' library to construct the json-ld based on the replicated claims in .sciloom/CLAIMS.json, "
            "the research paper .sciloom/RESEARCH_PAPER.md, the replication scripts in .sciloom/scripts/, "
            "and the provided dtreg skills and examples inside .sciloom/dtreg_skills/ and .sciloom/dtreg_examples/. "
            "Write the resulting dtreg serialization python script to .sciloom/scripts/generate_dtreg.py, "
            "execute it to produce the json-ld, and write the final output to .sciloom/dtreg_output.jsonld."
        ]

        await log_callback(f"Executing sandbox agent command: {' '.join(cmd)}")
        
        session_id = None
        success = False
        error_details = None
        
        custom_env = os.environ.copy()
        if settings.gemini_api_key:
            custom_env["GOOGLE_API_KEY"] = settings.gemini_api_key
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=custom_env
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
            logger.exception(f"Failed to run dtreg generation agent in sandbox {sandbox_name}")
            success = False
            error_details = str(e)
            
        return {
            "success": success,
            "session_id": session_id,
            "error_details": error_details
        }

agent_service = AgentService()


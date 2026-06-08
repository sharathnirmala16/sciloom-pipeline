import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from sciloom_pipeline.config import settings

logger = logging.getLogger("sciloom.log_service")

# Maps stage names to their log file names
STAGE_LOG_FILES = {
    "PROVISIONING": "provisioning.log",
    "CLAIM_EXTRACTION": "claim_extraction.log",
    "CODE_EXECUTION": "code_execution.log",
    "CLAIM_REPLICATION": "claim_replication.log",
    "DTREG_GENERATION": "dtreg_generation.log",
}


class LogService:
    """File-based logging service that writes per-stage log files and broadcasts via SSE."""

    def get_sciloom_dir(self, job_id: str) -> Path:
        """Returns the .sciloom directory for a job, inside REPO."""
        return settings.jobs_dir / job_id / "REPO" / ".sciloom"

    def _get_log_path(self, job_id: str, stage_name: str) -> Path:
        """Returns the log file path for a specific stage."""
        log_filename = STAGE_LOG_FILES.get(stage_name)
        if not log_filename:
            log_filename = f"{stage_name.lower()}.log"
        return self.get_sciloom_dir(job_id) / log_filename

    async def add_log(
        self, job_id: str, stage_name: str, level: str, message: str
    ) -> None:
        """Appends a log line to the stage log file and broadcasts via SSE."""
        timestamp = datetime.now().strftime("%I:%M:%S %p")
        log_line = f"[{timestamp}] [{level}] {message}\n"

        log_path = self._get_log_path(job_id, stage_name)

        def _write():
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_line)

        await asyncio.to_thread(_write)

        # Broadcast via queue service SSE notifications
        from sciloom_pipeline.services.queue_service import queue_service

        await queue_service.broadcast_log(job_id, level, message, timestamp)

    async def get_logs_for_stage(
        self, job_id: str, stage_name: str
    ) -> List[Dict[str, Any]]:
        """Reads and parses all log entries from a stage log file."""
        log_path = self._get_log_path(job_id, stage_name)
        if not log_path.is_file():
            return []

        def _read():
            return log_path.read_text(encoding="utf-8")

        content = await asyncio.to_thread(_read)
        return self._parse_log_content(content)

    async def get_all_logs(self, job_id: str) -> List[Dict[str, Any]]:
        """Reads and returns all log entries across all stages, in stage order."""
        all_logs: List[Dict[str, Any]] = []
        for stage_name in STAGE_LOG_FILES:
            stage_logs = await self.get_logs_for_stage(job_id, stage_name)
            all_logs.extend(stage_logs)
        return all_logs

    def _parse_log_content(self, content: str) -> List[Dict[str, Any]]:
        """Parses raw log file content into structured log entries."""
        logs = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            # Expected format: [HH:MM:SS AM] [LEVEL] message
            try:
                # Extract timestamp between first pair of brackets
                ts_start = line.index("[") + 1
                ts_end = line.index("]", ts_start)
                timestamp = line[ts_start:ts_end]

                # Extract level between second pair of brackets
                lvl_start = line.index("[", ts_end) + 1
                lvl_end = line.index("]", lvl_start)
                level = line[lvl_start:lvl_end]

                # Everything after the second closing bracket is the message
                message = line[lvl_end + 1 :].strip()

                logs.append(
                    {"timestamp": timestamp, "level": level, "message": message}
                )
            except (ValueError, IndexError):
                # Malformed line — include as-is with INFO level
                logs.append(
                    {"timestamp": "", "level": "INFO", "message": line}
                )
        return logs


log_service = LogService()

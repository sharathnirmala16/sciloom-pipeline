import asyncio
import os
import logging
from typing import Any, Dict
import honker
from sciloom_pipeline.config import settings
from sciloom_pipeline.db.database import SessionLocal

logger = logging.getLogger("sciloom.queue")

# Initialize Honker connection
db = honker.open(str(settings.database_path))
jobs_queue = db.queue("pipeline_jobs")

class QueueService:
    def __init__(self):
        self.db = db
        self.queue = jobs_queue
        self._worker_task = None
        self._log_listeners: Dict[str, set[asyncio.Queue]] = {}

    def register_log_listener(self, job_id: str, queue: asyncio.Queue) -> None:
        """Registers an in-memory queue to receive real-time log updates for a job."""
        if job_id not in self._log_listeners:
            self._log_listeners[job_id] = set()
        self._log_listeners[job_id].add(queue)

    def unregister_log_listener(self, job_id: str, queue: asyncio.Queue) -> None:
        """Unregisters a log stream queue when a client disconnects."""
        if job_id in self._log_listeners:
            self._log_listeners[job_id].discard(queue)
            if not self._log_listeners[job_id]:
                del self._log_listeners[job_id]

    def enqueue_job_task(self, task_type: str, job_id: str, payload: Dict[str, Any] = None) -> int:
        """Enqueues a pipeline stage execution task."""
        task_payload = {
            "type": task_type,
            "job_id": job_id,
            "data": payload or {}
        }
        return self.queue.enqueue(task_payload)

    async def broadcast_log(self, job_id: str, level: str, message: str, timestamp: str) -> None:
        """Broadcasts a log message via in-memory listener queues."""
        payload = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        # Push log updates to all active SSE queues for this job
        queues = self._log_listeners.get(job_id, [])
        for q in list(queues):
            await q.put(payload)

    async def start_worker(self) -> None:
        """Starts the background worker loop to consume jobs."""
        if self._worker_task is not None:
            return
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Background job worker started.")

    async def stop_worker(self) -> None:
        """Stops the background worker loop."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("Background job worker stopped.")

    async def _worker_loop(self) -> None:
        worker_id = f"worker-{os.getpid()}"
        from sciloom_pipeline.services.job_service import job_service
        
        async for job in self.queue.claim(worker_id):
            payload = job.payload
            task_type = payload.get("type")
            job_id = payload.get("job_id")
            logger.info(f"Claimed job {job.id} for job_id={job_id}, task_type={task_type}")

            # Open a thread-safe database session context for worker tasks
            with SessionLocal() as session:
                try:
                    if task_type == "provision":
                        await job_service.run_provisioning(job_id, db=session)
                    elif task_type == "retry_ocr":
                        await job_service.run_ocr_retry(job_id, db=session)
                    elif task_type == "claim_extraction":
                        await job_service.run_claim_extraction(job_id, db=session)
                    elif task_type == "code_execution":
                        await job_service.run_code_execution(job_id, db=session)
                    elif task_type == "claim_replication":
                        await job_service.run_claim_replication(job_id, db=session)
                    elif task_type == "dtreg_generation":
                        await job_service.run_dtreg_generation(job_id, db=session)
                    else:
                        logger.warning(f"Unknown task type: {task_type}")
                    
                    job.ack()
                    logger.info(f"Successfully processed and acked task {job.id}")
                except Exception as e:
                    logger.exception(f"Error processing task {job.id}: {e}")
                    job.fail(error=str(e))
                    try:
                        # Map task_type to corresponding Stage name dynamically
                        stage_map = {
                            "provision": "PROVISIONING",
                            "retry_ocr": "PROVISIONING",
                            "claim_extraction": "CLAIM_EXTRACTION",
                            "code_execution": "CODE_EXECUTION",
                            "claim_replication": "CLAIM_REPLICATION",
                            "dtreg_generation": "DTREG_GENERATION"
                        }
                        failed_stage = stage_map.get(task_type, "PROVISIONING")
                        await job_service.mark_stage_failed(job_id, failed_stage, str(e), db=session)
                    except Exception as inner_e:
                        logger.error(f"Failed to update failed status in DB for {job_id}: {inner_e}")

queue_service = QueueService()

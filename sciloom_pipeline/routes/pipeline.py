import json
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from sciloom_pipeline.services.job_service import job_service
from sciloom_pipeline.services.queue_service import queue_service
from sciloom_pipeline.db.database import get_db
from sciloom_pipeline.db import models
from sciloom_pipeline.schemas.sandbox import SandboxInfoResponse

router = APIRouter(prefix="/jobs/{job_id}", tags=["Pipeline Orchestration"])

# List of stages in order
STAGES_ORDER = ["PROVISIONING", "CLAIM_EXTRACTION", "CODE_EXECUTION", "CLAIM_REPLICATION", "DTREG_GENERATION"]

@router.get("/stages")
async def get_stages(job_id: str, db: Session = Depends(get_db)):
    """Retrieves all pipeline stages for a specific job."""
    job = await job_service.get_job_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return await job_service.get_stages_for_job(job_id, db=db)

@router.post("/advance", status_code=status.HTTP_200_OK)
async def advance_stage(job_id: str, db: Session = Depends(get_db)):
    """Manually advances the pipeline to the next stage."""
    job = await job_service.get_job_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    current_stage = job.get("currentStage")
    if current_stage not in STAGES_ORDER:
        raise HTTPException(status_code=400, detail=f"Invalid current stage: {current_stage}")

    curr_idx = STAGES_ORDER.index(current_stage)
    
    # Check if we can advance (e.g. stage is completed)
    stages = await job_service.get_stages_for_job(job_id, db=db)
    curr_stage_obj = next((s for s in stages if s["stageName"] == current_stage), None)
    
    if not curr_stage_obj:
        raise HTTPException(status_code=500, detail=f"Stage {current_stage} not found in tracking records.")

    # We allow advancing if completed, or manually forcing it if applicable
    if curr_stage_obj["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot advance. Current stage {current_stage} is in status '{curr_stage_obj['status']}'."
        )

    # Determine next stage
    now_str = datetime.now().isoformat()
    
    try:
        # Get Job record
        job_record = db.query(models.Job).filter(models.Job.id == job_id).first()
        if not job_record:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

        if curr_idx + 1 < len(STAGES_ORDER):
            next_stage = STAGES_ORDER[curr_idx + 1]
            
            # Update job record
            job_record.status = next_stage
            job_record.current_stage = next_stage
            job_record.updated_at = datetime.now(timezone.utc)
            
            # Update stage records: mark current completed, mark next as running
            curr_stage_record = db.query(models.Stage).filter(
                models.Stage.job_id == job_id,
                models.Stage.stage_name == current_stage
            ).first()
            if curr_stage_record:
                curr_stage_record.status = "completed"
                curr_stage_record.completed_at = now_str
                curr_stage_record.updated_at = datetime.now(timezone.utc)

            next_stage_record = db.query(models.Stage).filter(
                models.Stage.job_id == job_id,
                models.Stage.stage_name == next_stage
            ).first()
            if next_stage_record:
                next_stage_record.status = "running"
                next_stage_record.started_at = now_str
                next_stage_record.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            
            # Log transition
            await job_service.add_log(job_id, "INFO", f"Advanced pipeline stage: {current_stage} -> {next_stage}", db=db)
            
            # If the next stage has an automated agent worker, enqueue it
            # For Stage 2, if no user claims were provided, it triggers Claim Extraction Agent
            # Otherwise, the user will trigger next steps.
            # We will enqueue next task if needed (Stage 2 claim extraction)
            if next_stage == "CLAIM_EXTRACTION":
                # Check if job has user claims
                claims = await job_service.get_claims_for_job(job_id)
                user_claims = [c for c in claims if c["source"] == "user"]
                if len(user_claims) > 0:
                    # User already supplied claims, we auto-complete Stage 2
                    await job_service.add_log(job_id, "INFO", "User claims detected. Skipping automated claim extraction.", db=db)
                    
                    job_record.status = "CODE_EXECUTION"
                    job_record.current_stage = "CODE_EXECUTION"
                    job_record.updated_at = datetime.now(timezone.utc)
                    
                    ce_stage = db.query(models.Stage).filter(
                        models.Stage.job_id == job_id,
                        models.Stage.stage_name == "CLAIM_EXTRACTION"
                    ).first()
                    if ce_stage:
                        ce_stage.status = "completed"
                        ce_stage.completed_at = now_str
                        ce_stage.updated_at = datetime.now(timezone.utc)
                        
                    code_stage = db.query(models.Stage).filter(
                        models.Stage.job_id == job_id,
                        models.Stage.stage_name == "CODE_EXECUTION"
                    ).first()
                    if code_stage:
                        code_stage.status = "pending"
                        code_stage.updated_at = datetime.now(timezone.utc)
                    
                    db.commit()
                    await job_service.add_log(job_id, "INFO", "Advanced pipeline stage: CLAIM_EXTRACTION -> CODE_EXECUTION", db=db)
                else:
                    queue_service.enqueue_job_task("claim_extraction", job_id)
                    await job_service.add_log(job_id, "INFO", "Enqueued Claim Extraction task for processing...", db=db)
            elif next_stage == "CODE_EXECUTION":
                queue_service.enqueue_job_task("code_execution", job_id)
                await job_service.add_log(job_id, "INFO", "Enqueued Code Execution task for sandbox configuration...", db=db)
            elif next_stage == "CLAIM_REPLICATION":
                queue_service.enqueue_job_task("claim_replication", job_id)
                await job_service.add_log(job_id, "INFO", "Enqueued Claim Replication task for verifying paper claims...", db=db)
            elif next_stage == "DTREG_GENERATION":
                queue_service.enqueue_job_task("dtreg_generation", job_id)
                await job_service.add_log(job_id, "INFO", "Enqueued DTREG Generation task for metadata creation...", db=db)

        else:
            # All stages completed
            job_record.status = "COMPLETED"
            job_record.updated_at = datetime.now(timezone.utc)
            
            curr_stage_record = db.query(models.Stage).filter(
                models.Stage.job_id == job_id,
                models.Stage.stage_name == current_stage
            ).first()
            if curr_stage_record:
                curr_stage_record.status = "completed"
                curr_stage_record.completed_at = now_str
                curr_stage_record.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            await job_service.add_log(job_id, "INFO", "Pipeline execution fully completed.", db=db)
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "success", "message": "Pipeline advanced."}

@router.post("/retry", status_code=status.HTTP_200_OK)
async def retry_stage(job_id: str, db: Session = Depends(get_db)):
    """Retries execution of the current pipeline stage."""
    job = await job_service.get_job_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    current_stage = job.get("currentStage")
    
    try:
        # Reset job status
        job_record = db.query(models.Job).filter(models.Job.id == job_id).first()
        if job_record:
            job_record.status = current_stage
            job_record.updated_at = datetime.now(timezone.utc)

        # Reset stage status
        stage_record = db.query(models.Stage).filter(
            models.Stage.job_id == job_id,
            models.Stage.stage_name == current_stage
        ).first()
        if stage_record:
            stage_record.status = "pending"
            stage_record.error_log = None
            stage_record.sandbox_info = None
            stage_record.started_at = None
            stage_record.completed_at = None
            stage_record.updated_at = datetime.now(timezone.utc)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        
    await job_service.add_log(job_id, "INFO", f"Retrying stage: {current_stage}", db=db)

    # Enqueue task in Honker queue
    task_type = "provision" if current_stage == "PROVISIONING" else current_stage.lower()
    queue_service.enqueue_job_task(task_type, job_id)

    return {"status": "success", "message": f"Stage {current_stage} queued for retry."}

@router.get("/logs")
async def stream_logs(job_id: str, request: Request, follow: bool = True, bulk: bool = False, db: Session = Depends(get_db)):
    """Streams logs for a job. If follow is True, streams in real-time via SSE."""
    job = await job_service.get_job_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    async def log_generator():
        # 1. Fetch and stream all existing logs
        logs = await job_service.get_logs_for_job(job_id)
        if bulk:
            yield f"data: {json.dumps({'is_history': True, 'logs': logs})}\n\n"
        else:
            for log in logs:
                data = {
                    "timestamp": log.get("timestamp"),
                    "level": log.get("level"),
                    "message": log.get("message")
                }
                yield f"data: {json.dumps(data)}\n\n"
        
        if not follow:
            return

        # 2. Stream new logs in real-time via in-memory queue notifications
        from sciloom_pipeline.services.queue_service import queue_service
        
        queue = asyncio.Queue()
        queue_service.register_log_listener(job_id, queue)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    log_data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    if bulk:
                        yield f"data: {json.dumps({'is_history': False, 'log': log_data})}\n\n"
                    else:
                        yield f"data: {json.dumps(log_data)}\n\n"
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            queue_service.unregister_log_listener(job_id, queue)

    return StreamingResponse(log_generator(), media_type="text/event-stream")

@router.get("/sandbox", response_model=SandboxInfoResponse)
async def get_sandbox(job_id: str, db: Session = Depends(get_db)):
    """Retrieves connection details and status of the sandbox for a job."""
    info = await job_service.get_sandbox_info(job_id, db=db)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Sandbox info not found for job {job_id}."
        )
    return info

@router.delete("/sandbox")
async def delete_sandbox(job_id: str, db: Session = Depends(get_db)):
    """Explicitly requests deletion of the job's sandbox container."""
    job = await job_service.get_job_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found.")
        
    await job_service.delete_sandbox(job_id, db=db)
    return {"status": "success", "message": "Sandbox deletion completed."}

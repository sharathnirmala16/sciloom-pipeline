import json
import shutil
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Depends
from sqlalchemy.orm import Session

from sciloom_pipeline.schemas.job import JobResponse, OCRUpdateRequest
from sciloom_pipeline.services.job_service import job_service
from sciloom_pipeline.services.queue_service import queue_service
from sciloom_pipeline.config import settings
from sciloom_pipeline.db.database import get_db

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.get("", response_model=List[JobResponse])
async def list_jobs(db: Session = Depends(get_db)):
    """Retrieves all jobs."""
    return await job_service.get_all_jobs(db=db)

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: Session = Depends(get_db)):
    """Retrieves details of a single job."""
    job = await job_service.get_job_by_id(job_id, db=db)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found."
        )
    return job

@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    title: str = Form(...),
    repoSource: str = Form(...),
    repoUrl: Optional[str] = Form(None),
    dataSource: str = Form(...),
    manualClaims: Optional[str] = Form(None),
    pdfFile: UploadFile = File(...),
    repoFile: Optional[UploadFile] = File(None),
    dataFile: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Creates a new replication job, uploads files, and triggers Stage 1 provisioning in the background."""
    import secrets
    job_id = f"job_{secrets.token_hex(6)}"

    # Parse manual claims
    claims_list = []
    if manualClaims:
        try:
            claims_list = json.loads(manualClaims)
            if not isinstance(claims_list, list):
                raise ValueError("manualClaims must be a JSON array of strings.")
        except Exception:
            claims_list = [c.strip() for c in manualClaims.split(",") if c.strip()]

    # Validate parameters
    if repoSource not in ("github", "zip"):
        raise HTTPException(status_code=400, detail="repoSource must be either 'github' or 'zip'")
    if dataSource not in ("zip", "in_repo"):
        raise HTTPException(status_code=400, detail="dataSource must be either 'zip' or 'in_repo'")
    if repoSource == "github" and not repoUrl:
        raise HTTPException(status_code=400, detail="repoUrl is required when repoSource is 'github'")
    if repoSource == "zip" and not repoFile:
        raise HTTPException(status_code=400, detail="repoFile is required when repoSource is 'zip'")
    if dataSource == "zip" and not dataFile:
        raise HTTPException(status_code=400, detail="dataFile is required when dataSource is 'zip'")

    # Create workspace directories
    job_dir = settings.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save PDF file
    pdf_dest = job_dir / "paper.pdf"
    with open(pdf_dest, "wb") as f:
        shutil_copy(pdfFile.file, f)

    # 2. Save repository ZIP
    repo_file_name = None
    if repoSource == "zip" and repoFile:
        repo_file_name = repoFile.filename
        repo_dest = job_dir / "repo_temp.zip"
        with open(repo_dest, "wb") as f:
            shutil_copy(repoFile.file, f)

    # 3. Save dataset ZIP
    data_file_name = None
    if dataSource == "zip" and dataFile:
        data_file_name = dataFile.filename
        data_dest = job_dir / "data_temp.zip"
        with open(data_dest, "wb") as f:
            shutil_copy(dataFile.file, f)

    # Create DB entry via Session
    await job_service.create_job_record(
        job_id=job_id,
        title=title,
        pdf_name=pdfFile.filename,
        repo_source=repoSource,
        repo_url=repoUrl,
        repo_file_name=repo_file_name,
        data_source=dataSource,
        data_file_name=data_file_name,
        manual_claims=claims_list,
        db=db
    )

    # Enqueue Stage 1 task in Honker
    queue_service.enqueue_job_task("provision", job_id)

    # Retrieve created job
    job = await job_service.get_job_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=500, detail="Failed to retrieve created job.")
    return job

@router.get("/{job_id}/ocr")
async def get_ocr(job_id: str):
    """Retrieves the OCR Markdown text of the paper."""
    try:
        content = await job_service.get_ocr_markdown(job_id)
        return {"markdown": content}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{job_id}/ocr", status_code=status.HTTP_200_OK)
async def update_ocr(job_id: str, body: "OCRUpdateRequest", db: Session = Depends(get_db)):
    """Overwrites the OCR Markdown file with user-edited content and recalculates page counts."""
    job = await job_service.get_job_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    try:
        await job_service.update_ocr_markdown(job_id, body.markdown, db=db)
        return {"status": "success", "message": "OCR markdown updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{job_id}/ocr/retry", status_code=status.HTTP_200_OK)
async def retry_ocr(job_id: str, db: Session = Depends(get_db)):
    """Enqueues an OCR-only retry for an already-provisioned job."""
    job = await job_service.get_job_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    queue_service.enqueue_job_task("retry_ocr", job_id)
    return {"status": "success", "message": "OCR retry queued."}

@router.get("/{job_id}/files")
async def get_files(job_id: str):
    """Retrieves the recursive workspace directory files JSON tree."""
    try:
        files_tree = await job_service.get_repo_files(job_id)
        return files_tree
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{job_id}", status_code=status.HTTP_200_OK)
async def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Deletes a job record, its cascade relations, and its workspace directory."""
    from sciloom_pipeline.db import models
    job_record = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found."
        )
    
    try:
        db.delete(job_record)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    try:
        job_dir = settings.jobs_dir / job_id
        if job_dir.is_dir():
            shutil.rmtree(job_dir)
    except Exception as e:
        print(f"Warning: Failed to remove directory for job {job_id}: {e}")

    return {"status": "success", "message": f"Job {job_id} successfully deleted."}

def shutil_copy(src, dst):
    import shutil
    shutil.copyfileobj(src, dst)

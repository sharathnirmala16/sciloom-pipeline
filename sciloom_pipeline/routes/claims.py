import time
import json
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from sciloom_pipeline.schemas.claim import ClaimResponse, ClaimsSyncRequest
from sciloom_pipeline.services.job_service import job_service
from sciloom_pipeline.db.database import get_db
from sciloom_pipeline.db import models

router = APIRouter(prefix="/jobs/{job_id}/claims", tags=["Claims"])

@router.get("", response_model=List[ClaimResponse])
async def get_claims(job_id: str, db: Session = Depends(get_db)):
    """Retrieves all claims registered for a specific job."""
    job = await job_service.get_job_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return await job_service.get_claims_for_job(job_id, db=db)

@router.put("", response_model=List[ClaimResponse])
async def sync_claims(job_id: str, request: ClaimsSyncRequest, db: Session = Depends(get_db)):
    """Synchronizes (adds, updates, removes) claims for a specific job using SQLAlchemy ORM."""
    job_record = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job_record:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    incoming_claims = request.claims
    
    # Get existing claims from DB
    existing_claims = db.query(models.Claim).filter(models.Claim.job_id == job_id).all()
    existing_map = {c.id: c for c in existing_claims}
    
    incoming_ids = set()
    
    try:
        for idx, claim_data in enumerate(incoming_claims):
            claim_text = claim_data.claim_text or ""
            if not claim_text.strip():
                continue
                
            claim_id = claim_data.id or f"{job_id}_claim_{int(time.time() * 1000)}_{idx}"
            incoming_ids.add(claim_id)
            
            screenshots_json = json.dumps(claim_data.user_screenshots or [])
            
            if claim_id in existing_map:
                # Update existing ORM object
                existing_claim = existing_map[claim_id]
                existing_claim.claim_text = claim_text
                existing_claim.metrics = claim_data.metrics
                existing_claim.evidence = claim_data.evidence
                if claim_data.replicated is not None:
                    existing_claim.replicated = claim_data.replicated
                existing_claim.replication_error = claim_data.replication_error
                existing_claim.user_instructions = claim_data.user_instructions
                existing_claim.user_screenshots = screenshots_json
            else:
                # Insert new ORM object
                new_claim = models.Claim(
                    id=claim_id,
                    job_id=job_id,
                    claim_text=claim_text,
                    metrics=claim_data.metrics,
                    evidence=claim_data.evidence,
                    source="user",
                    replicated=claim_data.replicated or False,
                    replication_error=claim_data.replication_error,
                    user_instructions=claim_data.user_instructions,
                    user_screenshots=screenshots_json
                )
                db.add(new_claim)
        
        # Delete claims not present in incoming list
        for claim_id, existing_claim in existing_map.items():
            if claim_id not in incoming_ids:
                db.delete(existing_claim)
                
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    # Log action using service
    await job_service.add_log(job_id, "INFO", "User synchronized claims list via UI.", db=db)

    # Return updated claims
    return await job_service.get_claims_for_job(job_id, db=db)

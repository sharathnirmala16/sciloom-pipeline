from pydantic import BaseModel, Field
from typing import Optional, List

class ClaimBase(BaseModel):
    claim_text: str = Field(..., alias="claimText")
    metrics: Optional[str] = None
    evidence: Optional[str] = None
    source: str = "agent"  # 'agent' | 'user'
    replicated: bool = False
    replication_error: Optional[str] = Field(None, alias="replicationError")
    user_instructions: Optional[str] = Field(None, alias="userInstructions")
    user_screenshots: Optional[List[str]] = Field(default=[], alias="userScreenshots")

class ClaimCreate(BaseModel):
    claim_text: str = Field(..., alias="claimText")

class ClaimUpdate(BaseModel):
    id: Optional[str] = None
    claim_text: Optional[str] = Field(None, alias="claimText")
    metrics: Optional[str] = None
    evidence: Optional[str] = None
    replicated: Optional[bool] = None
    replication_error: Optional[str] = Field(None, alias="replicationError")
    user_instructions: Optional[str] = Field(None, alias="userInstructions")
    user_screenshots: Optional[List[str]] = Field(None, alias="userScreenshots")

class ClaimResponse(ClaimBase):
    id: str
    job_id: str = Field(..., alias="jobId")
    created_at: str = Field(..., alias="createdAt")

    class Config:
        populate_by_name = True
        from_attributes = True

class ClaimsSyncRequest(BaseModel):
    claims: List[ClaimUpdate]

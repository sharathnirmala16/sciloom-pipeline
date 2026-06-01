from pydantic import BaseModel, Field
from typing import Optional

class SandboxInfo(BaseModel):
    sandbox_id: str = Field(..., alias="sandboxId")
    connection_command: str = Field(..., alias="connectionCommand")

class StageResponse(BaseModel):
    id: str
    job_id: str = Field(..., alias="jobId")
    stage_name: str = Field(..., alias="stageName")
    status: str  # 'pending' | 'running' | 'completed' | 'failed'
    error_log: Optional[str] = Field(None, alias="errorLog")
    sandbox_info: Optional[SandboxInfo] = Field(None, alias="sandboxInfo")
    started_at: Optional[str] = Field(None, alias="startedAt")
    completed_at: Optional[str] = Field(None, alias="completedAt")

    class Config:
        populate_by_name = True
        from_attributes = True

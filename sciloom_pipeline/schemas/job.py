from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class JobStatus(str, Enum):
    CREATED = "CREATED"
    PROVISIONING = "PROVISIONING"
    PROVISIONED = "PROVISIONED"
    CLAIM_EXTRACTION = "CLAIM_EXTRACTION"
    CODE_EXECUTION = "CODE_EXECUTION"
    CLAIM_REPLICATION = "CLAIM_REPLICATION"
    DTREG_GENERATION = "DTREG_GENERATION"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"

class StageName(str, Enum):
    PROVISIONING = "PROVISIONING"
    CLAIM_EXTRACTION = "CLAIM_EXTRACTION"
    CODE_EXECUTION = "CODE_EXECUTION"
    CLAIM_REPLICATION = "CLAIM_REPLICATION"
    DTREG_GENERATION = "DTREG_GENERATION"

class RepoSource(str, Enum):
    github = "github"
    zip = "zip"

class DataSource(str, Enum):
    zip = "zip"
    in_repo = "in_repo"

class JobBase(BaseModel):
    title: str
    repo_source: RepoSource = Field(..., alias="repoSource")
    repo_url: Optional[str] = Field(None, alias="repoUrl")
    data_source: DataSource = Field(..., alias="dataSource")

class JobCreate(JobBase):
    manual_claims: Optional[List[str]] = Field(default=[], alias="manualClaims")

class JobResponse(BaseModel):
    id: str
    title: str
    pdf_path: str = Field(..., alias="pdfPath")
    pdf_name: str = Field(..., alias="pdfName")
    repo_source: RepoSource = Field(..., alias="repoSource")
    repo_url: Optional[str] = Field(None, alias="repoUrl")
    repo_file_name: Optional[str] = Field(None, alias="repoFileName")
    data_source: DataSource = Field(..., alias="dataSource")
    data_file_name: Optional[str] = Field(None, alias="dataFileName")
    status: str
    current_stage: str = Field(..., alias="currentStage")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")
    ocr_page_char_counts: Optional[List[int]] = Field(None, alias="ocrPageCharCounts")

    class Config:
        populate_by_name = True
        from_attributes = True

class JobLogResponse(BaseModel):
    timestamp: str
    level: str
    message: str

    class Config:
        from_attributes = True

class OCRUpdateRequest(BaseModel):
    """Request body for PUT /api/jobs/{job_id}/ocr — accepts raw markdown text."""
    markdown: str


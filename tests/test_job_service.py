import io
import zipfile
import pytest
from sciloom_pipeline.services.job_service import job_service
from sciloom_pipeline.config import settings

def create_in_memory_zip(file_tree: dict) -> bytes:
    """Helper to create a ZIP file in memory representing a mock repository."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for filename, content in file_tree.items():
            zip_file.writestr(filename, content)
    zip_buffer.seek(0)
    return zip_buffer.read()

@pytest.mark.asyncio
async def test_run_provisioning_zip_success(mock_ocr_extractor):
    """Positive Case: Verify provisioning runs successfully for a ZIP repo source."""
    job_id = "test_job_zip_success"
    job_dir = settings.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Create dummy paper.pdf
    pdf_path = job_dir / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy contents")
    
    # 2. Create dummy repo ZIP
    repo_zip = job_dir / "repo_temp.zip"
    file_tree = {
        "README.md": "# Readme Content",
        "src/main.py": "print('running main')"
    }
    repo_zip.write_bytes(create_in_memory_zip(file_tree))
    
    # Create DB entry
    await job_service.create_job_record(
        job_id=job_id,
        title="Zip Success Test",
        pdf_name="paper.pdf",
        repo_source="zip",
        repo_url=None,
        repo_file_name="repo_temp.zip",
        data_source="in_repo",
        data_file_name=None,
        manual_claims=["Claim: The model replicates easily."]
    )
    
    # Run provisioning
    await job_service.run_provisioning(job_id)
    
    # Verify Job updated to PROVISIONED
    job = await job_service.get_job_by_id(job_id)
    assert job["status"] == "PROVISIONED"
    
    # Verify Stage completed
    stages = await job_service.get_stages_for_job(job_id)
    prov_stage = next(s for s in stages if s["stageName"] == "PROVISIONING")
    assert prov_stage["status"] == "completed"
    
    # Verify files extracted and OCR created
    assert (job_dir / "REPO" / "README.md").is_file()
    assert (job_dir / "REPO" / "src" / "main.py").is_file()
    assert (job_dir / "REPO" / ".sciloom" / "RESEARCH_PAPER.md").is_file()
    assert not repo_zip.is_file()  # Temp zip deleted
    
    # Verify .opencode/agents folder was copied to REPO directory
    assert (job_dir / "REPO" / ".opencode" / "agents").is_dir()
    assert (job_dir / "REPO" / ".opencode" / "agents" / "code-execution-agent.md").is_file()
    assert not (job_dir / "REPO" / ".opencode" / "node_modules").exists()



@pytest.mark.asyncio
async def test_run_provisioning_missing_pdf(mock_ocr_extractor):
    """Negative Case: Verify provisioning fails when paper.pdf is missing."""
    job_id = "test_job_missing_pdf"
    job_dir = settings.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Write repo zip, but do NOT write paper.pdf
    repo_zip = job_dir / "repo_temp.zip"
    repo_zip.write_bytes(create_in_memory_zip({"README.md": "..."}))
    
    await job_service.create_job_record(
        job_id=job_id,
        title="Missing PDF Test",
        pdf_name="paper.pdf",
        repo_source="zip",
        repo_url=None,
        repo_file_name="repo_temp.zip",
        data_source="in_repo",
        data_file_name=None,
        manual_claims=[]
    )
    
    with pytest.raises(FileNotFoundError):
        await job_service.run_provisioning(job_id)
        
    # Verify Job updated to FAILED
    job = await job_service.get_job_by_id(job_id)
    assert job["status"] == "FAILED"
    
    # Verify Stage marked failed
    stages = await job_service.get_stages_for_job(job_id)
    prov_stage = next(s for s in stages if s["stageName"] == "PROVISIONING")
    assert prov_stage["status"] == "failed"
    assert prov_stage["errorLog"] is not None

@pytest.mark.asyncio
async def test_run_provisioning_zip_slip_prevention(mock_ocr_extractor):
    """Negative Case: Verify that directory traversal (Zip Slip) in repository zip is caught and prevented."""
    job_id = "test_job_zip_slip"
    job_dir = settings.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Create PDF
    pdf_path = job_dir / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy contents")
    
    # Create malicious ZIP containing a path traversal entry
    repo_zip = job_dir / "repo_temp.zip"
    malicious_buffer = io.BytesIO()
    with zipfile.ZipFile(malicious_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        # Relative traversal path
        zip_file.writestr("../traversal_file.txt", "unauthorized content")
        zip_file.writestr("good_file.txt", "authorized content")
    malicious_buffer.seek(0)
    repo_zip.write_bytes(malicious_buffer.read())
    
    await job_service.create_job_record(
        job_id=job_id,
        title="Zip Slip Test",
        pdf_name="paper.pdf",
        repo_source="zip",
        repo_url=None,
        repo_file_name="repo_temp.zip",
        data_source="in_repo",
        data_file_name=None,
        manual_claims=[]
    )
    
    # Verify that a PermissionError is raised
    with pytest.raises(PermissionError) as exc_info:
        await job_service.run_provisioning(job_id)
    
    assert "Directory traversal detected in ZIP" in str(exc_info.value)
    
    # Verify job status updated to FAILED
    job = await job_service.get_job_by_id(job_id)
    assert job["status"] == "FAILED"
    
    # Verify traversal file was NOT created outside REPO directory
    traversal_dest = job_dir / "traversal_file.txt"
    assert not traversal_dest.is_file()

@pytest.mark.asyncio
async def test_run_provisioning_invalid_git_url(mock_ocr_extractor):
    """Negative Case: Verify git cloning fails and prevents argument injection if URL is invalid."""
    job_id = "test_job_invalid_git"
    job_dir = settings.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Create PDF
    pdf_path = job_dir / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy contents")
    
    # URL starting with '-' is an injection threat to CLI arguments
    malicious_url = "--upload-pack=evil_payload"
    
    await job_service.create_job_record(
        job_id=job_id,
        title="Invalid Git Test",
        pdf_name="paper.pdf",
        repo_source="github",
        repo_url=malicious_url,
        repo_file_name=None,
        data_source="in_repo",
        data_file_name=None,
        manual_claims=[]
    )
    
    with pytest.raises(ValueError) as exc_info:
        await job_service.run_provisioning(job_id)
        
    assert "Invalid repository URL scheme" in str(exc_info.value)
    
    job = await job_service.get_job_by_id(job_id)
    assert job["status"] == "FAILED"

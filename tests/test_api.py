import json
import time
import pytest
from sciloom_pipeline.config import settings

def create_mock_zip_bytes() -> bytes:
    import io, zipfile
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr("README.md", "# Test Repo")
        zip_file.writestr("src/__init__.py", "")
    zip_buffer.seek(0)
    return zip_buffer.read()

def test_api_list_jobs_empty(fastapi_client):
    """Verify listing jobs returns empty list when no jobs are present."""
    response = fastapi_client.get("/api/jobs")
    assert response.status_code == 200
    assert response.json() == []

def test_api_create_job(fastapi_client):
    """Verify that posting multipart form data correctly initializes a job, uploads files, and runs provisioning."""
    pdf_bytes = b"%PDF-1.4 dummy contents"
    repo_zip_bytes = create_mock_zip_bytes()
    
    form_data = {
        "title": "API Test Job",
        "repoSource": "zip",
        "dataSource": "in_repo",
        "manualClaims": json.dumps(["Claim 1: Test accuracy improvements."])
    }
    
    files = {
        "pdfFile": ("paper.pdf", pdf_bytes, "application/pdf"),
        "repoFile": ("repo.zip", repo_zip_bytes, "application/zip")
    }
    
    # Submit job
    response = fastapi_client.post("/api/jobs", data=form_data, files=files)
    assert response.status_code == 201
    
    data = response.json()
    job_id = data["id"]
    assert data["title"] == "API Test Job"
    assert data["pdfName"] == "paper.pdf"
    assert data["repoSource"] == "zip"
    assert data["dataSource"] == "in_repo"
    
    # Wait for the Honker background worker to complete the provisioning task
    # (Since worker runs in asyncio loop in lifespan, we poll GET /api/jobs/{id})
    max_attempts = 10
    for attempt in range(max_attempts):
        time.sleep(0.5)
        status_resp = fastapi_client.get(f"/api/jobs/{job_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        if status_data["status"] == "PROVISIONED":
            break
    else:
         pytest.fail("Background provisioning task did not complete in time.")
         
    # Check directory file explorer tree endpoint
    files_resp = fastapi_client.get(f"/api/jobs/{job_id}/files")
    assert files_resp.status_code == 200
    files_tree = files_resp.json()
    assert len(files_tree) > 0
    assert any(f["name"] == "README.md" for f in files_tree)
    
    # Check OCR endpoint
    ocr_resp = fastapi_client.get(f"/api/jobs/{job_id}/ocr")
    assert ocr_resp.status_code == 200
    assert "Successfully parsed OCR" in ocr_resp.json()["markdown"]
    
    # Check claims list
    claims_resp = fastapi_client.get(f"/api/jobs/{job_id}/claims")
    assert claims_resp.status_code == 200
    claims = claims_resp.json()
    assert len(claims) == 1
    assert claims[0]["claimText"] == "Claim 1: Test accuracy improvements."

def test_api_sync_claims(fastapi_client):
    """Verify GET and PUT endpoints for claims lists operations."""
    pdf_bytes = b"%PDF-1.4 dummy contents"
    form_data = {
        "title": "Claims Sync Test",
        "repoSource": "github",
        "repoUrl": "https://github.com/example/repo",
        "dataSource": "in_repo",
        "manualClaims": json.dumps([])
    }
    files = {"pdfFile": ("paper.pdf", pdf_bytes, "application/pdf")}
    
    create_resp = fastapi_client.post("/api/jobs", data=form_data, files=files)
    job_id = create_resp.json()["id"]
    
    # Check claims initially empty
    get_resp = fastapi_client.get(f"/api/jobs/{job_id}/claims")
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 0
    
    # Update claims (PUT)
    new_claims_data = {
        "claims": [
            {"claimText": "Synced Claim A", "userInstructions": "First instruction"},
            {"claimText": "Synced Claim B", "replicated": True}
        ]
    }
    put_resp = fastapi_client.put(f"/api/jobs/{job_id}/claims", json=new_claims_data)
    assert put_resp.status_code == 200
    updated_claims = put_resp.json()
    assert len(updated_claims) == 2
    assert any(c["claimText"] == "Synced Claim A" and c["userInstructions"] == "First instruction" for c in updated_claims)
    assert any(c["claimText"] == "Synced Claim B" and c["replicated"] is True for c in updated_claims)
    
    # Verify deletions work by sync-ing a list with only the first claim
    claim_a_id = next(c["id"] for c in updated_claims if c["claimText"] == "Synced Claim A")
    sync_delete_data = {
        "claims": [
            {"id": claim_a_id, "claimText": "Synced Claim A - Updated"}
        ]
    }
    put_resp2 = fastapi_client.put(f"/api/jobs/{job_id}/claims", json=sync_delete_data)
    assert put_resp2.status_code == 200
    updated_claims2 = put_resp2.json()
    assert len(updated_claims2) == 1
    assert updated_claims2[0]["id"] == claim_a_id
    assert updated_claims2[0]["claimText"] == "Synced Claim A - Updated"

def test_api_advance_and_retry(fastapi_client):
    """Verify advancing and retrying pipeline stages updates database states correctly."""
    pdf_bytes = b"%PDF-1.4"
    repo_zip_bytes = create_mock_zip_bytes()
    form_data = {
        "title": "Stage Advance Test",
        "repoSource": "zip",
        "dataSource": "in_repo",
        "manualClaims": json.dumps(["User Supplied Claim"])  # Contains user claim
    }
    files = {
        "pdfFile": ("paper.pdf", pdf_bytes, "application/pdf"),
        "repoFile": ("repo.zip", repo_zip_bytes, "application/zip")
    }
    
    create_resp = fastapi_client.post("/api/jobs", data=form_data, files=files)
    job_id = create_resp.json()["id"]
    
    # Wait for it to become PROVISIONED
    max_attempts = 10
    for attempt in range(max_attempts):
        time.sleep(0.5)
        status_data = fastapi_client.get(f"/api/jobs/{job_id}").json()
        if status_data["status"] == "PROVISIONED":
            break
    else:
        pytest.fail("Failed to provision job in time.")

    # Try to advance
    advance_resp = fastapi_client.post(f"/api/jobs/{job_id}/advance")
    assert advance_resp.status_code == 200
    
    # Since job contains user claims, advancing from PROVISIONING will transition CLAIM_EXTRACTION
    # and skip straight to CODE_EXECUTION
    job_status = fastapi_client.get(f"/api/jobs/{job_id}").json()
    assert job_status["status"] == "CODE_EXECUTION"
    assert job_status["currentStage"] == "CODE_EXECUTION"
    
    # Test retry endpoint for CODE_EXECUTION stage
    retry_resp = fastapi_client.post(f"/api/jobs/{job_id}/retry")
    assert retry_resp.status_code == 200
    
    job_status_after_retry = fastapi_client.get(f"/api/jobs/{job_id}").json()
    # Retry sets status back to stage name
    assert job_status_after_retry["status"] == "CODE_EXECUTION"


def test_api_stages_and_logs_endpoints(fastapi_client):
    """Verify that the stages and logs endpoints return the expected positive values for a job."""
    pdf_bytes = b"%PDF-1.4 dummy contents"
    repo_zip_bytes = create_mock_zip_bytes()
    
    form_data = {
        "title": "Stages and Logs Test Job",
        "repoSource": "zip",
        "dataSource": "in_repo",
        "manualClaims": json.dumps(["Claim for testing stages/logs."])
    }
    
    files = {
        "pdfFile": ("paper.pdf", pdf_bytes, "application/pdf"),
        "repoFile": ("repo.zip", repo_zip_bytes, "application/zip")
    }
    
    # 1. Create a job
    response = fastapi_client.post("/api/jobs", data=form_data, files=files)
    assert response.status_code == 201
    job_data = response.json()
    job_id = job_data["id"]
    
    # 2. Test GET /api/jobs/{job_id}/stages immediately
    stages_resp = fastapi_client.get(f"/api/jobs/{job_id}/stages")
    assert stages_resp.status_code == 200
    stages = stages_resp.json()
    assert len(stages) == 5
    stage_names = [s["stageName"] for s in stages]
    assert "PROVISIONING" in stage_names
    assert "CLAIM_EXTRACTION" in stage_names
    
    # 3. Wait for the background worker to finish Stage 1 provisioning
    max_attempts = 10
    for attempt in range(max_attempts):
        time.sleep(0.5)
        status_resp = fastapi_client.get(f"/api/jobs/{job_id}")
        assert status_resp.status_code == 200
        if status_resp.json()["status"] == "PROVISIONED":
            break
    else:
        pytest.fail("Background provisioning task did not complete in time.")
        
    # 4. Test GET /api/jobs/{job_id}/stages after provisioning completes
    stages_resp_after = fastapi_client.get(f"/api/jobs/{job_id}/stages")
    assert stages_resp_after.status_code == 200
    stages_after = stages_resp_after.json()
    provisioning_stage = next(s for s in stages_after if s["stageName"] == "PROVISIONING")
    assert provisioning_stage["status"] == "completed"
    
    # 5. Test GET /api/jobs/{job_id}/logs (SSE streaming endpoint, with follow=false to get log snapshot)
    logs_resp = fastapi_client.get(f"/api/jobs/{job_id}/logs?follow=false")
    assert logs_resp.status_code == 200
    stream_lines = []
    for line in logs_resp.iter_lines():
        if line:
            decoded = line.strip()
            if decoded.startswith("data:"):
                data_str = decoded[len("data:"):].strip()
                log_data = json.loads(data_str)
                stream_lines.append(log_data)
    assert len(stream_lines) > 0
    assert any("Initializing provisioning" in l["message"] for l in stream_lines)


def test_api_claims_key_normalization(fastapi_client):
    """Verify that get_claims endpoint normalizes keys from agent-generated CLAIMS.json properly."""
    pdf_bytes = b"%PDF-1.4 dummy contents"
    form_data = {
        "title": "Claims Normalization Test",
        "repoSource": "github",
        "repoUrl": "https://github.com/example/repo",
        "dataSource": "in_repo",
        "manualClaims": json.dumps([])
    }
    files = {"pdfFile": ("paper.pdf", pdf_bytes, "application/pdf")}
    
    # 1. Create a job
    create_resp = fastapi_client.post("/api/jobs", data=form_data, files=files)
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]
    
    # 2. Write an agent-style CLAIMS.json with claim_id and claim_text
    from sciloom_pipeline.services.job_service import job_service
    sciloom_dir = job_service._ensure_sciloom_dir(job_id)
    claims_path = sciloom_dir / "CLAIMS.json"
    
    agent_claims = [
        {
            "id": "CLAIM-001",
            "claimText": "First agent claim statement.",
            "metrics": "metrics-a",
            "evidence": "evidence-a"
        },
        {
            "id": "CLAIM-002",
            "claimText": "Second agent claim statement."
        }
    ]
    
    with open(claims_path, "w", encoding="utf-8") as f:
        json.dump(agent_claims, f)
        
    # 3. Retrieve claims via GET API endpoint
    get_resp = fastapi_client.get(f"/api/jobs/{job_id}/claims")
    assert get_resp.status_code == 200
    
    claims = get_resp.json()
    assert len(claims) == 2
    
    # Verify mapping to id, jobId, claimText, etc.
    assert claims[0]["id"] == "CLAIM-001"
    assert claims[0]["jobId"] == job_id
    assert claims[0]["claimText"] == "First agent claim statement."
    assert claims[0]["metrics"] == "metrics-a"
    assert claims[0]["evidence"] == "evidence-a"
    assert claims[0]["source"] == "agent"
    
    assert claims[1]["id"] == "CLAIM-002"
    assert claims[1]["jobId"] == job_id
    assert claims[1]["claimText"] == "Second agent claim statement."
    assert claims[1]["source"] == "agent"




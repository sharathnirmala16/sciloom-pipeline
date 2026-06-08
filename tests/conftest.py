import os
import sys
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure the root package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
test_temp_dir = REPO_ROOT / "jobs" / ".test_temp"

# Clean and recreate test temp dir
if os.path.exists(test_temp_dir):
    shutil.rmtree(test_temp_dir, ignore_errors=True)
os.makedirs(test_temp_dir, exist_ok=True)

os.environ["DATABASE_PATH"] = str(test_temp_dir / "test_sciloom.db")
os.environ["JOBS_DIR"] = str(test_temp_dir / "jobs")

from sqlalchemy import text
from sciloom_pipeline.config import settings
from sciloom_pipeline.db.database import init_db, engine
from sciloom_pipeline.services.queue_service import queue_service

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Initializes the database and sets up cleanup hooks for the test session."""
    # Ensure jobs directory exists
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    yield
    # Clean up and close Honker DB connection to stop background threads before deleting files
    try:
        from sciloom_pipeline.services.queue_service import db as honker_db
        honker_db.close()
    except Exception:
        pass
    # Clean up test temp files after test session finishes
    shutil.rmtree(test_temp_dir, ignore_errors=True)
@pytest.fixture(autouse=True)
def clean_database():
    """Cleans up all table contents before each test case to prevent cross-test pollution."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM stages"))
        conn.execute(text("DELETE FROM jobs"))
        # Clear honker's internal tables if any exist
        try:
            conn.execute(text("DELETE FROM _honker_live"))
            conn.execute(text("DELETE FROM _honker_dead"))
        except Exception:
            pass
    yield

@pytest.fixture
def mock_ocr_extractor():
    """Mocks PDFExtractor.extract method globally during the test to avoid Gemini API calls."""
    async def mock_extract(self, pdf_path, output_dir, dpi=300):
        out_path = Path(output_dir) / "RESEARCH_PAPER.md"
        out_path.write_text("# Mocked Research Paper\nSuccessfully parsed OCR.", encoding="utf-8")
        return out_path, [100]

    with patch("sciloom_pipeline.document_processing.pdf_extractor.PDFExtractor.extract", new=mock_extract) as mock:
        yield mock

@pytest.fixture
def fastapi_client(mock_ocr_extractor):
    """Starts the FastAPI client and context (triggering lifespan and Honker worker) for tests."""
    from fastapi.testclient import TestClient
    from sciloom_pipeline.main import app
    
    with TestClient(app) as client:
        yield client

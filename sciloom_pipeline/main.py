import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from sciloom_pipeline.document_processing.pdf_extractor import PDFExtractor

load_dotenv()

# main.py lives at <repo_root>/sciloom_pipeline/main.py, so the repo root
# is always one level up — regardless of the working directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = REPO_ROOT / "jobs"


async def main():
    extractor = PDFExtractor(gemini_api_key=os.getenv("GEMINI_API_KEY"))
    await extractor.extract(
        pdf_path=JOBS_DIR / "job_2" / "s10340-022-01489-1.pdf",
        output_dir=JOBS_DIR / "job_2",
    )


if __name__ == "__main__":
    asyncio.run(main())

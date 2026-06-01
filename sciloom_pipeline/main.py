import os
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

from sciloom_pipeline.db.database import init_db
from sciloom_pipeline.services.queue_service import queue_service
from sciloom_pipeline.routes.jobs import router as jobs_router
from sciloom_pipeline.routes.claims import router as claims_router
from sciloom_pipeline.routes.pipeline import router as pipeline_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the SQLite tables
    init_db()
    # Start the background task queue worker
    await queue_service.start_worker()
    yield
    # Stop the background worker on exit
    await queue_service.stop_worker()

# Initialize FastAPI application
app = FastAPI(
    title="SciLoom Pipeline API",
    description="Backend API for managing paper OCR, repository sandboxing, claim verification and DTREG generation.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for the Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production environments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes under the '/api' prefix
app.include_router(jobs_router, prefix="/api")
app.include_router(claims_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    # Start local uvicorn development server
    uvicorn.run("sciloom_pipeline.main:app", host="0.0.0.0", port=8000, reload=True)

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    gemini_api_key: str = ""
    jobs_dir: Path = REPO_ROOT / "jobs"
    database_path: Path = REPO_ROOT / "jobs" / "sciloom.db"

    # API configuration
    api_prefix: str = "/api"
    project_name: str = "SciLoom Pipeline"

settings = Settings()

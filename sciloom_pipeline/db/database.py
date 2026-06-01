import sqlite3
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from sciloom_pipeline.config import settings

# Construct the SQLite database URL
SQLALCHEMY_DATABASE_URL = f"sqlite:///{settings.database_path}"

# Create engine with thread-safe settings for SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Create SessionLocal sessionmaker class
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enables WAL mode, foreign keys, and registers compatibility fallback functions on SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()

    # Register custom unixepoch fallback function if system SQLite version < 3.38.0
    if sqlite3.sqlite_version_info < (3, 38, 0):
        import time
        dbapi_connection.create_function("unixepoch", 0, lambda: int(time.time()))

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session context."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """Runs Alembic migrations programmatically to set up/upgrade the database schema."""
    from alembic.config import Config
    from alembic import command
    from pathlib import Path
    
    # Locate alembic.ini relative to this file
    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("programmatic", "true")
    command.upgrade(alembic_cfg, "head")


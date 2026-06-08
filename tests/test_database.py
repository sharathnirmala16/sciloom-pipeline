from sqlalchemy import text
from sciloom_pipeline.db.database import engine

def test_database_wal_mode():
    """Verify that the database connection enables WAL (Write-Ahead Logging) mode and foreign keys."""
    with engine.connect() as conn:
        # Check journal mode
        journal_mode = conn.execute(text("PRAGMA journal_mode;")).scalar()
        assert journal_mode.upper() == "WAL"
        
        # Check foreign keys
        foreign_keys = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert foreign_keys == 1

def test_database_tables_exist():
    """Verify that all required Stage 1 tables are correctly initialized in the database."""
    with engine.connect() as conn:
        cursor = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
        tables = {row[0] for row in cursor.fetchall()}
        
        required_tables = {"jobs", "stages"}
        assert required_tables.issubset(tables)


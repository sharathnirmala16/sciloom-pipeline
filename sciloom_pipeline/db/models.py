from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import ForeignKey, String, DateTime, Boolean, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    pdf_path: Mapped[str] = mapped_column(String(255))
    repo_source: Mapped[Optional[str]] = mapped_column(String(50))
    repo_url: Mapped[Optional[str]] = mapped_column(String(500))
    data_source: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="CREATED")
    current_stage: Mapped[str] = mapped_column(String(50), default="PROVISIONING")
    sandbox_id: Mapped[Optional[str]] = mapped_column(String(100))
    opencode_session_id: Mapped[Optional[str]] = mapped_column(String(512))
    opencode_server_url: Mapped[Optional[str]] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    stages: Mapped[List["Stage"]] = relationship("Stage", back_populates="job", cascade="all, delete-orphan", order_by="Stage.id")
    claims: Mapped[List["Claim"]] = relationship("Claim", back_populates="job", cascade="all, delete-orphan", order_by="Claim.created_at")
    logs: Mapped[List["Log"]] = relationship("Log", back_populates="job", cascade="all, delete-orphan", order_by="Log.id")
    ocr_logs: Mapped[List["OcrLog"]] = relationship("OcrLog", back_populates="job", cascade="all, delete-orphan", order_by="OcrLog.page_number")


class OcrLog(Base):
    __tablename__ = "ocr_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(50), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="ocr_logs")


class Stage(Base):
    __tablename__ = "stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(50), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    stage_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_log: Mapped[Optional[str]] = mapped_column(String)
    sandbox_info: Mapped[Optional[str]] = mapped_column(String)  # JSON-serialized sandbox info
    started_at: Mapped[Optional[str]] = mapped_column(String(100))
    completed_at: Mapped[Optional[str]] = mapped_column(String(100))
    output_json: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="stages")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(50), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    claim_text: Mapped[str] = mapped_column(String, nullable=False)
    metrics: Mapped[Optional[str]] = mapped_column(String)
    evidence: Mapped[Optional[str]] = mapped_column(String)
    source: Mapped[str] = mapped_column(String(50), default="agent")  # 'agent' | 'user'
    replicated: Mapped[bool] = mapped_column(Boolean, default=False)
    replication_error: Mapped[Optional[str]] = mapped_column(String)
    user_instructions: Mapped[Optional[str]] = mapped_column(String)
    user_screenshots: Mapped[Optional[str]] = mapped_column(String, default="[]")  # JSON array
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="claims")


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(50), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)  # 'INFO' | 'WARN' | 'ERROR'
    message: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="logs")

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

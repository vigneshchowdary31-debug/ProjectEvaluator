"""
Project Report ORM model — stores the authoritative unified audit report for a project.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectReport(Base):
    __tablename__ = "project_reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    audit_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("audit_runs.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    
    # ── Scores & Classifications ─────────────────────────────────────
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    completion_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    security_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    performance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    uiux_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    code_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    production_readiness: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # ── Full JSON Data ───────────────────────────────────────────────
    report_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # ── Supabase Storage URLs ────────────────────────────────────────
    report_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    json_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # ── Relationships ────────────────────────────────────────────────
    project: Mapped["Project"] = relationship("Project", back_populates="project_reports")  # noqa: F821
    audit_run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="project_report")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ProjectReport {self.id} for project {self.project_id}>"

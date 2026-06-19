"""
Generated Report ORM model — stores comprehensive Student and Company reports.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import DateTime, ForeignKey, String, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    completion_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    student_report: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    company_report: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # ── Relationships ────────────────────────────────────────────────
    project: Mapped["Project"] = relationship("Project")  # noqa: F821

    def __repr__(self) -> str:
        return f"<GeneratedReport {self.id} for project {self.project_id}>"

"""
Evidence ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Evidence(Base):
    __tablename__ = "evidences"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    audit_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("audit_runs.id"), nullable=False
    )
    file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    function_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    line_range: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    screenshot_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")  # noqa: F821
    audit_run: Mapped["AuditRun"] = relationship("AuditRun")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Evidence {self.evidence_type} for project {self.project_id}>"

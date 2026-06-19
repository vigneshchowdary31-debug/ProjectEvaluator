"""
Report ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Union

from sqlalchemy import DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    findings: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    severity: Mapped[str] = mapped_column(
        String(50), default="info"
    )  # info | low | medium | high | critical
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    audit_run_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("audit_runs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # ── Relationships ────────────────────────────────────────────────
    project: Mapped["Project"] = relationship("Project", back_populates="reports")  # noqa: F821
    audit_run: Mapped[Optional["AuditRun"]] = relationship(  # noqa: F821
        "AuditRun", back_populates="reports"
    )

    def __repr__(self) -> str:
        return f"<Report {self.title}>"

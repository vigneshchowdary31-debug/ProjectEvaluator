"""
AuditRun ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from sqlalchemy import DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditRun(Base):
    __tablename__ = "audit_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending | running | completed | failed
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trigger: Mapped[str] = mapped_column(
        String(50), default="manual"
    )  # manual | scheduled
    config: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    triggered_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # ── Relationships ────────────────────────────────────────────────
    project: Mapped["Project"] = relationship("Project", back_populates="audit_runs")  # noqa: F821
    triggered_by_user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="triggered_runs"
    )
    reports: Mapped[list["Report"]] = relationship(  # noqa: F821
        "Report", back_populates="audit_run"
    )

    # ── Valid status transitions ─────────────────────────────────────
    VALID_TRANSITIONS: Dict[str, Set[str]] = {
        "pending": {"running", "failed"},
        "running": {"completed", "failed"},
        "completed": set(),
        "failed": {"pending"},  # allow retry
    }

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.VALID_TRANSITIONS.get(self.status, set())

    def __repr__(self) -> str:
        return f"<AuditRun {self.id} [{self.status}]>"

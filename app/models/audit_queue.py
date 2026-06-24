"""
Audit queue ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditQueue(Base):
    __tablename__ = "audit_queues"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="queued")  # queued | running | completed | failed | cancelled
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1 (highest) to 10 (lowest)
    trigger_reason: Mapped[str] = mapped_column(String(255))  # approval_granted | prd_changed | manual
    audit_run_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("audit_runs.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failed_stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_successful_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="queue_items")  # noqa: F821
    audit_run: Mapped[Optional["AuditRun"]] = relationship("AuditRun")  # noqa: F821

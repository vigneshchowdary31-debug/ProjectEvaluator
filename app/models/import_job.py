"""
Import job ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    sheet_connection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sheet_connections.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="running")  # running | completed | failed
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # List of error dicts
    triggered_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    sheet_connection: Mapped["SheetConnection"] = relationship("SheetConnection", back_populates="import_jobs")  # noqa: F821
    user: Mapped["User"] = relationship("User")  # noqa: F821
    sync_histories: Mapped[list["ProjectSyncHistory"]] = relationship("ProjectSyncHistory", back_populates="import_job", cascade="all, delete-orphan")  # noqa: F821

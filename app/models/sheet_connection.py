"""
Sheet connection ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SheetConnection(Base):
    __tablename__ = "sheet_connections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet_url: Mapped[str] = mapped_column(String(512), nullable=False)
    sheet_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active")  # active | disconnected | error
    sync_frequency: Mapped[str] = mapped_column(String(50), default="manual")  # manual | hourly | daily
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # success | failed
    last_sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    owner: Mapped["User"] = relationship("User")  # noqa: F821
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="sheet_connection")  # noqa: F821
    import_jobs: Mapped[list["ImportJob"]] = relationship("ImportJob", back_populates="sheet_connection", cascade="all, delete-orphan")  # noqa: F821

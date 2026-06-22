"""
Project sync history ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectSyncHistory(Base):
    __tablename__ = "project_sync_histories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    import_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(50))  # created | updated | unchanged
    changes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {field: {old, new}}
    sheet_row_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="sync_histories")  # noqa: F821
    import_job: Mapped["ImportJob"] = relationship("ImportJob", back_populates="sync_histories")  # noqa: F821

"""
Project ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repository_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    prd_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    deployment_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")  # active | archived
    rbac_enabled: Mapped[bool] = mapped_column(default=False)
    admin_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    user_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    secret_reference: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # ── Relationships ────────────────────────────────────────────────
    owner: Mapped["User"] = relationship("User", back_populates="projects")  # noqa: F821
    reports: Mapped[list["Report"]] = relationship(  # noqa: F821
        "Report", back_populates="project", cascade="all, delete-orphan"
    )
    audit_runs: Mapped[list["AuditRun"]] = relationship(  # noqa: F821
        "AuditRun", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name}>"

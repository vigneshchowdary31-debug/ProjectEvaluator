"""
Project ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Integer
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
    auth_required: Mapped[bool] = mapped_column(default=False)
    login_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    secret_reference: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    
    # Google Sheets Integration Columns
    student_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual")  # manual | sheet_import
    sheet_row_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sheet_connection_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sheet_connections.id", ondelete="SET NULL"), nullable=True
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
    rbac_results: Mapped[list["RBACAuditResult"]] = relationship(  # noqa: F821
        "RBACAuditResult", back_populates="project", cascade="all, delete-orphan"
    )
    auth_results: Mapped[list["AuthAuditResult"]] = relationship(  # noqa: F821
        "AuthAuditResult", back_populates="project", cascade="all, delete-orphan"
    )
    evidences: Mapped[list["Evidence"]] = relationship(  # noqa: F821
        "Evidence", back_populates="project", cascade="all, delete-orphan"
    )
    generated_reports: Mapped[list["GeneratedReport"]] = relationship(  # noqa: F821
        "GeneratedReport", back_populates="project", cascade="all, delete-orphan"
    )
    
    # New relationships
    sheet_connection: Mapped[Optional["SheetConnection"]] = relationship(  # noqa: F821
        "SheetConnection", back_populates="projects"
    )
    approval: Mapped[Optional["ProjectApproval"]] = relationship(  # noqa: F821
        "ProjectApproval", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    sync_histories: Mapped[list["ProjectSyncHistory"]] = relationship(  # noqa: F821
        "ProjectSyncHistory", back_populates="project", cascade="all, delete-orphan"
    )
    queue_items: Mapped[list["AuditQueue"]] = relationship(  # noqa: F821
        "AuditQueue", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name}>"

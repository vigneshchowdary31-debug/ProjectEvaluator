"""
AuthAuditResult ORM model — stores authentication quality test results per audit run.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Float, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthAuditResult(Base):
    __tablename__ = "auth_audit_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    audit_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("audit_runs.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )

    # Overall status
    status: Mapped[str] = mapped_column(String(50), default="UNTESTED")  # UNTESTED | SUCCESS | PARTIAL | FAILED

    # Test results
    login_success: Mapped[bool] = mapped_column(Boolean, default=False)
    logout_success: Mapped[bool] = mapped_column(Boolean, default=False)
    session_persisted: Mapped[bool] = mapped_column(Boolean, default=False)
    invalid_password_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    empty_creds_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    routes_protected: Mapped[bool] = mapped_column(Boolean, default=False)

    # Redirect tracking
    redirect_after_login: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    redirect_after_logout: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Route discovery
    protected_routes_found: Mapped[int] = mapped_column(Integer, default=0)
    protected_routes_audited: Mapped[int] = mapped_column(Integer, default=0)

    # Scoring
    auth_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Login URL used
    login_url_used: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # JSON results
    findings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    protected_routes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="auth_results")  # noqa: F821
    audit_run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="auth_results")  # noqa: F821

    def __repr__(self) -> str:
        return f"<AuthAuditResult {self.id} status={self.status}>"

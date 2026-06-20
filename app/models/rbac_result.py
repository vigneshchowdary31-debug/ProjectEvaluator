"""
RBACAuditResult ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RBACAuditResult(Base):
    __tablename__ = "rbac_audit_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    audit_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("audit_runs.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    rbac_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="UNTESTED")  # UNTESTED | RUNNING | COMPLETED | FAILED
    
    # Scores
    auth_score: Mapped[float] = mapped_column(Float, default=0.0)
    authz_score: Mapped[float] = mapped_column(Float, default=0.0)
    session_score: Mapped[float] = mapped_column(Float, default=0.0)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # JSON results
    role_coverage_matrix: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    violations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    findings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")  # noqa: F821
    audit_run: Mapped["AuditRun"] = relationship("AuditRun")  # noqa: F821

    def __repr__(self) -> str:
        return f"<RBACAuditResult {self.id} for audit_run {self.audit_run_id}>"

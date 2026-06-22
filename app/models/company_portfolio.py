"""
Company portfolio ORM model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CompanyPortfolio(Base):
    __tablename__ = "company_portfolios"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    projects_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_completion: Mapped[float] = mapped_column(Float, default=0.0)
    avg_security: Mapped[float] = mapped_column(Float, default=0.0)
    avg_readiness: Mapped[float] = mapped_column(Float, default=0.0)
    projects_at_risk: Mapped[int] = mapped_column(Integer, default=0)
    top_risks: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # List/dict of risks
    health_rating: Mapped[str] = mapped_column(String(50), default="average")  # excellent | good | average | poor
    report_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    last_generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<CompanyPortfolio {self.company_name}>"

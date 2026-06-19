"""
GitHub Analysis ORM model for caching.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import DateTime, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GithubAnalysis(Base):
    __tablename__ = "github_analyses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    repo_url: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(100), nullable=True)
    result: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<GithubAnalysis {self.repo_url} @ {self.commit_sha}>"

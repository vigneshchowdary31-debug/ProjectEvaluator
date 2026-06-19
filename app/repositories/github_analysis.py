"""
GitHub Analysis Repository — data-access layer for GithubAnalysis model.
"""

from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.github_analysis import GithubAnalysis


class GithubAnalysisRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, analysis_id: str) -> Optional[GithubAnalysis]:
        return self.db.get(GithubAnalysis, analysis_id)

    def get_by_repo_url(self, repo_url: str) -> Optional[GithubAnalysis]:
        stmt = select(GithubAnalysis).where(GithubAnalysis.repo_url == repo_url)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all_cached(self, page: int = 1, page_size: int = 20) -> Tuple[List[GithubAnalysis], int]:
        count_stmt = select(func.count(GithubAnalysis.id))
        data_stmt = select(GithubAnalysis)

        total = self.db.execute(count_stmt).scalar() or 0
        offset = (page - 1) * page_size
        data_stmt = data_stmt.offset(offset).limit(page_size).order_by(
            GithubAnalysis.updated_at.desc()
        )
        analyses = list(self.db.execute(data_stmt).scalars().all())
        return analyses, total

    def create(self, analysis: GithubAnalysis) -> GithubAnalysis:
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def update(self, analysis: GithubAnalysis, commit_sha: Optional[str], result: dict) -> GithubAnalysis:
        analysis.commit_sha = commit_sha
        analysis.result = result
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def delete(self, analysis: GithubAnalysis) -> None:
        self.db.delete(analysis)
        self.db.commit()

"""
Generated Report Repository — data-access layer for GeneratedReport model.
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.generated_report import GeneratedReport


class GeneratedReportRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, report_id: str) -> Optional[GeneratedReport]:
        return self.db.get(GeneratedReport, report_id)

    def get_by_project_id(self, project_id: str) -> List[GeneratedReport]:
        stmt = (
            select(GeneratedReport)
            .where(GeneratedReport.project_id == project_id)
            .order_by(GeneratedReport.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, report: GeneratedReport) -> GeneratedReport:
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def delete(self, report: GeneratedReport) -> None:
        self.db.delete(report)
        self.db.commit()

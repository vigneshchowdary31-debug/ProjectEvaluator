"""
Project Report Repository — data-access layer for ProjectReport model.
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project_report import ProjectReport


class ProjectReportRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, report_id: str) -> Optional[ProjectReport]:
        return self.db.get(ProjectReport, report_id)

    def get_by_project_id(self, project_id: str) -> List[ProjectReport]:
        stmt = (
            select(ProjectReport)
            .where(ProjectReport.project_id == project_id)
            .order_by(ProjectReport.generated_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, report: ProjectReport) -> ProjectReport:
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def delete(self, report: ProjectReport) -> None:
        self.db.delete(report)
        self.db.commit()

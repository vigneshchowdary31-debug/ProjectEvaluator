"""
Report repository — data-access layer for Report model.
"""

from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.report import Report


class ReportRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, report_id: str) -> Optional[Report]:
        return self.db.get(Report, report_id)

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        project_id: Optional[str] = None,
        audit_run_id: Optional[str] = None,
    ) -> Tuple[List[Report], int]:
        count_stmt = select(func.count(Report.id))
        data_stmt = select(Report)

        if project_id:
            count_stmt = count_stmt.where(Report.project_id == project_id)
            data_stmt = data_stmt.where(Report.project_id == project_id)
        if audit_run_id:
            count_stmt = count_stmt.where(Report.audit_run_id == audit_run_id)
            data_stmt = data_stmt.where(Report.audit_run_id == audit_run_id)

        total = self.db.execute(count_stmt).scalar() or 0
        offset = (page - 1) * page_size
        data_stmt = data_stmt.offset(offset).limit(page_size).order_by(
            Report.created_at.desc()
        )
        reports = list(self.db.execute(data_stmt).scalars().all())
        return reports, total

    def get_by_project(self, project_id: str) -> List[Report]:
        stmt = select(Report).where(Report.project_id == project_id)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, report: Report) -> Report:
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def update(self, report: Report, data: dict) -> Report:
        for key, value in data.items():
            if value is not None:
                setattr(report, key, value)
        self.db.commit()
        self.db.refresh(report)
        return report

    def delete(self, report: Report) -> None:
        self.db.delete(report)
        self.db.commit()

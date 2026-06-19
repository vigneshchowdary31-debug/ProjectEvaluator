"""
AuditRun repository — data-access layer for AuditRun model.
"""

from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_run import AuditRun


class AuditRunRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, audit_run_id: str) -> Optional[AuditRun]:
        return self.db.get(AuditRun, audit_run_id)

    def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[AuditRun], int]:
        count_stmt = select(func.count(AuditRun.id))
        data_stmt = select(AuditRun)

        if project_id:
            count_stmt = count_stmt.where(AuditRun.project_id == project_id)
            data_stmt = data_stmt.where(AuditRun.project_id == project_id)
        if status:
            count_stmt = count_stmt.where(AuditRun.status == status)
            data_stmt = data_stmt.where(AuditRun.status == status)

        total = self.db.execute(count_stmt).scalar() or 0
        offset = (page - 1) * page_size
        data_stmt = data_stmt.offset(offset).limit(page_size).order_by(
            AuditRun.created_at.desc()
        )
        runs = list(self.db.execute(data_stmt).scalars().all())
        return runs, total

    def get_by_project(self, project_id: str) -> List[AuditRun]:
        stmt = (
            select(AuditRun)
            .where(AuditRun.project_id == project_id)
            .order_by(AuditRun.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, audit_run: AuditRun) -> AuditRun:
        self.db.add(audit_run)
        self.db.commit()
        self.db.refresh(audit_run)
        return audit_run

    def update(self, audit_run: AuditRun, data: dict) -> AuditRun:
        for key, value in data.items():
            if value is not None:
                setattr(audit_run, key, value)
        self.db.commit()
        self.db.refresh(audit_run)
        return audit_run

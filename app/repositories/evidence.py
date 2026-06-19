"""
Evidence Repository — data-access layer for Evidence model.
"""

from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.evidence import Evidence


class EvidenceRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, evidence_id: str) -> Evidence:
        return self.db.get(Evidence, evidence_id)

    def get_by_project_id(self, project_id: str) -> List[Evidence]:
        stmt = (
            select(Evidence)
            .where(Evidence.project_id == project_id)
            .order_by(Evidence.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_audit_run_id(self, audit_run_id: str) -> List[Evidence]:
        stmt = (
            select(Evidence)
            .where(Evidence.audit_run_id == audit_run_id)
            .order_by(Evidence.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, evidence: Evidence) -> Evidence:
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)
        return evidence

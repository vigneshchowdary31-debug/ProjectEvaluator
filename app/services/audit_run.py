"""
AuditRun service — business logic for audit run management.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.audit_run import AuditRun
from app.repositories.audit_run import AuditRunRepository
from app.repositories.project import ProjectRepository
from app.schemas.audit_run import AuditRunCreate, AuditRunStatusUpdate
from app.utils.exceptions import BadRequestException, NotFoundException


class AuditRunService:

    def __init__(self, db: Session):
        self.audit_run_repo = AuditRunRepository(db)
        self.project_repo = ProjectRepository(db)

    def get_audit_run(self, audit_run_id: str) -> AuditRun:
        run = self.audit_run_repo.get_by_id(audit_run_id)
        if not run:
            raise NotFoundException(detail="Audit run not found")
        return run

    def list_audit_runs(
        self,
        page: int = 1,
        page_size: int = 20,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[AuditRun], int]:
        return self.audit_run_repo.get_all(
            page=page, page_size=page_size, project_id=project_id, status=status
        )

    def create_audit_run(self, data: AuditRunCreate, user_id: str) -> AuditRun:
        # Validate project exists
        project = self.project_repo.get_by_id(data.project_id)
        if not project:
            raise NotFoundException(detail="Project not found")

        audit_run = AuditRun(
            project_id=data.project_id,
            triggered_by=user_id,
            trigger=data.trigger.value if hasattr(data.trigger, "value") else data.trigger,
            config=data.config,
            status="pending",
        )
        return self.audit_run_repo.create(audit_run)

    def update_status(
        self, audit_run_id: str, data: AuditRunStatusUpdate
    ) -> AuditRun:
        run = self.get_audit_run(audit_run_id)
        new_status = data.status.value if hasattr(data.status, "value") else data.status

        # Enforce state machine
        if not run.can_transition_to(new_status):
            raise BadRequestException(
                detail=f"Cannot transition from '{run.status}' to '{new_status}'"
            )

        update_data: Dict = {"status": new_status}

        # Automatically set timestamps
        now = datetime.now(timezone.utc)
        if new_status == "running":
            update_data["started_at"] = now
        elif new_status in ("completed", "failed"):
            update_data["completed_at"] = now

        if data.result_summary is not None:
            update_data["result_summary"] = data.result_summary

        return self.audit_run_repo.update(run, update_data)

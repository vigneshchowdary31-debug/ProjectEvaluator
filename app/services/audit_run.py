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

    def get_audit_run_diagnostics(self, audit_run_id: str) -> dict:
        """
        Gathers diagnostic details for an audit run, including checked backend dependency health status.
        """
        run = self.get_audit_run(audit_run_id)
        
        # Check backend dependencies dynamically
        dependency_status = {}
        
        # 1. Supabase/PostgreSQL
        try:
            from sqlalchemy import text
            self.audit_run_repo.db.execute(text("select 1"))
            dependency_status["supabase"] = "healthy"
        except Exception as e:
            dependency_status["supabase"] = f"unhealthy ({str(e)})"
            
        # 2. Gemini API
        from app.config import get_settings
        settings = get_settings()
        if not settings.GEMINI_API_KEY:
            dependency_status["gemini"] = "unconfigured (missing key)"
        else:
            try:
                from google import genai
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                dependency_status["gemini"] = "healthy"
            except Exception as e:
                dependency_status["gemini"] = f"unhealthy ({str(e)})"
                
        # 3. Playwright Headless Browser
        try:
            import playwright
            dependency_status["playwright"] = "healthy"
        except Exception as e:
            dependency_status["playwright"] = f"unhealthy (missing package: {str(e)})"
            
        # 4. Google Drive API
        from app.services.google_drive import GoogleDriveService
        try:
            drive = GoogleDriveService()
            if not drive.enabled:
                dependency_status["google_drive"] = "disabled"
            else:
                try:
                    drive.service.files().list(pageSize=1).execute()
                    dependency_status["google_drive"] = "healthy"
                except Exception as e:
                    dependency_status["google_drive"] = f"degraded ({str(e)})"
        except Exception as e:
            dependency_status["google_drive"] = f"unhealthy ({str(e)})"
                
        # 5. Google Sheets API
        from app.services.google_sheets import GoogleSheetsService
        try:
            sheets = GoogleSheetsService()
            if not sheets.enabled:
                dependency_status["google_sheets"] = "disabled"
            else:
                if sheets.service:
                    dependency_status["google_sheets"] = "healthy"
                else:
                    dependency_status["google_sheets"] = "unhealthy"
        except Exception as e:
            dependency_status["google_sheets"] = f"unhealthy ({str(e)})"

        return {
            "audit_run_id": run.id,
            "failed_stage": run.failed_stage,
            "failure_reason": run.failure_reason,
            "failure_stack_trace": run.failure_stack_trace,
            "last_successful_step": run.last_successful_step,
            "dependency_status": dependency_status
        }

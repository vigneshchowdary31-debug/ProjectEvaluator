"""
Report service — business logic for report management.
"""

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.report import Report
from app.repositories.report import ReportRepository
from app.repositories.project import ProjectRepository
from app.schemas.report import ReportCreate, ReportUpdate
from app.utils.exceptions import NotFoundException


class ReportService:

    def __init__(self, db: Session):
        self.report_repo = ReportRepository(db)
        self.project_repo = ProjectRepository(db)

    def get_report(self, report_id: str) -> Report:
        report = self.report_repo.get_by_id(report_id)
        if not report:
            raise NotFoundException(detail="Report not found")
        return report

    def list_reports(
        self,
        page: int = 1,
        page_size: int = 20,
        project_id: Optional[str] = None,
        audit_run_id: Optional[str] = None,
    ) -> Tuple[List[Report], int]:
        return self.report_repo.get_all(
            page=page,
            page_size=page_size,
            project_id=project_id,
            audit_run_id=audit_run_id,
        )

    def create_report(self, data: ReportCreate) -> Report:
        # Validate project exists
        project = self.project_repo.get_by_id(data.project_id)
        if not project:
            raise NotFoundException(detail="Project not found")

        report = Report(
            title=data.title,
            summary=data.summary,
            findings=data.findings,
            severity=data.severity.value if hasattr(data.severity, "value") else data.severity,
            project_id=data.project_id,
            audit_run_id=data.audit_run_id,
        )
        return self.report_repo.create(report)

    def update_report(self, report_id: str, data: ReportUpdate) -> Report:
        report = self.get_report(report_id)
        update_data = data.model_dump(exclude_unset=True)
        if "severity" in update_data and update_data["severity"] is not None:
            update_data["severity"] = update_data["severity"].value if hasattr(update_data["severity"], "value") else update_data["severity"]
        return self.report_repo.update(report, update_data)

    def delete_report(self, report_id: str) -> None:
        report = self.get_report(report_id)
        self.report_repo.delete(report)

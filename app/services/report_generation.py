"""
Report Generation Service — orchestrates compiling PRD, GitHub, Browser,
and Matching findings into Student and Company reports, and saving them to database.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.project_report import ProjectReport
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.project_report import ProjectReportRepository
from app.schemas.report_generation import (
    ReportGenerationRequest,
    ReportGenerationResponse,
)
from app.services.llm.llm_service import LLMService, LLMError
from app.utils.exceptions import BadRequestException, ForbiddenException, NotFoundException

logger = logging.getLogger(__name__)


class ReportGenerationService:
    """Orchestrates report generation and database storage."""

    def __init__(self, db: Session, audit_run=None):
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.report_repo = ProjectReportRepository(db)
        self.audit_run = audit_run
        self.llm = LLMService(audit_run=audit_run)

    def generate(
        self, request: ReportGenerationRequest, current_user: User
    ) -> ReportGenerationResponse:
        logger.info(
            "Request to generate reports for project: %s by user: %s",
            request.project_id,
            current_user.email,
        )

        # 1. Verify project exists
        project = self.project_repo.get_by_id(request.project_id)
        if not project:
            raise NotFoundException(detail="Project not found")

        # 2. Check ownership
        if project.owner_id != current_user.id and not current_user.is_admin:
            raise ForbiddenException(detail="You do not own this project")

        # 3. Calculate completion percentage
        implemented = request.requirement_analysis.implemented_features
        partial = request.requirement_analysis.partially_implemented_features
        missing = request.requirement_analysis.missing_features
        
        total_features = len(implemented) + len(partial) + len(missing)
        calc_percentage = -1.0
        if total_features > 0:
            calc_percentage = ((len(implemented) + 0.5 * len(partial)) / total_features) * 100.0

        logger.info("Calculated base completion percentage: %.1f%%", calc_percentage)

        # 4. Invoke LLM to generate reports
        try:
            report_data = self.llm.generate_project_reports(
                prd=request.prd_analysis,
                github=request.github_analysis,
                browser=request.browser_analysis,
                matching=request.requirement_analysis,
                calc_percentage=calc_percentage
            )
        except LLMError as e:
            logger.error("LLM report generation failed: %s", str(e))
            raise BadRequestException(detail=f"Report generation failed: {str(e)}")

        # 5. Build and save database model
        audit_run_id = self.audit_run.id if self.audit_run else ""
        db_report = ProjectReport(
            audit_run_id=audit_run_id,
            project_id=request.project_id,
            overall_score=report_data.overall_score,
            completion_score=report_data.requirement_completion_score,
            security_score=report_data.security_score,
            performance_score=report_data.performance_score,
            uiux_score=report_data.uiux_score,
            code_quality_score=report_data.code_quality_score,
            production_readiness=report_data.status,
            status=report_data.status,
            report_data=report_data.model_dump()
        )
        
        self.report_repo.create(db_report)

        logger.info("Successfully created and saved generated report: %s", db_report.id)

        # 6. Format API response
        return ReportGenerationResponse(
            id=db_report.id,
            project_id=db_report.project_id,
            report=report_data,
            created_at=db_report.generated_at.isoformat()
        )

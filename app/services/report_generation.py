"""
Report Generation Service — orchestrates compiling PRD, GitHub, Browser,
and Matching findings into Student and Company reports, and saving them to database.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.generated_report import GeneratedReport
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.generated_report import GeneratedReportRepository
from app.schemas.report_generation import (
    ReportGenerationRequest,
    ReportGenerationResponse,
)
from app.services.gemini import GeminiError, GeminiService
from app.utils.exceptions import BadRequestException, ForbiddenException, NotFoundException

logger = logging.getLogger(__name__)


class ReportGenerationService:
    """Orchestrates report generation and database storage."""

    def __init__(self, db: Session):
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.report_repo = GeneratedReportRepository(db)
        self.gemini = GeminiService()

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
        calc_percentage = 0.0
        if total_features > 0:
            calc_percentage = ((len(implemented) + 0.5 * len(partial)) / total_features) * 100.0

        logger.info("Calculated base completion percentage: %.1f%%", calc_percentage)

        # 4. Invoke Gemini to generate reports
        try:
            gemini_wrapper = self.gemini.generate_project_reports(
                prd=request.prd_analysis,
                github=request.github_analysis,
                browser=request.browser_analysis,
                matching=request.requirement_analysis,
                calc_percentage=calc_percentage
            )
        except GeminiError as e:
            logger.error("Gemini report generation failed: %s", str(e))
            raise BadRequestException(detail=f"Report generation failed: {str(e)}")

        # 5. Build and save database model
        student_dict = gemini_wrapper.student_report.model_dump()
        company_dict = gemini_wrapper.company_report.model_dump()

        db_report = GeneratedReport(
            project_id=request.project_id,
            completion_percentage=calc_percentage,
            student_report=student_dict,
            company_report=company_dict
        )
        
        self.report_repo.create(db_report)

        logger.info("Successfully created and saved generated report: %s", db_report.id)

        # 6. Format API response
        return ReportGenerationResponse(
            id=db_report.id,
            project_id=db_report.project_id,
            completion_percentage=db_report.completion_percentage,
            student_report=gemini_wrapper.student_report,
            company_report=gemini_wrapper.company_report,
            created_at=db_report.created_at.isoformat()
        )

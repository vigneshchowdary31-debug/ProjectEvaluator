"""
Report Generation Router — endpoints for generating and listing Student and Company reports.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.report_generation import (
    ReportGenerationRequest,
    ReportGenerationResponse,
)
from app.services.report_generation import ReportGenerationService
from app.repositories.generated_report import GeneratedReportRepository
from app.repositories.project import ProjectRepository
from app.utils.exceptions import ForbiddenException, NotFoundException

router = APIRouter(prefix="/api/v1/reports", tags=["Report Generation"])


@router.post(
    "/generate",
    response_model=ReportGenerationResponse,
    summary="Generate comprehensive Student and Company reports",
    description=(
        "Aggregates PRD analysis, GitHub repository analysis, Browser crawler audit data, "
        "and Requirement matching findings. Uses Gemini to construct educational Student and "
        "executive Company reports, stores them in SQLite, and returns them."
    ),
)
def generate_project_report(
    request: ReportGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Triggers project report generation. Restricts execution to project owner/admin.
    """
    service = ReportGenerationService(db)
    return service.generate(request, current_user)


@router.get(
    "/project/{project_id}",
    response_model=List[ReportGenerationResponse],
    summary="Get all generated reports for a project",
    description="Lists all Student and Company reports previously generated for the specified project.",
)
def get_project_reports(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves project reports history. Enforces ownership/admin authorization check.
    """
    # Verify project ownership
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id(project_id)
    if not project:
        raise NotFoundException(detail="Project not found")

    if project.owner_id != current_user.id and not current_user.is_admin:
        raise ForbiddenException(detail="You do not own this project")

    repo = GeneratedReportRepository(db)
    reports = repo.get_by_project_id(project_id)
    
    # Format DB results into response schema
    response_items = []
    for r in reports:
        response_items.append(ReportGenerationResponse(
            id=r.id,
            project_id=r.project_id,
            completion_percentage=r.completion_percentage,
            student_report=r.student_report,
            company_report=r.company_report,
            created_at=r.created_at.isoformat()
        ))
    return response_items

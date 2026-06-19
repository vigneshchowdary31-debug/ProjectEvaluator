"""
Projects router — CRUD for projects with nested report & audit-run listing.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.audit_run import AuditRunListResponse, AuditRunResponse
from app.schemas.project import ProjectCreate, ProjectListResponse, ProjectResponse, ProjectUpdate
from app.schemas.report import ReportListResponse
from app.services.audit_run import AuditRunService
from app.services.project import ProjectService
from app.services.report import ReportService
from app.services.orchestrator import OrchestratorService

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


@router.get("/", response_model=ProjectListResponse)
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List projects. Admins see all; regular users see only their own."""
    project_service = ProjectService(db)
    projects, total = project_service.list_projects(
        page=page, page_size=page_size, current_user=current_user
    )
    return ProjectListResponse(
        items=projects, total=total, page=page, page_size=page_size
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a project by ID."""
    project_service = ProjectService(db)
    return project_service.get_project(project_id)


@router.post("/", response_model=ProjectResponse, status_code=201)
def create_project(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new project (owner = current user)."""
    project_service = ProjectService(db)
    return project_service.create_project(data, owner_id=current_user.id)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a project (owner or admin only)."""
    project_service = ProjectService(db)
    return project_service.update_project(project_id, data, current_user)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a project (owner or admin only)."""
    project_service = ProjectService(db)
    project_service.delete_project(project_id, current_user)


# ── Nested resources ────────────────────────────────────────────────────────

@router.get("/{project_id}/reports", response_model=ReportListResponse)
def list_project_reports(
    project_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all reports for a specific project."""
    # Ensure project exists
    ProjectService(db).get_project(project_id)
    report_service = ReportService(db)
    reports, total = report_service.list_reports(
        page=page, page_size=page_size, project_id=project_id
    )
    return ReportListResponse(
        items=reports, total=total, page=page, page_size=page_size
    )


@router.get("/{project_id}/audit-runs", response_model=AuditRunListResponse)
def list_project_audit_runs(
    project_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all audit runs for a specific project."""
    ProjectService(db).get_project(project_id)
    audit_run_service = AuditRunService(db)
    runs, total = audit_run_service.list_audit_runs(
        page=page, page_size=page_size, project_id=project_id
    )
    return AuditRunListResponse(
        items=runs, total=total, page=page, page_size=page_size
    )


@router.post("/{project_id}/audit", response_model=AuditRunResponse, status_code=201)
def trigger_project_audit(
    project_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger a comprehensive end-to-end background audit for a project.
    """
    project_service = ProjectService(db)
    project = project_service.get_project(project_id)
    project_service._check_ownership(project, current_user)
    
    orchestrator = OrchestratorService(db)
    return orchestrator.trigger_audit(project_id, background_tasks, current_user.id)

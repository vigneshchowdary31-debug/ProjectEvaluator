"""
AuditRuns router — create, list, get, and update status of audit runs.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.audit_run import (
    AuditRunCreate,
    AuditRunListResponse,
    AuditRunResponse,
    AuditRunStatusUpdate,
)
from app.services.audit_run import AuditRunService

router = APIRouter(prefix="/api/v1/audit-runs", tags=["Audit Runs"])


@router.get("/", response_model=AuditRunListResponse)
def list_audit_runs(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List audit runs with optional filters."""
    audit_run_service = AuditRunService(db)
    runs, total = audit_run_service.list_audit_runs(
        page=page, page_size=page_size, project_id=project_id, status=status
    )
    return AuditRunListResponse(
        items=runs, total=total, page=page, page_size=page_size
    )


@router.get("/{audit_run_id}", response_model=AuditRunResponse)
def get_audit_run(
    audit_run_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get an audit run by ID."""
    audit_run_service = AuditRunService(db)
    return audit_run_service.get_audit_run(audit_run_id)


@router.post("/", response_model=AuditRunResponse, status_code=201)
def create_audit_run(
    data: AuditRunCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new audit run for a project."""
    audit_run_service = AuditRunService(db)
    return audit_run_service.create_audit_run(data, user_id=current_user.id)


@router.patch("/{audit_run_id}/status", response_model=AuditRunResponse)
def update_audit_run_status(
    audit_run_id: str,
    data: AuditRunStatusUpdate,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update the status of an audit run.

    Valid transitions:
    - pending → running, failed
    - running → completed, failed
    - failed → pending (retry)
    - completed → (terminal state)
    """
    audit_run_service = AuditRunService(db)
    return audit_run_service.update_status(audit_run_id, data)

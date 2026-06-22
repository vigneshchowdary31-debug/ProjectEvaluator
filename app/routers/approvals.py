"""
Approvals Router — endpoints to manage admin approval workflow of imported projects.
"""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.project_approval import ProjectApproval
from app.services.approval_service import ApprovalService
from app.schemas.approvals import ProjectApprovalResponse, ProjectApprovalReviewRequest, BulkApproveRequest
from app.utils.exceptions import NotFoundException, ForbiddenException

router = APIRouter(prefix="/api/v1/approvals", tags=["Google Sheets Intake & Automation"])


def _check_admin(user: User) -> None:
    if not user.is_admin:
        raise ForbiddenException(detail="Admin privilege required for this action")


@router.get("/", response_model=List[ProjectApprovalResponse])
def get_pending_approvals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all projects currently pending review."""
    _check_admin(current_user)
    service = ApprovalService(db)
    return service.get_pending_approvals()


@router.post("/{project_id}/approve", response_model=ProjectApprovalResponse)
def approve_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve a project and enqueue it in the automated audit queue."""
    _check_admin(current_user)
    service = ApprovalService(db)
    return service.approve(project_id, current_user.id)


@router.post("/{project_id}/reject", response_model=ProjectApprovalResponse)
def reject_project(
    project_id: str,
    payload: ProjectApprovalReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject a project and record review feedback/notes."""
    _check_admin(current_user)
    service = ApprovalService(db)
    return service.reject(project_id, current_user.id, payload.notes)


@router.post("/bulk-approve")
def bulk_approve_projects(
    payload: BulkApproveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bulk approve multiple projects."""
    _check_admin(current_user)
    service = ApprovalService(db)
    approved_count = service.bulk_approve(payload.project_ids, current_user.id)
    return {"approved_count": approved_count}

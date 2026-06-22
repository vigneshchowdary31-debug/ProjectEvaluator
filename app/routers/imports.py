"""
Imports Router — endpoints to retrieve sheet import job summaries and histories.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.import_job import ImportJob
from app.models.project_sync_history import ProjectSyncHistory
from app.schemas.sheets import ImportJobResponse, ProjectSyncHistoryResponse
from app.utils.exceptions import NotFoundException, ForbiddenException

router = APIRouter(prefix="/api/v1/imports", tags=["Google Sheets Intake & Automation"])


def _check_admin(user: User) -> None:
    if not user.is_admin:
        raise ForbiddenException(detail="Admin privilege required for this action")


@router.get("/", response_model=List[ImportJobResponse])
def list_import_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all sheet import jobs."""
    _check_admin(current_user)
    stmt = select(ImportJob).order_by(desc(ImportJob.started_at))
    return list(db.execute(stmt).scalars().all())


@router.get("/{id}", response_model=ImportJobResponse)
def get_import_job(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details of a specific sheet import job execution."""
    _check_admin(current_user)
    job = db.query(ImportJob).filter(ImportJob.id == id).first()
    if not job:
        raise NotFoundException(detail="Import job not found")
    return job


@router.get("/{id}/history", response_model=List[ProjectSyncHistoryResponse])
def get_import_job_history(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve detailed per-project sync logs and diffs for a specific import job."""
    _check_admin(current_user)
    stmt = select(ProjectSyncHistory).where(
        ProjectSyncHistory.import_job_id == id
    ).order_by(ProjectSyncHistory.sheet_row_number.asc())
    return list(db.execute(stmt).scalars().all())

"""
Queue Router — endpoints to monitor and manage the database-backed audit task queue.
"""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.audit_queue import AuditQueue
from app.services.audit_queue_service import AuditQueueService
from app.schemas.queue import AuditQueueResponse, QueueStatusResponse
from app.utils.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.config import get_settings

router = APIRouter(prefix="/api/v1/queue", tags=["Google Sheets Intake & Automation"])


def _check_admin(user: User) -> None:
    if not user.is_admin:
        raise ForbiddenException(detail="Admin privilege required for this action")


@router.get("/", response_model=List[AuditQueueResponse])
def get_queue_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all items currently in the audit queue, ordered by priority and date."""
    _check_admin(current_user)
    service = AuditQueueService(db)
    return service.get_recent_items(limit=100)


@router.get("/status", response_model=QueueStatusResponse)
def get_queue_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get summarized counts of audit queue tasks."""
    _check_admin(current_user)
    service = AuditQueueService(db)
    counts = service.get_queue_status()
    
    # We can fetch count of active worker threads or concurrent limit
    settings = get_settings()
    
    return QueueStatusResponse(
        counts=counts,
        active_worker_threads=settings.AUDIT_WORKER_CONCURRENCY
    )


@router.post("/{id}/cancel", response_model=AuditQueueResponse)
def cancel_queued_item(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a pending/queued audit run."""
    _check_admin(current_user)
    service = AuditQueueService(db)
    cancelled = service.cancel(id)
    if not cancelled:
        raise BadRequestException(detail="Only pending/queued tasks can be cancelled.")
    return cancelled

"""
Notifications Router — endpoints to retrieve, read, and manage in-app notifications.
"""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.notification_service import NotificationService
from app.schemas.notifications import NotificationResponse
from app.utils.exceptions import NotFoundException

router = APIRouter(prefix="/api/v1/notifications", tags=["In-app Notifications"])


@router.get("/", response_model=List[NotificationResponse])
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all notifications for the authenticated user."""
    service = NotificationService(db)
    return service.get_all(current_user.id)


@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the total count of unread notifications."""
    service = NotificationService(db)
    unread = service.get_unread(current_user.id)
    return {"unread_count": len(unread)}


@router.post("/{id}/read", response_model=NotificationResponse)
def mark_notification_read(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a specific notification as read."""
    service = NotificationService(db)
    notification = service.mark_read(id, current_user.id)
    if not notification:
        raise NotFoundException(detail="Notification not found")
    return notification


@router.post("/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all unread notifications as read."""
    service = NotificationService(db)
    count = service.mark_all_read(current_user.id)
    return {"marked_read_count": count}

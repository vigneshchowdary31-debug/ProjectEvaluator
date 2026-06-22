"""
Notification Service — manages in-app notifications.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.models.notification import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """Service to log and fetch in-app notifications."""

    def __init__(self, db: Session):
        self.db = db

    def notify(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """Create a new notification for a user."""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            metadata_=metadata,
            is_read=False
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        
        # Proactively trigger UI WebSocket notifications if websocket manager exists
        try:
            # We can import and broadcast using WS manager if applicable
            pass
        except Exception as ws_err:
            logger.debug("Failed to broadcast notification over websocket: %s", str(ws_err))

        return notification

    def get_unread(self, user_id: str) -> List[Notification]:
        """Fetch all unread notifications for a user."""
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).order_by(desc(Notification.created_at))
        return list(self.db.execute(stmt).scalars().all())

    def get_all(self, user_id: str, limit: int = 50) -> List[Notification]:
        """Fetch all notifications for a user (both read and unread)."""
        stmt = select(Notification).where(
            Notification.user_id == user_id
        ).order_by(desc(Notification.created_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def mark_read(self, notification_id: str, user_id: str) -> Notification:
        """Mark a notification as read."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id
        )
        notification = self.db.execute(stmt).scalar_one_or_none()
        if notification:
            notification.is_read = True
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user."""
        notifications = self.get_unread(user_id)
        count = len(notifications)
        for n in notifications:
            n.is_read = True
        self.db.commit()
        return count

"""
Audit Queue Service — database-backed task queue operations.
Uses PostgreSQL FOR UPDATE SKIP LOCKED for safe concurrent worker execution.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.models.audit_queue import AuditQueue

logger = logging.getLogger(__name__)


class AuditQueueService:
    """Service handling queuing, dequeuing, and monitoring audit tasks."""

    def __init__(self, db: Session):
        self.db = db

    def enqueue(self, project_id: str, trigger_reason: str, priority: int = 5) -> AuditQueue:
        """Add a project audit task to the queue if not already queued/running."""
        existing = self.db.query(AuditQueue).filter(
            AuditQueue.project_id == project_id,
            AuditQueue.status.in_(["queued", "running"])
        ).first()
        
        if existing:
            logger.info("Project %s is already queued/running (Queue ID: %s)", project_id, existing.id)
            return existing

        item = AuditQueue(
            project_id=project_id,
            status="queued",
            priority=priority,
            trigger_reason=trigger_reason
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        logger.info("Enqueued project %s for audit. Trigger reason: %s", project_id, trigger_reason)
        return item

    def dequeue(self) -> Optional[AuditQueue]:
        """Locks and retrieves the next queued audit task."""
        stmt = select(AuditQueue).where(AuditQueue.status == "queued").order_by(
            AuditQueue.priority.asc(), AuditQueue.created_at.asc()
        )
        
        # Check database dialect for SKIP LOCKED support
        dialect = "postgresql"
        if self.db.bind:
            dialect = self.db.bind.dialect.name
            
        if dialect == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True).limit(1)
        else:
            stmt = stmt.limit(1)
            
        result = self.db.execute(stmt).scalar_one_or_none()
        if result:
            result.status = "running"
            result.started_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(result)
            logger.info("Dequeued audit queue task %s (Project: %s) for running", result.id, result.project_id)
            return result
        return None

    def mark_completed(self, queue_id: str, audit_run_id: str) -> None:
        """Mark queue task as completed and link the generated audit run."""
        item = self.db.query(AuditQueue).filter(AuditQueue.id == queue_id).first()
        if item:
            item.status = "completed"
            item.audit_run_id = audit_run_id
            item.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.info("Completed queue task %s", queue_id)

    def mark_failed(self, queue_id: str, reason: str, failed_stage: Optional[str] = None, last_successful_step: Optional[str] = None) -> None:
        """Mark queue task as failed and log the reason."""
        item = self.db.query(AuditQueue).filter(AuditQueue.id == queue_id).first()
        if item:
            item.status = "failed"
            item.failure_reason = reason
            item.failed_stage = failed_stage
            item.last_successful_step = last_successful_step
            item.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.info("Failed queue task %s: %s", queue_id, reason)

    def cancel(self, queue_id: str) -> Optional[AuditQueue]:
        """Cancel a pending/queued task."""
        item = self.db.query(AuditQueue).filter(AuditQueue.id == queue_id).first()
        if item:
            if item.status == "queued":
                item.status = "cancelled"
                item.completed_at = datetime.now(timezone.utc)
                self.db.commit()
                self.db.refresh(item)
                logger.info("Cancelled queue task %s", queue_id)
                return item
            else:
                logger.warning("Cannot cancel queue task %s in status %s", queue_id, item.status)
        return None

    def get_queue_status(self) -> Dict[str, int]:
        """Get summary count of items in the queue by status."""
        from sqlalchemy import func
        counts = self.db.query(AuditQueue.status, func.count(AuditQueue.id)).group_by(AuditQueue.status).all()
        return {status: count for status, count in counts}

    def get_recent_items(self, limit: int = 50) -> List[AuditQueue]:
        """Get recent queue entries ordered by creation date."""
        stmt = select(AuditQueue).order_by(desc(AuditQueue.created_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

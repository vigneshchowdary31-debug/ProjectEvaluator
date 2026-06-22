"""
Approval Service — manages the project review/approval lifecycle before auditing.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.models.project import Project
from app.models.project_approval import ProjectApproval
from app.services.audit_queue_service import AuditQueueService
from app.services.notification_service import NotificationService
from app.utils.exceptions import NotFoundException, BadRequestException

logger = logging.getLogger(__name__)


class ApprovalService:
    """Business logic for reviewing, approving, and rejection of projects before they get audited."""

    def __init__(self, db: Session):
        self.db = db
        self.queue_service = AuditQueueService(db)
        self.notification_service = NotificationService(db)

    def get_pending_approvals(self) -> List[ProjectApproval]:
        """Get all projects awaiting review."""
        stmt = select(ProjectApproval).where(
            ProjectApproval.status == "pending"
        ).order_by(desc(ProjectApproval.created_at))
        return list(self.db.execute(stmt).scalars().all())

    def approve(self, project_id: str, admin_id: str) -> ProjectApproval:
        """Approve a project and enqueue it in the audit pipeline."""
        approval = self.db.query(ProjectApproval).filter(ProjectApproval.project_id == project_id).first()
        if not approval:
            raise NotFoundException(detail="Approval record not found for this project")

        if approval.status == "approved":
            raise BadRequestException(detail="Project is already approved")

        approval.status = "approved"
        approval.reviewed_by = admin_id
        approval.reviewed_at = datetime.now(timezone.utc)
        approval.notes = "Approved by admin."
        self.db.commit()

        # Enqueue project for audit
        self.queue_service.enqueue(
            project_id=project_id,
            trigger_reason="approval_granted",
            priority=5
        )

        # Notify project owner
        project = approval.project
        if project:
            self.notification_service.notify(
                user_id=project.owner_id,
                notification_type="approval_needed",
                title="Project Approved",
                message=f"Your project '{project.name}' has been approved and queued for audit.",
                metadata={"project_id": project_id}
            )

        logger.info("Project %s approved by admin %s", project_id, admin_id)
        return approval

    def reject(self, project_id: str, admin_id: str, notes: Optional[str] = None) -> ProjectApproval:
        """Reject a project with optional review feedback."""
        approval = self.db.query(ProjectApproval).filter(ProjectApproval.project_id == project_id).first()
        if not approval:
            raise NotFoundException(detail="Approval record not found for this project")

        approval.status = "rejected"
        approval.reviewed_by = admin_id
        approval.reviewed_at = datetime.now(timezone.utc)
        approval.notes = notes
        self.db.commit()

        # Notify project owner
        project = approval.project
        if project:
            self.notification_service.notify(
                user_id=project.owner_id,
                notification_type="approval_needed",
                title="Project Rejected",
                message=f"Your project '{project.name}' was rejected by the admin. Reason: {notes or 'No notes provided'}",
                metadata={"project_id": project_id}
            )

        logger.info("Project %s rejected by admin %s. Notes: %s", project_id, admin_id, notes)
        return approval

    def bulk_approve(self, project_ids: List[str], admin_id: str) -> int:
        """Approve multiple projects in a single operation."""
        count = 0
        for pid in project_ids:
            try:
                self.approve(pid, admin_id)
                count += 1
            except Exception as e:
                logger.warning("Failed to approve project %s in bulk: %s", pid, str(e))
        return count

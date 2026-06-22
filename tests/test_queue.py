import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker

from app.models.audit_queue import AuditQueue
from app.models.project import Project
from app.models.audit_run import AuditRun
from app.services.audit_queue_service import AuditQueueService
from app.services.audit_worker import AuditWorker
from tests.test_sheets import MockSession, DummyAdminUser


class MockQueueSession(MockSession):
    def __init__(self):
        super().__init__()
        self.queue_item = AuditQueue(
            id="queue-item-uuid",
            project_id="project-uuid",
            status="queued",
            priority=5,
            trigger_reason="approval_granted"
        )
        self.project_item = Project(
            id="project-uuid",
            name="Test Project",
            owner_id="admin-user-id",
            company_name="Google",
            sheet_connection_id="conn-id",
            sheet_row_number=10
        )
        
    def query(self, model):
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        
        if model == AuditQueue:
            mock_query.first.return_value = self.queue_item
        elif model == Project:
            mock_query.first.return_value = self.project_item
        elif model == AuditRun:
            # Return a completed run
            run = AuditRun(
                id="run-uuid",
                project_id="project-uuid",
                triggered_by="admin-user-id",
                status="completed",
                completed_at=datetime.now(timezone.utc)
            )
            mock_query.first.return_value = run
        else:
            mock_query.first.return_value = None
            
        mock_query.all.return_value = []
        return mock_query

    def execute(self, statement):
        mock_res = MagicMock()
        # Mock dequeue return
        mock_res.scalar_one_or_none.return_value = self.queue_item
        return mock_res


def test_queue_service_operations():
    db = MockQueueSession()
    service = AuditQueueService(db)
    
    # Test enqueue (already queued/running mock returns existing)
    item = service.enqueue("project-uuid", "approval_granted")
    assert item.status == "queued"
    assert item.project_id == "project-uuid"
    
    # Test dequeue
    dequeued = service.dequeue()
    assert dequeued is not None
    assert dequeued.status == "running"
    assert dequeued.started_at is not None
    
    # Test status marks
    service.mark_completed("queue-item-uuid", "run-uuid")
    assert db.queue_item.status == "completed"
    assert db.queue_item.audit_run_id == "run-uuid"
    assert db.queue_item.completed_at is not None
    
    service.mark_failed("queue-item-uuid", "Audit failed due to timeout.")
    assert db.queue_item.status == "failed"
    assert db.queue_item.failure_reason == "Audit failed due to timeout."


@pytest.mark.anyio
@patch("app.services.orchestrator.OrchestratorService.trigger_audit_direct")
@patch("app.services.orchestrator.OrchestratorService.run_audit_task")
@patch("app.services.sheet_writeback.SheetWritebackService.writeback")
@patch("app.services.portfolio_engine.PortfolioEngine.generate_portfolio")
async def test_worker_process_task(
    mock_portfolio, mock_writeback, mock_run_task, mock_trigger_direct
):
    # Setup mock Orchestrator returns
    mock_run = AuditRun(id="run-uuid", project_id="project-uuid", status="completed")
    mock_trigger_direct.return_value = mock_run
    
    db = MockQueueSession()
    # Force state of queue item for test
    db.queue_item.status = "running"
    
    session_factory = MagicMock(spec=sessionmaker)
    session_factory.return_value = db
    
    worker = AuditWorker(session_factory)
    
    # Process task synchronously in test
    await worker._process_task("queue-item-uuid", "project-uuid")
    
    # Verify Orchestrator was called to trigger and execute the audit task
    mock_trigger_direct.assert_called_once_with(
        project_id="project-uuid",
        user_id="admin-user-id",
        trigger_reason="approval_granted"
    )
    mock_run_task.assert_called_once_with("run-uuid", "project-uuid", "admin-user-id")
    
    # Verify sheets writeback and company portfolio refresh were invoked
    mock_writeback.assert_called_once_with("project-uuid")
    mock_portfolio.assert_called_once_with("Google")
    
    # Verify queue item is updated to completed
    assert db.queue_item.status == "completed"

"""
Audit Worker Service — runs as an async background task within the FastAPI lifespan
and processes queued project audits concurrently.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Set
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit_queue import AuditQueue
from app.models.project import Project
from app.models.audit_run import AuditRun
from app.services.audit_queue_service import AuditQueueService
from app.config import get_settings

logger = logging.getLogger(__name__)


class AuditWorker:
    """Async background worker that processes the database audit queue concurrently."""

    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory
        self.settings = get_settings()
        self.concurrency = self.settings.AUDIT_WORKER_CONCURRENCY
        self.enabled = self.settings.AUDIT_WORKER_ENABLED
        self.active_tasks: Set[asyncio.Task] = set()
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self.is_running = False
        self._loop_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background worker thread/loop."""
        if not self.enabled:
            logger.info("Audit Worker is disabled in configuration settings.")
            return
        
        self.is_running = True
        self._loop_task = asyncio.create_task(self._main_loop())
        logger.info("Audit Worker started successfully with concurrency: %d", self.concurrency)

    async def stop(self) -> None:
        """Stop the background loop and wait for any running audits to finish."""
        logger.info("Stopping Audit Worker...")
        self.is_running = False
        
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

        if self.active_tasks:
            logger.info("Waiting for %d active audits to complete...", len(self.active_tasks))
            await asyncio.gather(*self.active_tasks, return_exceptions=True)
            logger.info("All active worker audits completed.")
        
        logger.info("Audit Worker stopped.")

    async def _main_loop(self) -> None:
        """Daemon polling loop fetching and processing tasks."""
        while self.is_running:
            try:
                # Acquire concurrency semaphore slot
                await self.semaphore.acquire()
                
                db = self.session_factory()
                try:
                    queue_service = AuditQueueService(db)
                    queue_item = queue_service.dequeue()
                    if not queue_item:
                        # Release slot since no work was found
                        self.semaphore.release()
                        # Sleep before next polling attempt
                        await asyncio.sleep(5)
                        continue

                    # Spawn asynchronous task to process dequeued project
                    task = asyncio.create_task(
                        self._process_task(queue_item.id, queue_item.project_id)
                    )
                    self.active_tasks.add(task)
                    task.add_done_callback(lambda t: self._task_done(t))
                finally:
                    db.close()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Exception in Audit Worker main loop: %s", str(e))
                # Release semaphore slot on loop exception
                try:
                    self.semaphore.release()
                except ValueError:
                    pass
                await asyncio.sleep(5)

    def _task_done(self, task: asyncio.Task) -> None:
        """Done callback to release concurrency slots and track active tasks."""
        self.active_tasks.discard(task)
        self.semaphore.release()
        try:
            task.result()  # Propagate exception if task failed unexpectedly
        except Exception as e:
            logger.error("Task failed with unhandled exception: %s", str(e))

    async def _process_task(self, queue_item_id: str, project_id: str) -> None:
        """Execute the project audit, save reports, writeback to Google Sheet, and update portfolio."""
        db = self.session_factory()
        try:
            queue_service = AuditQueueService(db)
            queue_item = db.query(AuditQueue).filter(AuditQueue.id == queue_item_id).first()
            if not queue_item:
                return

            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                queue_service.mark_failed(queue_item_id, "Linked project record not found.")
                return

            # Instantiate orchestrator using background session
            from app.services.orchestrator import OrchestratorService
            orchestrator = OrchestratorService(db)
            
            trigger_user_id = project.owner_id

            # Create AuditRun record
            try:
                audit_run = orchestrator.trigger_audit_direct(
                    project_id=project_id,
                    user_id=trigger_user_id,
                    trigger_reason=queue_item.trigger_reason
                )
                queue_item.audit_run_id = audit_run.id
                db.commit()
            except Exception as trigger_err:
                queue_service.mark_failed(queue_item_id, f"Initialization of audit run failed: {str(trigger_err)}")
                return

            # Run actual audit task (GitHub fetch, PRD analysis, Browser audit, report gen)
            try:
                await orchestrator.run_audit_task(audit_run.id, project_id, trigger_user_id)
                
                # Refresh session and fetch updated audit run status
                db.refresh(queue_item)
                db_run = db.query(AuditRun).filter(AuditRun.id == audit_run.id).first()
                
                if db_run and db_run.status == "completed":
                    queue_service.mark_completed(queue_item_id, audit_run.id)
                    
                    # 1. Trigger writeback to sheet row
                    try:
                        from app.services.sheet_writeback import SheetWritebackService
                        writeback_service = SheetWritebackService(db)
                        writeback_service.writeback(project_id)
                    except Exception as wb_err:
                        logger.error("Sheet writeback failed for project %s: %s", project_id, str(wb_err))

                    # 2. Trigger company portfolio recalculation
                    if project.company_name:
                        try:
                            from app.services.portfolio_engine import PortfolioEngine
                            portfolio_engine = PortfolioEngine(db)
                            portfolio_engine.generate_portfolio(project.company_name)
                        except Exception as port_err:
                            logger.error("Company portfolio aggregation failed for %s: %s", project.company_name, str(port_err))
                else:
                    reason = db_run.result_summary if db_run else "Audit run did not complete successfully."
                    queue_service.mark_failed(queue_item_id, reason or "Failed during run task execution.")
                    
            except Exception as run_err:
                queue_service.mark_failed(queue_item_id, f"Error running audit task workflow: {str(run_err)}")
                
        except Exception as e:
            logger.error("Fatal exception in process task for project %s: %s", project_id, str(e))
        finally:
            db.close()

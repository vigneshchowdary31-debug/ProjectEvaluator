"""
Pydantic schemas for the audit queue monitoring.
"""

from datetime import datetime
from typing import Optional, Dict, List
from pydantic import BaseModel, Field
from app.schemas.project import ProjectResponse


class AuditQueueResponse(BaseModel):
    id: str
    project_id: str
    status: str
    priority: int
    trigger_reason: str
    audit_run_id: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    failure_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    project: Optional[ProjectResponse] = None

    model_config = {"from_attributes": True}


class QueueStatusResponse(BaseModel):
    counts: Dict[str, int] = Field(..., description="Summary counts of tasks grouped by queue status")
    active_worker_threads: Optional[int] = Field(0, description="Count of concurrent running workers")

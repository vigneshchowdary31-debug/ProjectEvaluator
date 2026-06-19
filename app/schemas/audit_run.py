"""
AuditRun schemas.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AuditRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditRunTrigger(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class AuditRunCreate(BaseModel):
    project_id: str
    trigger: AuditRunTrigger = AuditRunTrigger.MANUAL
    config: Optional[Dict[str, Any]] = None


class AuditRunStatusUpdate(BaseModel):
    status: AuditRunStatus
    result_summary: Optional[str] = None


class AuditRunResponse(BaseModel):
    id: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    trigger: str
    config: Optional[Dict[str, Any]]
    result_summary: Optional[str]
    project_id: str
    triggered_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditRunListResponse(BaseModel):
    items: List[AuditRunResponse]
    total: int
    page: int
    page_size: int

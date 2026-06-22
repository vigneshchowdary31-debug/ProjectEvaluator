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
    failed_stage: Optional[str] = None
    failure_reason: Optional[str] = None
    failure_stack_trace: Optional[str] = None
    last_successful_step: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditRunDiagnosticsResponse(BaseModel):
    audit_run_id: str
    failed_stage: Optional[str] = None
    failure_reason: Optional[str] = None
    failure_stack_trace: Optional[str] = None
    last_successful_step: Optional[str] = None
    dependency_status: Dict[str, str]


class AuditRunListResponse(BaseModel):
    items: List[AuditRunResponse]
    total: int
    page: int
    page_size: int

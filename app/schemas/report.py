"""
Report schemas.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReportCreate(BaseModel):
    title: str
    summary: str
    findings: Optional[Any] = None
    severity: Severity = Severity.INFO
    project_id: str
    audit_run_id: Optional[str] = None


class ReportUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    findings: Optional[Any] = None
    severity: Optional[Severity] = None


class ReportResponse(BaseModel):
    id: str
    title: str
    summary: str
    findings: Optional[Any]
    severity: str
    project_id: str
    audit_run_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    total: int
    page: int
    page_size: int

"""
Pydantic schemas for the Authenticated Audit Framework.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AuthAuditCredentialsSaveRequest(BaseModel):
    """Payload to save audited project authentication credentials securely."""
    auth_required: bool = Field(False, description="Enable authenticated testing for this project")
    login_url: Optional[str] = Field(None, description="Audited login page URL path")
    email: Optional[str] = Field(None, description="Audited login email credentials")
    password: Optional[str] = Field(None, description="Audited login password credentials")


class AuthAuditStatusResponse(BaseModel):
    """Payload returning authenticated validation status."""
    project_id: str
    auth_required: bool
    status: str  # UNTESTED | RUNNING | COMPLETED | FAILED
    has_credentials: bool
    last_audit_run_id: Optional[str]
    updated_at: Optional[datetime]


class AuthAuditFindingDetail(BaseModel):
    """Detailed category finding."""
    category: str  # AUTH | PROTECTED_ROUTE | SESSION
    title: str
    description: str
    severity: str  # low | medium | high | critical
    recommendation: str


class AuthAuditFindingsResponse(BaseModel):
    """Consolidated authenticated audit findings."""
    project_id: str
    audit_run_id: str
    findings: List[AuthAuditFindingDetail]


class AuthAuditScoresResponse(BaseModel):
    """Audited project authentication metrics score."""
    project_id: str
    audit_run_id: str
    auth_score: float


class AuthAuditProtectedRouteRow(BaseModel):
    """A row mapping a specific protected route's access status when unauthenticated."""
    route: str
    status: str  # ACCESSED | REDIRECTED | BLOCKED
    screenshot_url: Optional[str] = None


class AuthAuditProtectedRoutesResponse(BaseModel):
    """Detailed protected routes matrix compiled from Playwright runs."""
    project_id: str
    audit_run_id: str
    protected_routes: List[AuthAuditProtectedRouteRow]

"""
Pydantic schemas for the RBAC Audit Framework.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RBACCredentialsSaveRequest(BaseModel):
    """Payload to save audited project role credentials securely."""
    rbac_enabled: bool = Field(False, description="Enable RBAC testing for this project")
    admin_url: Optional[str] = Field(None, description="Audited admin panel URL path")
    admin_email: Optional[str] = Field(None, description="Audited admin email credentials")
    admin_password: Optional[str] = Field(None, description="Audited admin password credentials")
    user_url: Optional[str] = Field(None, description="Audited regular user dashboard URL path")
    user_email: Optional[str] = Field(None, description="Audited user email credentials")
    user_password: Optional[str] = Field(None, description="Audited user password credentials")


class RBACStatusResponse(BaseModel):
    """Payload returning RBAC validation status."""
    project_id: str
    rbac_enabled: bool
    status: str  # UNTESTED | RUNNING | COMPLETED | FAILED
    has_admin_credentials: bool
    has_user_credentials: bool
    last_audit_run_id: Optional[str]
    updated_at: Optional[datetime]


class RBACCoverageRow(BaseModel):
    """A row mapping a specific page's access status for a given role."""
    page: str
    role: str
    status: str  # ALLOWED | BLOCKED | PRIVILEGE_ESCALATION | UNKNOWN
    url: str
    screenshot_url: Optional[str] = None


class RBACCoverageResponse(BaseModel):
    """Detailed role coverage matrix compiled from Playwright runs."""
    project_id: str
    audit_run_id: str
    coverage: List[RBACCoverageRow]


class RBACFindingDetail(BaseModel):
    """Detailed category finding."""
    category: str  # AUTH | AUTHZ | SESSION
    title: str
    description: str
    severity: str  # low | medium | high | critical
    recommendation: str


class RBACFindingsResponse(BaseModel):
    """Consolidated RBAC audit findings."""
    project_id: str
    audit_run_id: str
    findings: List[RBACFindingDetail]


class RBACScoresResponse(BaseModel):
    """Audited project RBAC metrics scores."""
    project_id: str
    audit_run_id: str
    auth_score: float
    authz_score: float
    session_score: float
    overall_score: float


class RBACViolationDetail(BaseModel):
    """A detailed privilege escalation instance."""
    source_role: str
    target_route: str
    result: str  # e.g., "Accessed successfully" or "HTTP 200 OK"
    severity: str  # high | critical
    description: str


class RBACViolationsResponse(BaseModel):
    """List of all flagged authorization privilege boundary breaches."""
    project_id: str
    audit_run_id: str
    violations: List[RBACViolationDetail]


class RoleDiscoveryItem(BaseModel):
    """Item representing a dynamically discovered user role on the audited site."""
    role_name: str
    login_url: Optional[str] = None
    target_dashboard: Optional[str] = None
    confidence: float  # Score from 0.0 to 1.0
    description: str


class RoleDiscoveryResult(BaseModel):
    """Result containing all dynamically discovered roles and credentials paths."""
    roles: List[RoleDiscoveryItem]


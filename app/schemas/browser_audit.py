"""
Pydantic schemas for the Browser Audit Service.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class BrowserAuditRequest(BaseModel):
    """Request payload to initiate a browser audit."""
    url: str = Field(
        ...,
        description="Deployment URL to run the browser audit on",
        examples=["https://example.com"]
    )
    max_pages: int = Field(
        default=10,
        description="Maximum number of internal pages to discover and audit"
    )
    test_forms: bool = Field(
        default=True,
        description="If True, detect forms, fill them with test values, and simulate submissions"
    )
    rbac_enabled: bool = Field(
        default=False,
        description="Enable RBAC multi-role crawling and testing"
    )
    admin_url: Optional[str] = Field(None, description="Admin panel path")
    admin_email: Optional[str] = Field(None, description="Admin email")
    admin_password: Optional[str] = Field(None, description="Admin password")
    user_url: Optional[str] = Field(None, description="Regular user dashboard path")
    user_email: Optional[str] = Field(None, description="Regular user email")
    user_password: Optional[str] = Field(None, description="Regular user password")
    auth_required: bool = Field(
        default=False,
        description="Enable authenticated crawling and security testing"
    )
    login_url: Optional[str] = Field(None, description="Audited login path/URL")
    auth_email: Optional[str] = Field(None, description="Authentication email credentials")
    auth_password: Optional[str] = Field(None, description="Authentication password credentials")


class FormFieldTestResult(BaseModel):
    """Record of a single form field filled during testing."""
    field_name: str
    field_type: str
    value_filled: str


class FormSubmissionResult(BaseModel):
    """Detailed record of a form submission test."""
    form_id: Optional[str] = None
    form_action: Optional[str] = None
    fields_tested: List[FormFieldTestResult] = Field(default_factory=list)
    success: bool = Field(..., description="Whether the submission succeeded without console/network errors")
    outcome: str = Field(..., description="Description of the submission result or navigation change")


class PageAuditResult(BaseModel):
    """Findings collected for a single page during the crawl."""
    url: str = Field(..., description="The audited page URL")
    status_code: Optional[int] = Field(None, description="HTTP status code of the page load")
    role: str = Field(default="Guest", description="The role context under which this page was audited (Guest | User | Admin)")
    access_status: str = Field(default="allowed", description="Permission access classification (allowed | blocked | escalated)")
    desktop_screenshot_url: Optional[str] = Field(None, description="Shareable URL of the desktop screenshot")
    mobile_screenshot_url: Optional[str] = Field(None, description="Shareable URL of the mobile screenshot")
    console_errors: List[str] = Field(default_factory=list, description="Intercepted console errors or warnings")
    broken_links: List[str] = Field(default_factory=list, description="Broken links discovered on this page")
    form_submission_results: List[FormSubmissionResult] = Field(default_factory=list, description="Results of form submission tests")


class BrowserAuditResponse(BaseModel):
    """Full structured JSON response returned after browser auditing."""
    audit_id: str = Field(..., description="Unique ID for this audit run")
    target_url: str = Field(..., description="Target URL that was audited")
    pages_audited: List[PageAuditResult] = Field(default_factory=list)
    total_pages_visited: int = Field(..., description="Total number of pages successfully crawled")
    drive_folder_url: Optional[str] = Field(None, description="Google Drive directory URL containing all screenshots")
    errors: List[str] = Field(default_factory=list, description="Any non-fatal error warnings (e.g. Google Drive uploads)")
    auth_status: Optional[str] = Field(default="UNTESTED", description="Status of the authenticated audit testing")
    authenticated_pages_audited: List[PageAuditResult] = Field(default_factory=list, description="List of pages audited behind authentication")
    protected_routes_discovered: List[str] = Field(default_factory=list, description="List of discovered protected routes")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")

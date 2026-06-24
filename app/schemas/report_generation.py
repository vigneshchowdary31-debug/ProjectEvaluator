"""
Pydantic schemas for the Report Generation Service.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.schemas.prd import PRDAnalysisResult
from app.schemas.github import GithubAnalysisResultSchema
from app.schemas.browser_audit import BrowserAuditResponse
from app.schemas.requirement_matching import RequirementMatchingResult


class ReportGenerationRequest(BaseModel):
    """Request payload to trigger comprehensive report generation."""
    project_id: str = Field(
        ...,
        description="The project ID to link the generated report to"
    )
    prd_analysis: PRDAnalysisResult = Field(
        ...,
        description="Structured findings from the PRD Document analysis"
    )
    github_analysis: GithubAnalysisResultSchema = Field(
        ...,
        description="Structured findings from the GitHub codebase analysis"
    )
    browser_analysis: Optional[BrowserAuditResponse] = Field(
        None,
        description="Optional structured findings from the Browser crawl audit"
    )
    requirement_analysis: RequirementMatchingResult = Field(
        ...,
        description="Structured results from the Requirement Matching comparison"
    )

# ── Feature Matrix ──────────────────────────────────────────────────────────
class FeatureStatus(BaseModel):
    feature: str
    expected: bool
    implemented: str  # e.g., "Implemented", "Partial", "Missing", "Broken"
    status: str
    evidence: str

class CoreSection(BaseModel):
    features: List[FeatureStatus]
    coverage_percentage: float
    implemented_count: int
    partial_count: int
    missing_count: int
    broken_count: int

# ── Bug Findings ────────────────────────────────────────────────────────────
class BugFinding(BaseModel):
    severity: str  # Critical, High, Medium, Low
    title: str
    description: str
    page: str
    steps_to_reproduce: str
    expected_behaviour: str
    actual_behaviour: str
    evidence_screenshot: Optional[str] = None

# ── Security & Performance ──────────────────────────────────────────────────
class SecurityFinding(BaseModel):
    severity: str
    description: str
    recommendation: str

class SecuritySection(BaseModel):
    authentication_status: str
    authorization_status: str
    jwt_validation: str
    session_handling: str
    secrets_exposure: str
    environment_variables: str
    dependency_vulnerabilities: str
    owasp_findings: List[SecurityFinding]

class PerformanceMetrics(BaseModel):
    load_time_ms: float
    first_contentful_paint_ms: float
    largest_contentful_paint_ms: float
    total_requests: int
    bundle_size_kb: float
    performance_findings: List[str]

# ── RBAC & Auth ─────────────────────────────────────────────────────────────
class AuthAccessTest(BaseModel):
    test_name: str  # e.g., "Login Success", "Dashboard Access"
    status: str
    evidence_screenshot: Optional[str] = None

class RoleMatrix(BaseModel):
    role: str
    permissions: List[str]

class PageAccessMatrix(BaseModel):
    page: str
    allowed_roles: List[str]

class RBACSection(BaseModel):
    access_tests: List[AuthAccessTest]
    role_matrix: List[RoleMatrix]
    page_access_matrix: List[PageAccessMatrix]
    unauthorized_access_tests: List[str]
    authorization_score: float
    rbac_score: float

# ── Evidence Gallery ────────────────────────────────────────────────────────
class ScreenshotEvidence(BaseModel):
    category: str  # Desktop, Tablet, Mobile, Homepage, Dashboard, etc.
    page: str
    action: str
    result: str
    timestamp: str
    screenshot_url: str

class EvidenceSection(BaseModel):
    screenshots: List[ScreenshotEvidence]

# ── Recommendations ─────────────────────────────────────────────────────────
class Recommendation(BaseModel):
    priority: str  # Critical, High, Medium, Low
    problem: str
    impact: str
    recommended_fix: str
    estimated_effort: str

# ── Root Project Audit Report Schema ────────────────────────────────────────
class ProjectAuditReportSchema(BaseModel):
    """The unified, single source of truth report for a project."""
    
    # 1. Executive Summary
    project_name: str
    student_name: str
    company_name: str
    audit_date: str
    audit_version: str
    audit_duration_seconds: int
    
    overall_score: float
    status: str  # Production Ready, Ready With Minor Fixes, Needs Major Improvements, Incomplete, Failed
    
    requirement_completion_score: float
    security_score: float
    performance_score: float
    uiux_score: float
    code_quality_score: float
    
    project_description: str
    technology_stack: Dict[str, str]  # Frontend, Backend, Database, Hosting, Authentication, RBAC
    
    # 2. Repository Information & Deployment
    deploy_url_reachable: bool
    http_status_code: int
    ssl_certificate_valid: bool
    page_load_time_ms: float
    mobile_responsive: bool
    accessibility_score: float
    deployment_status: str  # "Deployment Working" or "Deployment Broken"
    
    repository_reachable: bool
    default_branch: str
    last_commit_hash: str
    last_commit_date: str
    contributors_count: int
    readme_exists: bool
    license_exists: bool
    package_files_found: bool
    tech_stack_detected: str
    repository_structure_score: float

    # 3. Core Section
    core_section: CoreSection
    
    # 4. Bug Findings
    bugs: List[BugFinding]
    
    # 5. Security & Performance
    security: SecuritySection
    performance: PerformanceMetrics
    
    # 6. RBAC
    rbac: Optional[RBACSection] = None
    
    # 7. Evidence
    evidence: EvidenceSection
    
    # 8. Recommendations
    recommendations: List[Recommendation]
    
    # 9. Final Verdict
    remaining_work_percentage: float
    estimated_missing_features: int
    critical_issues_count: int
    score_explanation: str


class ReportGenerationResponse(BaseModel):
    """Detailed response returned after saving reports to database."""
    id: str = Field(..., description="Unique ID of the generated project report record")
    project_id: str = Field(..., description="Project ID linked to the report")
    report: ProjectAuditReportSchema
    report_url: Optional[str] = Field(None, description="Public Web Report URL (Supabase Storage)")
    pdf_url: Optional[str] = Field(None, description="PDF Report URL (Supabase Storage)")
    json_url: Optional[str] = Field(None, description="JSON Report URL (Supabase Storage)")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")

    model_config = {"from_attributes": True}

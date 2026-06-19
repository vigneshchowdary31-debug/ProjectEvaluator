"""
Pydantic schemas for the Report Generation Service.
"""

from typing import List, Optional
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


class StudentReportSchema(BaseModel):
    """Educational audit report tailored for student developers."""
    completion_percentage: float = Field(
        ...,
        description="Percentage of requirements successfully implemented (0.0 to 100.0)"
    )
    features_implemented: List[str] = Field(
        default_factory=list,
        description="List of fully or partially implemented features with educational verification notes"
    )
    missing_features: List[str] = Field(
        default_factory=list,
        description="List of missing features with guidance on how they should have been designed"
    )
    security_findings: List[str] = Field(
        default_factory=list,
        description="Detailed security findings explaining the vulnerabilities, code risks, and how to fix them"
    )
    ui_findings: List[str] = Field(
        default_factory=list,
        description="Detailed UI/UX evaluation matching expected pages, touch interactions, or routing errors"
    )
    code_quality_findings: List[str] = Field(
        default_factory=list,
        description="Detailed review of coding styles, modularity, layering, and database queries"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Step-by-step learning recommendations to improve the project codebase"
    )
    educational_notes: str = Field(
        ...,
        description="Comprehensive tutoring notes on best practices, architecture theory, and software engineering principles"
    )


class CompanyReportSchema(BaseModel):
    """Commercial-grade audit report tailored for corporate stakeholders."""
    completion_percentage: float = Field(
        ...,
        description="Percentage of requirements successfully implemented (0.0 to 100.0)"
    )
    features_implemented: List[str] = Field(
        default_factory=list,
        description="Summary of implemented business capabilities mapped to requirements"
    )
    missing_features: List[str] = Field(
        default_factory=list,
        description="Summary of missing business capabilities and product gaps"
    )
    security_findings: List[str] = Field(
        default_factory=list,
        description="High-level security risk profile, dependency alerts, and potential compliance liabilities"
    )
    ui_findings: List[str] = Field(
        default_factory=list,
        description="UI/UX branding evaluation, usability scores, and screenshot validation outcomes"
    )
    code_quality_findings: List[str] = Field(
        default_factory=list,
        description="Maintainability ratings, dependency stability, and system complexity checks"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Strategic recommendations regarding readiness for release, refactoring investments, and technical debt"
    )
    executive_summary: str = Field(
        ...,
        description="Executive summary profiling project health, risk level, and go-live capability assessment"
    )


class ReportGenerationResponse(BaseModel):
    """Detailed response returned after saving reports to SQLite."""
    id: str = Field(..., description="Unique ID of the generated report record")
    project_id: str = Field(..., description="Project ID linked to the report")
    completion_percentage: float = Field(..., description="Calculated project completion percentage")
    student_report: StudentReportSchema
    company_report: CompanyReportSchema
    created_at: str = Field(..., description="ISO 8601 creation timestamp")

    model_config = {"from_attributes": True}

"""
Pydantic schemas for the Requirement Matching Service.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.prd import PRDAnalysisResult
from app.schemas.github import GithubAnalysisResultSchema
from app.schemas.browser_audit import BrowserAuditResponse


class RequirementMatchingRequest(BaseModel):
    """Request payload containing findings from PRD, GitHub, and Browser audits."""
    prd_findings: PRDAnalysisResult = Field(
        ...,
        description="Structured findings from the PRD Document analysis"
    )
    github_findings: GithubAnalysisResultSchema = Field(
        ...,
        description="Structured findings from the GitHub codebase repository analysis"
    )
    browser_findings: Optional[BrowserAuditResponse] = Field(
        None,
        description="Optional structured findings from the Playwright browser crawl"
    )


class FeatureMatchInfo(BaseModel):
    """Details of a requirement that is fully implemented."""
    name: str = Field(..., description="Feature name")
    description: str = Field(..., description="Feature description from PRD")
    evidence: str = Field(..., description="Evidence of implementation found in GitHub code or Browser crawl findings")
    matched_files: List[str] = Field(default_factory=list, description="Relevant source files showing the implementation")


class PartialFeatureMatchInfo(BaseModel):
    """Details of a requirement that is partially implemented."""
    name: str = Field(..., description="Feature name")
    description: str = Field(..., description="Feature description from PRD")
    implemented_details: str = Field(..., description="What part of the feature is implemented")
    missing_details: str = Field(..., description="What part of the feature is missing or incorrect")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations to complete the implementation")


class MissingFeatureInfo(BaseModel):
    """Details of a requirement that is completely missing."""
    name: str = Field(..., description="Feature name")
    description: str = Field(..., description="Feature description from PRD")
    priority: str = Field(..., description="Expected feature priority (must_have, should_have, nice_to_have)")


class RequirementMatchingResult(BaseModel):
    """The structured gap analysis results comparing PRD requirements with implementation findings."""
    implemented_features: List[FeatureMatchInfo] = Field(
        default_factory=list,
        description="List of features determined to be fully implemented"
    )
    partially_implemented_features: List[PartialFeatureMatchInfo] = Field(
        default_factory=list,
        description="List of features determined to be partially implemented"
    )
    missing_features: List[MissingFeatureInfo] = Field(
        default_factory=list,
        description="List of expected features that are completely missing"
    )
    confidence_score: float = Field(
        ...,
        description="Confidence score of the assessment as a float from 0.0 to 1.0",
        ge=0.0,
        le=1.0
    )
    summary: str = Field(
        ...,
        description="Executive summary of the matching audit and gap analysis findings"
    )

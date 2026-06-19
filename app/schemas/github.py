"""
Pydantic models for GitHub Repository analysis.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GithubAnalysisRequest(BaseModel):
    """Request schema for analyzing a GitHub repository."""
    repo_url: str = Field(
        ...,
        description="Public GitHub repository URL to analyze",
        examples=["https://github.com/vigneshchowdary31-debug/ProjectEvaluator"]
    )
    force_refresh: bool = Field(
        default=False,
        description="If True, bypasses cache and forces re-fetching and re-analysis"
    )


class PageInfo(BaseModel):
    """Information about a page or primary endpoint found in the repository."""
    name: str = Field(..., description="Name of the page or route")
    route: Optional[str] = Field(None, description="URL path or route (e.g. '/login', 'GET /users')")
    file_path: Optional[str] = Field(None, description="Path to the file defining this page/route")
    description: Optional[str] = Field(None, description="What this page or route does")


class UIComponentInfo(BaseModel):
    """Information about a reusable UI component or software building block."""
    name: str = Field(..., description="Component name")
    type: str = Field(..., description="Component type (e.g., button, repository, card, context, modal)")
    file_path: Optional[str] = Field(None, description="Path to the component file")
    description: Optional[str] = Field(None, description="What this component is used for")


class SecuritySeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SecurityIssue(BaseModel):
    """A detected security concern or potential vulnerability."""
    severity: SecuritySeverity = Field(..., description="Severity of the issue")
    issue: str = Field(..., description="Title/summary of the security concern")
    file_path: Optional[str] = Field(None, description="File path containing the issue")
    description: str = Field(..., description="Detailed description and remedy suggestion")


class ArchitectureRating(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class ArchitectureQuality(BaseModel):
    """Assessment of the repository's code architecture."""
    rating: ArchitectureRating = Field(..., description="Architectural rating")
    strengths: List[str] = Field(default_factory=list, description="Strengths of the architecture")
    weaknesses: List[str] = Field(default_factory=list, description="Weaknesses or architectural gaps")
    recommendations: List[str] = Field(default_factory=list, description="Concrete improvement tips")


class GithubAnalysisResultSchema(BaseModel):
    """The structured data schema Gemini must return for a GitHub repository."""
    technologies: List[str] = Field(default_factory=list, description="Languages and platforms used (e.g., Python, TypeScript)")
    frameworks: List[str] = Field(default_factory=list, description="Frameworks and major libraries (e.g., FastAPI, React, SQLAlchemy)")
    pages: List[PageInfo] = Field(default_factory=list, description="Main pages or endpoints detected")
    components: List[UIComponentInfo] = Field(default_factory=list, description="Architectural components or modular UI elements")
    folder_structure: Dict[str, Any] = Field(default_factory=dict, description="Nested dictionary representing the folder layout")
    security_issues: List[SecurityIssue] = Field(default_factory=list, description="List of potential security concerns")
    architecture_quality: ArchitectureQuality = Field(..., description="Architecture quality assessment")


class GithubAnalysisResponse(BaseModel):
    """API response returned to the client."""
    repo_url: str = Field(..., description="The analyzed repository URL")
    commit_sha: Optional[str] = Field(None, description="The commit SHA that was analyzed")
    is_cached: bool = Field(..., description="Whether the response came from database cache")
    analyzed_at: str = Field(..., description="ISO 8601 timestamp of the analysis")
    analysis: GithubAnalysisResultSchema = Field(..., description="Detailed structured analysis results")

    model_config = {"from_attributes": True}

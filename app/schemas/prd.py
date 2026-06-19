"""
Pydantic models for PRD (Product Requirements Document) analysis.

Defines the structured output schema that Gemini must return,
along with request/response models for the API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


# ─── Granular PRD Components ────────────────────────────────────────────────


class UIComponent(BaseModel):
    """A single UI component within a page."""
    name: str = Field(..., description="Component name (e.g., 'Header', 'Sidebar', 'DataTable')")
    type: str = Field(..., description="Component type (e.g., 'navigation', 'display', 'input', 'modal')")
    description: str = Field(..., description="What this component does")


class Page(BaseModel):
    """A page/screen described in the PRD."""
    name: str = Field(..., description="Page name (e.g., 'Dashboard', 'Login', 'Settings')")
    route: Optional[str] = Field(None, description="Suggested route path (e.g., '/dashboard')")
    description: str = Field(..., description="Purpose and behavior of this page")
    components: List[UIComponent] = Field(default_factory=list, description="UI components on this page")
    connected_pages: List[str] = Field(default_factory=list, description="Names of pages this page links to")


class FeaturePriority(str, Enum):
    MUST_HAVE = "must_have"
    SHOULD_HAVE = "should_have"
    NICE_TO_HAVE = "nice_to_have"


class Feature(BaseModel):
    """A feature described in the PRD."""
    name: str = Field(..., description="Feature name")
    description: str = Field(..., description="Detailed feature description")
    priority: FeaturePriority = Field(
        default=FeaturePriority.SHOULD_HAVE,
        description="Feature priority level"
    )
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="List of acceptance criteria for this feature"
    )
    related_pages: List[str] = Field(
        default_factory=list,
        description="Pages where this feature appears"
    )


class FormFieldType(str, Enum):
    TEXT = "text"
    EMAIL = "email"
    PASSWORD = "password"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    TEXTAREA = "textarea"
    FILE = "file"
    TOGGLE = "toggle"
    OTHER = "other"


class FormField(BaseModel):
    """A single field within a form."""
    name: str = Field(..., description="Field name / label")
    field_type: FormFieldType = Field(..., description="Input type")
    required: bool = Field(default=False, description="Whether the field is required")
    validation_rules: List[str] = Field(
        default_factory=list,
        description="Validation rules (e.g., 'min 8 chars', 'valid email')"
    )
    options: List[str] = Field(
        default_factory=list,
        description="Options for select/radio/checkbox fields"
    )


class Form(BaseModel):
    """A form described in the PRD."""
    name: str = Field(..., description="Form name (e.g., 'Registration Form', 'Create Project')")
    description: str = Field(..., description="What this form is for")
    page: Optional[str] = Field(None, description="Page where this form appears")
    fields: List[FormField] = Field(default_factory=list, description="Form fields")
    submit_action: Optional[str] = Field(None, description="What happens on submission")


class UserFlowStep(BaseModel):
    """A single step in a user flow."""
    step_number: int = Field(..., description="Step order (1-indexed)")
    action: str = Field(..., description="What the user does")
    page: Optional[str] = Field(None, description="Page where this step occurs")
    expected_result: Optional[str] = Field(None, description="Expected system response")


class UserFlow(BaseModel):
    """A user flow / user journey described in the PRD."""
    name: str = Field(..., description="Flow name (e.g., 'User Registration', 'Checkout')")
    description: str = Field(..., description="High-level description of the flow")
    actor: str = Field(default="User", description="Who performs this flow")
    preconditions: List[str] = Field(default_factory=list, description="Required preconditions")
    steps: List[UserFlowStep] = Field(default_factory=list, description="Ordered steps")
    postconditions: List[str] = Field(default_factory=list, description="State after flow completes")


# ─── Top-level PRD Analysis Result ──────────────────────────────────────────


class PRDAnalysisResult(BaseModel):
    """
    The structured output returned by Gemini after analyzing a PRD.
    This is the core schema that Gemini must conform to.
    """
    pages: List[Page] = Field(default_factory=list, description="All pages/screens identified")
    features: List[Feature] = Field(default_factory=list, description="All features identified")
    forms: List[Form] = Field(default_factory=list, description="All forms identified")
    user_flows: List[UserFlow] = Field(default_factory=list, description="All user flows identified")


# ─── API Request / Response ─────────────────────────────────────────────────


class PRDAnalysisRequest(BaseModel):
    """Request body for PRD analysis endpoint."""
    google_doc_url: str = Field(
        ...,
        description="Public Google Docs URL to analyze",
        examples=["https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit"]
    )
    project_id: Optional[str] = Field(
        None,
        description="Optional project ID to associate the analysis with"
    )


class PRDAnalysisResponse(BaseModel):
    """Full response for PRD analysis endpoint."""
    id: str = Field(..., description="Unique analysis ID")
    google_doc_url: str
    document_title: Optional[str] = Field(None, description="Extracted document title")
    analysis: PRDAnalysisResult
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str

    model_config = {"from_attributes": True}


class PRDAnalysisSummary(BaseModel):
    """Lightweight summary of a PRD analysis."""
    id: str
    google_doc_url: str
    document_title: Optional[str]
    page_count: int
    feature_count: int
    form_count: int
    user_flow_count: int
    created_at: str

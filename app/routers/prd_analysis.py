"""
PRD Analysis router — analyze Product Requirements Documents via Google Docs URL.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.prd import (
    PRDAnalysisRequest,
    PRDAnalysisResponse,
    PRDAnalysisResult,
)
from app.services.prd_analysis import PRDAnalysisService

router = APIRouter(prefix="/api/v1/prd", tags=["PRD Analysis"])


@router.post(
    "/analyze",
    response_model=PRDAnalysisResponse,
    summary="Analyze a PRD from a Google Docs URL",
    description=(
        "Downloads a public Google Doc, extracts text, sends it to Gemini AI, "
        "and returns a structured analysis with pages, features, forms, and user flows."
    ),
)
def analyze_prd(
    request: PRDAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyze a Product Requirements Document.

    **Input**: A public Google Docs URL.

    **Process**:
    1. Download the document
    2. Extract text content
    3. Send to Gemini AI for analysis

    **Output**: Structured JSON with pages, features, forms, and user_flows.
    """
    service = PRDAnalysisService()
    return service.analyze(request)


@router.post(
    "/validate",
    response_model=PRDAnalysisResult,
    summary="Validate a PRD analysis result",
    description="Validate a raw PRD analysis JSON against the expected schema.",
)
def validate_prd_analysis(
    data: PRDAnalysisResult,
    _: User = Depends(get_current_user),
):
    """
    Validate a PRD analysis result against the Pydantic schema.

    Useful for testing or re-validating cached/stored analysis results.
    Returns the validated data if valid, or a 422 error with details if not.
    """
    return data

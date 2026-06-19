"""
Requirement Matching Router — matches PRD requirements with codebase and web audit findings.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.requirement_matching import (
    RequirementMatchingRequest,
    RequirementMatchingResult,
)
from app.services.requirement_matching import RequirementMatchingService

router = APIRouter(prefix="/api/v1/requirements", tags=["Requirement Matching"])


@router.post(
    "/match",
    response_model=RequirementMatchingResult,
    summary="Compare PRD requirements with implementation findings",
    description=(
        "Sends parsed PRD specifications, GitHub codebase structure, and optional Browser audit findings "
        "to Gemini AI to compare and generate a gap analysis. Returns lists of fully implemented, "
        "partially implemented, and missing features alongside a confidence score."
    ),
)
def match_requirements(
    request: RequirementMatchingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Perform a requirement matching gap analysis.
    
    **Inputs**: PRD Analysis JSON, GitHub Repository Analysis JSON, and (optional) Playwright Browser Audit JSON.
    """
    service = RequirementMatchingService()
    return service.match(request)

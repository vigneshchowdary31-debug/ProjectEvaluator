"""
Requirement Matching Service — compares PRD requirements with implementation findings via Gemini.
"""

import logging
from typing import Optional

from app.schemas.requirement_matching import (
    RequirementMatchingRequest,
    RequirementMatchingResult,
)
from app.services.llm.llm_service import LLMService, LLMError
from app.utils.exceptions import BadRequestException

logger = logging.getLogger(__name__)


class RequirementMatchingService:
    """Orchestrates comparison of specifications and code/web findings using LLMs."""

    def __init__(self, audit_run=None):
        self.llm = LLMService(audit_run=audit_run)

    def match(self, request: RequirementMatchingRequest) -> RequirementMatchingResult:
        logger.info("Starting requirement matching analysis")
        
        try:
            result = self.llm.analyze_requirement_matching(
                prd=request.prd_findings,
                github=request.github_findings,
                browser=request.browser_findings
            )
            return result
        except LLMError as e:
            logger.error("Requirements matching analysis failed: %s", str(e))
            raise BadRequestException(detail=f"Gap analysis failed: {str(e)}")

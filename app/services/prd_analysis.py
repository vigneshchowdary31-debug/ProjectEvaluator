"""
PRD Analysis Service — orchestrates parsing + Gemini analysis.

This is the high-level service that coordinates:
1. Downloading and extracting text from Google Docs
2. Sending text to Gemini for analysis
3. Validating and storing results
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.schemas.prd import (
    PRDAnalysisRequest,
    PRDAnalysisResponse,
    PRDAnalysisResult,
    PRDAnalysisSummary,
)
from app.services.llm.llm_service import LLMService, LLMError
from app.services.prd_parser import PRDParserService, ParserError
from app.utils.exceptions import BadRequestException, NotFoundException

logger = logging.getLogger(__name__)


class PRDAnalysisError(Exception):
    """Raised when PRD analysis fails."""
    pass


class PRDAnalysisService:
    """
    Orchestrates the full PRD analysis pipeline:
    URL → Download → Extract Text → LLM → Validated Result
    """

    def __init__(self, audit_run=None):
        self.parser = PRDParserService()
        self.llm = LLMService(audit_run=audit_run)

    def analyze(self, request: PRDAnalysisRequest) -> PRDAnalysisResponse:
        """
        Run the full PRD analysis pipeline.

        Args:
            request: Contains the Google Doc URL and optional project_id.

        Returns:
            PRDAnalysisResponse with structured analysis results.

        Raises:
            BadRequestException: If the URL is invalid or the document can't be accessed.
        """
        analysis_id = str(uuid.uuid4())
        logger.info("Starting PRD analysis %s for URL: %s", analysis_id, request.google_doc_url)

        import time
        start_time = time.time()
        
        # ── Step 1: Download & extract text ─────────────────────────────
        try:
            document_text, document_title = self.parser.extract_text(request.google_doc_url)
            doc_id = self.parser.extract_doc_id(request.google_doc_url)
        except ParserError as e:
            logger.error("Parser failed for analysis %s: %s", analysis_id, str(e))
            raise BadRequestException(detail=str(e))

        logger.info(
            "Analysis %s — Document ID: %s, extracted %d chars, title: '%s'",
            analysis_id,
            doc_id,
            len(document_text),
            document_title or "Untitled",
        )

        # ── Step 2: Analyze with LLM ─────────────────────────────────
        try:
            analysis_result = self.llm.analyze_prd(document_text)
        except LLMError as e:
            logger.error("LLM failed for analysis %s: %s", analysis_id, str(e))
            raise BadRequestException(detail=f"AI analysis failed: {str(e)}")

        provider_used = self.llm.current_provider.provider_name if hasattr(self.llm, "current_provider") and self.llm.current_provider else "gemini"
        duration = time.time() - start_time

        # ── Step 3: Build response ──────────────────────────────────────
        response = PRDAnalysisResponse(
            id=analysis_id,
            google_doc_url=request.google_doc_url,
            document_title=document_title,
            analysis=analysis_result,
            metadata={
                "document_length": len(document_text),
                "project_id": request.project_id,
                "model": provider_used,
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(
            "[PRD DIAGNOSTICS] Analysis %s completed in %.2fs | URL: %s | Doc ID: %s | "
            "Status: Downloaded | Text Length: %d chars | Provider: %s | "
            "Features: %d | Pages: %d | Forms: %d | Flows: %d",
            analysis_id,
            duration,
            request.google_doc_url,
            doc_id,
            len(document_text),
            provider_used,
            len(analysis_result.features),
            len(analysis_result.pages),
            len(analysis_result.forms),
            len(analysis_result.user_flows)
        )

        return response

    @staticmethod
    def build_summary(response: PRDAnalysisResponse) -> PRDAnalysisSummary:
        """Build a lightweight summary from a full analysis response."""
        return PRDAnalysisSummary(
            id=response.id,
            google_doc_url=response.google_doc_url,
            document_title=response.document_title,
            page_count=len(response.analysis.pages),
            feature_count=len(response.analysis.features),
            form_count=len(response.analysis.forms),
            user_flow_count=len(response.analysis.user_flows),
            created_at=response.created_at,
        )

"""
PRD Parser Service — downloads Google Docs and extracts plain text.

Supports public Google Doc URLs by converting them to the export/text endpoint.
"""

import logging
import re
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs

import httpx

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
GOOGLE_DOCS_EXPORT_BASE = "https://docs.google.com/document/d/{doc_id}/export?format=txt"
GOOGLE_DOCS_TITLE_URL = "https://docs.google.com/document/d/{doc_id}/edit"

# Regex patterns to extract the document ID from various Google Docs URL formats
DOC_ID_PATTERNS = [
    re.compile(r"/document/d/([a-zA-Z0-9_-]+)"),       # Standard URL
    re.compile(r"/document/u/\d+/d/([a-zA-Z0-9_-]+)"),  # URL with user index
    re.compile(r"id=([a-zA-Z0-9_-]+)"),                  # Query param format
]

# ── Timeout & limits ────────────────────────────────────────────────────────
HTTP_TIMEOUT = 30.0  # seconds
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024  # 5 MB


class ParserError(Exception):
    """Raised when document parsing fails."""
    pass


class PRDParserService:
    """Download and extract text from public Google Docs."""

    @staticmethod
    def extract_doc_id(url: str) -> str:
        """
        Extract the Google Document ID from a URL.

        Supports formats:
        - https://docs.google.com/document/d/DOC_ID/edit
        - https://docs.google.com/document/d/DOC_ID/preview
        - https://docs.google.com/document/u/0/d/DOC_ID/edit
        - https://docs.google.com/document/d/DOC_ID

        Raises:
            ParserError: If no document ID can be extracted.
        """
        for pattern in DOC_ID_PATTERNS:
            match = pattern.search(url)
            if match:
                doc_id = match.group(1)
                logger.debug("Extracted document ID: %s", doc_id)
                return doc_id

        raise ParserError(
            f"Could not extract Google Document ID from URL: {url}. "
            "Ensure the URL is a valid Google Docs link (OneDrive, Notion, etc. are not supported)."
        )

    @staticmethod
    def _build_export_url(doc_id: str) -> str:
        """Build the plaintext export URL for a Google Doc."""
        return GOOGLE_DOCS_EXPORT_BASE.format(doc_id=doc_id)

    def download_document(self, url: str) -> Tuple[str, Optional[str]]:
        """
        Download a public Google Doc and return its text content.

        Args:
            url: Public Google Docs URL.

        Returns:
            Tuple of (extracted_text, document_title).

        Raises:
            ParserError: If download or extraction fails.
        """
        doc_id = self.extract_doc_id(url)
        export_url = self._build_export_url(doc_id)

        logger.info("Downloading document %s from: %s", doc_id, export_url)

        try:
            with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
                response = client.get(export_url)
                response.raise_for_status()
        except httpx.TimeoutException:
            raise ParserError(
                f"Timeout while downloading document (>{HTTP_TIMEOUT}s). "
                "The document may be too large or the network is slow."
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ParserError(
                    "Document not found. Ensure the URL is correct and the document is public."
                )
            elif e.response.status_code == 403:
                raise ParserError(
                    "Access denied. Ensure the document is shared as 'Anyone with the link can view'."
                )
            else:
                raise ParserError(
                    f"HTTP error {e.response.status_code} while downloading document."
                )
        except httpx.RequestError as e:
            raise ParserError(f"Network error while downloading document: {str(e)}")

        # ── Validate content ────────────────────────────────────────────
        content_length = len(response.content)
        if content_length > MAX_DOCUMENT_SIZE:
            raise ParserError(
                f"Document is too large ({content_length / 1024 / 1024:.1f} MB). "
                f"Maximum allowed size is {MAX_DOCUMENT_SIZE / 1024 / 1024:.0f} MB."
            )

        raw_text = response.text.strip()
        if not raw_text:
            raise ParserError("Document appears to be empty.")

        # If Google redirects to a sign-in page, the content will be HTML instead of text.
        lower_text = raw_text.lstrip().lower()
        if lower_text.startswith("<!doctype html") or lower_text.startswith("<html"):
            raise ParserError(
                "Access denied. The document is private or requires authentication. "
                "Please ensure the Google Doc is shared as 'Anyone with the link can view'."
            )

        # ── Extract title (first non-empty line) ────────────────────────
        title = self._extract_title(raw_text)

        logger.info(
            "Successfully downloaded document: '%s' (%d chars)",
            title or "Untitled",
            len(raw_text),
        )

        return raw_text, title

    @staticmethod
    def _extract_title(text: str) -> Optional[str]:
        """Extract the document title from the first non-empty line."""
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped:
                # Cap title length
                return stripped[:200] if len(stripped) > 200 else stripped
        return None

    def extract_text(self, url: str) -> Tuple[str, Optional[str]]:
        """
        High-level method: download + extract text from a Google Doc URL.

        Returns:
            Tuple of (cleaned_text, document_title).
        """
        raw_text, title = self.download_document(url)
        cleaned = self._clean_text(raw_text)
        return cleaned, title

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Clean extracted text:
        - Normalize whitespace
        - Remove excessive blank lines
        - Strip BOM and zero-width characters
        """
        # Remove BOM and zero-width chars
        text = text.replace("\ufeff", "").replace("\u200b", "")

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Collapse 3+ consecutive newlines into 2
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Strip trailing whitespace per line
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()

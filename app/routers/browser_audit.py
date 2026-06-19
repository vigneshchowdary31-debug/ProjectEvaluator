"""
Browser Audit Router — triggers browser audit runs using Playwright.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.browser_audit import BrowserAuditRequest, BrowserAuditResponse
from app.services.browser_audit import BrowserAuditService

router = APIRouter(prefix="/api/v1/browser", tags=["Browser Audit"])


@router.post(
    "/audit",
    response_model=BrowserAuditResponse,
    summary="Run a browser audit on a deployment URL",
    description=(
        "Launches a headless browser to open the deployment website, discovers links, "
        "crawls internal pages, captures desktop and mobile screenshots, checks for console errors, "
        "detects broken links, tests form inputs, and uploads captured screenshots to Google Drive."
    ),
)
async def run_browser_audit(
    request: BrowserAuditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Triggers an async browser audit using Playwright.
    
    **Scope**: Crawls up to `max_pages` pages within the same domain. Emulates viewport environments.
    """
    service = BrowserAuditService()
    return await service.audit(request)

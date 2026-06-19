import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.main import app
from app.dependencies import get_current_user, get_db
from app.schemas.browser_audit import BrowserAuditResponse, PageAuditResult
from app.services.browser_audit import BrowserAuditService

client = TestClient(app)

# Dummy user fixture
class DummyUser:
    id = "test-user-id"
    email = "test@example.com"
    is_admin = False
    is_active = True

def mock_get_current_user():
    return DummyUser()

def mock_get_db():
    return MagicMock()

# Setup overrides for this test suite
@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db] = mock_get_db
    
    with patch("app.services.gemini.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.GEMINI_API_KEY = "dummy_key"
        mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
        mock_settings.GOOGLE_CREDENTIALS_JSON = ""
        mock_settings.GOOGLE_DRIVE_FOLDER_ID = ""
        mock_get_settings.return_value = mock_settings
        
        with patch("google.genai.Client"):
            yield
            
    app.dependency_overrides.clear()

@pytest.mark.anyio
@patch("app.services.browser_audit.async_playwright")
@patch("app.services.browser_audit.GoogleDriveService")
async def test_audit_flow(mock_drive_service_class, mock_playwright):
    # Mock Google Drive Service
    mock_drive = MagicMock()
    mock_drive.enabled = True
    mock_drive.create_folder.return_value = "folder-123"
    mock_drive.upload_screenshot.return_value = "https://drive.google.com/screenshot"
    mock_drive.get_folder_link.return_value = "https://drive.google.com/folder"
    mock_drive_service_class.return_value = mock_drive

    # Mock Playwright structures
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.screenshot = AsyncMock()
    mock_page.query_selector_all.return_value = []
    
    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_context.close = AsyncMock()
    
    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context
    mock_browser.close = AsyncMock()
    
    # Configure mock playwright launch
    mock_playwright_inst = AsyncMock()
    mock_playwright_inst.chromium.launch.return_value = mock_browser
    mock_playwright.return_value.__aenter__.return_value = mock_playwright_inst

    service = BrowserAuditService()
    # Force mock drive to be enabled
    service.drive_service = mock_drive
    
    # Request body
    from app.schemas.browser_audit import BrowserAuditRequest
    req = BrowserAuditRequest(url="https://testwebsite.com", max_pages=1, test_forms=False)
    
    response = await service.audit(req)
    
    assert response.target_url == "https://testwebsite.com"
    assert response.total_pages_visited == 1
    assert response.drive_folder_url == "https://drive.google.com/folder"
    assert response.pages_audited[0].desktop_screenshot_url == "https://drive.google.com/screenshot"
    
    assert mock_page.goto.call_count == 2
    assert mock_page.screenshot.call_count == 2
    mock_browser.close.assert_called_once()


@patch("app.services.browser_audit.BrowserAuditService.audit")
def test_audit_router_endpoint(mock_audit):
    # Setup mock response
    mock_response = BrowserAuditResponse(
        audit_id="audit-uuid",
        target_url="https://example.com",
        pages_audited=[
            PageAuditResult(
                url="https://example.com",
                status_code=200,
                desktop_screenshot_url="https://drive.google.com/screenshot",
                mobile_screenshot_url="https://drive.google.com/screenshot-mob",
                console_errors=[],
                broken_links=[],
                form_submission_results=[]
            )
        ],
        total_pages_visited=1,
        drive_folder_url="https://drive.google.com/folder",
        errors=[],
        created_at=datetime.now(timezone.utc).isoformat()
    )
    # Async mock for router call
    mock_audit.return_value = mock_response

    payload = {
        "url": "https://example.com",
        "max_pages": 5,
        "test_forms": True
    }
    
    response = client.post("/api/v1/browser/audit", json=payload)
    
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["audit_id"] == "audit-uuid"
    assert len(json_data["pages_audited"]) == 1
    assert json_data["pages_audited"][0]["url"] == "https://example.com"

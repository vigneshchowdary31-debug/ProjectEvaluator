import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.prd import PRDAnalysisResponse, PRDAnalysisResult

# Client fixture
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

# Setup dependency overrides for all router tests
@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db] = mock_get_db
    
    with patch("app.services.gemini.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.GEMINI_API_KEY = "dummy_key_for_testing"
        mock_settings.GEMINI_MODEL = "gemini-2.5-flash"
        mock_get_settings.return_value = mock_settings
        
        with patch("google.genai.Client"):
            yield
            
    app.dependency_overrides.clear()


@patch("app.services.prd_analysis.PRDAnalysisService.analyze")
def test_analyze_prd_endpoint(mock_analyze):
    # Setup mock response
    mock_response = PRDAnalysisResponse(
        id="test-analysis-uuid",
        google_doc_url="https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit",
        document_title="Sample PRD Title",
        analysis=PRDAnalysisResult(pages=[], features=[], forms=[], user_flows=[]),
        metadata={"project_id": None},
        created_at="2026-06-20T00:00:00Z"
    )
    mock_analyze.return_value = mock_response

    # Call endpoint
    payload = {
        "google_doc_url": "https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit",
        "project_id": None
    }
    response = client.post("/api/v1/prd/analyze", json=payload)
    
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["id"] == "test-analysis-uuid"
    assert json_data["document_title"] == "Sample PRD Title"
    mock_analyze.assert_called_once()

def test_validate_prd_endpoint_success():
    payload = {
        "pages": [
            {
                "name": "Login",
                "route": "/login",
                "description": "Login page description",
                "components": [],
                "connected_pages": []
            }
        ],
        "features": [],
        "forms": [],
        "user_flows": []
    }
    
    response = client.post("/api/v1/prd/validate", json=payload)
    assert response.status_code == 200
    assert len(response.json()["pages"]) == 1

def test_validate_prd_endpoint_invalid_schema():
    # Invalid page payload (missing 'description')
    payload = {
        "pages": [
            {
                "name": "Login",
                "route": "/login"
            }
        ],
        "features": [],
        "forms": [],
        "user_flows": []
    }
    
    response = client.post("/api/v1/prd/validate", json=payload)
    assert response.status_code == 422

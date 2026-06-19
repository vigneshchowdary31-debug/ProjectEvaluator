import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.dependencies import get_current_user, get_db
from app.schemas.requirement_matching import RequirementMatchingResult

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
        mock_get_settings.return_value = mock_settings
        
        with patch("google.genai.Client"):
            yield
            
    app.dependency_overrides.clear()

@patch("app.services.requirement_matching.RequirementMatchingService.match")
def test_match_requirements_endpoint(mock_match):
    # Setup mock result
    mock_result = RequirementMatchingResult(
        implemented_features=[
            {"name": "Auth", "description": "User login", "evidence": "Found auth.py router", "matched_files": ["app/routers/auth.py"]}
        ],
        partially_implemented_features=[],
        missing_features=[],
        confidence_score=0.95,
        summary="Code implements base login."
    )
    mock_match.return_value = mock_result

    # Minimal valid payloads for request matching
    payload = {
        "prd_findings": {
            "pages": [],
            "features": [{"name": "Auth", "description": "User login", "priority": "must_have", "acceptance_criteria": [], "related_pages": []}],
            "forms": [],
            "user_flows": []
        },
        "github_findings": {
            "technologies": ["Python"],
            "frameworks": ["FastAPI"],
            "pages": [],
            "components": [],
            "folder_structure": {},
            "security_issues": [],
            "architecture_quality": {
                "rating": "good",
                "strengths": [],
                "weaknesses": [],
                "recommendations": []
            }
        },
        "browser_findings": None
    }
    
    response = client.post("/api/v1/requirements/match", json=payload)
    
    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data["implemented_features"]) == 1
    assert json_data["implemented_features"][0]["name"] == "Auth"
    assert json_data["confidence_score"] == 0.95
    mock_match.assert_called_once()

def test_match_requirements_endpoint_invalid_payload():
    # Empty payload missing prd_findings and github_findings
    payload = {}
    response = client.post("/api/v1/requirements/match", json=payload)
    assert response.status_code == 422

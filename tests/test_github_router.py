import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.main import app
from app.dependencies import get_current_user, get_db
from app.schemas.github import GithubAnalysisResponse, GithubAnalysisResultSchema, ArchitectureQuality

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

@patch("app.services.github_analysis.GithubAnalysisService.analyze")
def test_analyze_github_endpoint(mock_analyze):
    # Setup mock response
    mock_response = GithubAnalysisResponse(
        repo_url="https://github.com/owner/repo",
        commit_sha="abcdef123456",
        is_cached=False,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        analysis=GithubAnalysisResultSchema(
            technologies=["Python"],
            frameworks=["FastAPI"],
            pages=[],
            components=[],
            folder_structure={},
            security_issues=[],
            architecture_quality=ArchitectureQuality(
                rating="excellent",
                strengths=["Modularity"],
                weaknesses=[],
                recommendations=[]
            )
        )
    )
    mock_analyze.return_value = mock_response

    # Call endpoint
    payload = {
        "repo_url": "https://github.com/owner/repo",
        "force_refresh": False
    }
    response = client.post("/api/v1/github/analyze", json=payload)
    
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["repo_url"] == "https://github.com/owner/repo"
    assert json_data["commit_sha"] == "abcdef123456"
    assert json_data["is_cached"] is False
    mock_analyze.assert_called_once()

@patch("app.repositories.github_analysis.GithubAnalysisRepository.get_all_cached")
def test_list_cached_analyses_endpoint(mock_get_all_cached):
    # Setup mock records
    mock_record = MagicMock()
    mock_record.id = "test-uuid"
    mock_record.repo_url = "https://github.com/owner/repo"
    mock_record.commit_sha = "abcdef123456"
    mock_record.created_at = datetime.now(timezone.utc)
    mock_record.updated_at = datetime.now(timezone.utc)
    
    mock_get_all_cached.return_value = ([mock_record], 1)

    response = client.get("/api/v1/github/cached?page=1&page_size=20")
    
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["total"] == 1
    assert len(json_data["items"]) == 1
    assert json_data["items"][0]["repo_url"] == "https://github.com/owner/repo"
    mock_get_all_cached.assert_called_once_with(1, 20)

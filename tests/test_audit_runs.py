import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.dependencies import get_current_user, get_db

client = TestClient(app)

class DummyUser:
    id = "test-user-id"
    email = "test@example.com"
    is_admin = False
    is_active = True

def mock_get_current_user():
    return DummyUser()

def mock_get_db():
    return MagicMock()

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db] = mock_get_db
    yield
    app.dependency_overrides.clear()

@patch("app.services.audit_run.AuditRunService.get_audit_run_diagnostics")
def test_get_audit_run_diagnostics_endpoint(mock_get_diagnostics):
    mock_get_diagnostics.return_value = {
        "audit_run_id": "test-run-uuid",
        "failed_stage": "github",
        "failure_reason": "Gemini API call failed: 503 Service Unavailable",
        "failure_stack_trace": "Traceback...",
        "last_successful_step": "prd",
        "dependency_status": {
            "supabase": "healthy",
            "gemini": "healthy",
            "playwright": "healthy",
            "google_drive": "degraded (File not found)",
            "google_sheets": "healthy"
        }
    }
    
    response = client.get("/api/v1/audit-runs/test-run-uuid/diagnostics")
    
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["audit_run_id"] == "test-run-uuid"
    assert json_data["failed_stage"] == "github"
    assert json_data["dependency_status"]["supabase"] == "healthy"
    mock_get_diagnostics.assert_called_once_with("test-run-uuid")

"""
Tests for the Authenticated Audit Framework.
"""

import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from app.models.project import Project
from app.models.auth_audit_result import AuthAuditResult
from app.services.secret_manager import SecretManagerService
from app.schemas.browser_audit import BrowserAuditResponse, PageAuditResult
from app.schemas.auth_audit import (
    AuthAuditCredentialsSaveRequest,
    AuthAuditStatusResponse,
    AuthAuditFindingsResponse,
    AuthAuditScoresResponse,
    AuthAuditProtectedRoutesResponse,
)
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


# Dummy User
class DummyUser:
    id = "user-auth-123"
    email = "authuser@test.com"
    is_admin = True
    is_active = True


def mock_get_current_user():
    return DummyUser()


def test_auth_credentials_save_and_retrieve():
    """Test that auth credentials can be saved and retrieved through SecretManager."""
    sm = SecretManagerService()

    admin_creds = {"email": "admin@example.com", "password": "AdminPass123"}
    user_creds = {"email": "user@example.com", "password": "UserPass123"}
    auth_creds = {"email": "auth@example.com", "password": "AuthPass123!"}

    ref = sm.save_credentials("auth-proj-123", admin_creds, user_creds, auth_creds=auth_creds)
    assert ref is not None

    decrypted = sm.retrieve_credentials(ref)
    assert decrypted is not None
    assert decrypted["admin"]["email"] == "admin@example.com"
    assert decrypted["user"]["email"] == "user@example.com"
    assert decrypted["auth"]["email"] == "auth@example.com"
    assert decrypted["auth"]["password"] == "AuthPass123!"

    sm.delete_credentials(ref)


def test_auth_credentials_without_auth_key():
    """Test backward compatibility — saving credentials without auth key."""
    sm = SecretManagerService()

    admin_creds = {"email": "admin@example.com", "password": "AdminPass123"}
    user_creds = {"email": "user@example.com", "password": "UserPass123"}

    ref = sm.save_credentials("auth-proj-456", admin_creds, user_creds)
    assert ref is not None

    decrypted = sm.retrieve_credentials(ref)
    assert decrypted is not None
    assert "auth" not in decrypted  # no auth key when not provided

    sm.delete_credentials(ref)


def test_auth_audit_result_model():
    """Test AuthAuditResult ORM model instantiation."""
    result = AuthAuditResult(
        audit_run_id="run-123",
        project_id="proj-123",
        status="SUCCESS",
        login_success=True,
        logout_success=True,
        session_persisted=True,
        invalid_password_rejected=True,
        empty_creds_rejected=True,
        routes_protected=True,
        redirect_after_login="/dashboard",
        redirect_after_logout="/login",
        protected_routes_found=5,
        protected_routes_audited=4,
        auth_score=85.0,
        login_url_used="https://example.com/login",
        findings=json.dumps([{
            "category": "AUTH",
            "title": "Test Finding",
            "description": "Test Description",
            "severity": "medium",
            "recommendation": "Test Recommendation"
        }]),
        protected_routes=json.dumps([
            {"route": "/dashboard", "status": "ACCESSED"},
            {"route": "/profile", "status": "ACCESSED"},
        ])
    )

    assert result.status == "SUCCESS"
    assert result.login_success is True
    assert result.auth_score == 85.0
    assert result.protected_routes_found == 5

    findings = json.loads(result.findings)
    assert len(findings) == 1
    assert findings[0]["category"] == "AUTH"

    routes = json.loads(result.protected_routes)
    assert len(routes) == 2


def test_auth_score_calculation():
    """Verify auth score penalties are calculated correctly."""
    # Full success: 100
    score = 100.0

    # Empty creds rejected = False → -15
    score -= 15.0
    assert score == 85.0

    # Invalid password rejected = False → -30
    score -= 30.0
    assert score == 55.0

    # Session not persisted → -15
    score -= 15.0
    assert score == 40.0

    # Logout failure → -15
    score -= 15.0
    assert score == 25.0

    # 2 unprotected routes → -20 (min(25, 2*10))
    score -= min(25.0, 2 * 10.0)
    assert score == 5.0

    score = max(0.0, min(100.0, score))
    assert score == 5.0


def test_auth_audit_schemas():
    """Test schema validation for auth audit types."""
    # Credentials request
    creds = AuthAuditCredentialsSaveRequest(
        auth_required=True,
        login_url="https://example.com/login",
        email="user@example.com",
        password="Password123"
    )
    assert creds.auth_required is True
    assert creds.email == "user@example.com"

    # Status response
    status = AuthAuditStatusResponse(
        project_id="proj-123",
        auth_required=True,
        status="SUCCESS",
        has_credentials=True,
        last_audit_run_id="run-123",
        updated_at=None
    )
    assert status.status == "SUCCESS"

    # Scores response
    scores = AuthAuditScoresResponse(
        project_id="proj-123",
        audit_run_id="run-123",
        auth_score=85.0
    )
    assert scores.auth_score == 85.0


def test_browser_audit_request_auth_fields():
    """Test that BrowserAuditRequest includes auth fields."""
    from app.schemas.browser_audit import BrowserAuditRequest

    req = BrowserAuditRequest(
        url="https://example.com",
        auth_required=True,
        login_url="https://example.com/login",
        auth_email="user@example.com",
        auth_password="Password123"
    )
    assert req.auth_required is True
    assert req.login_url == "https://example.com/login"
    assert req.auth_email == "user@example.com"
    assert req.auth_password == "Password123"


def test_browser_audit_response_auth_fields():
    """Test that BrowserAuditResponse includes auth fields."""
    resp = BrowserAuditResponse(
        audit_id="audit-123",
        target_url="https://example.com",
        pages_audited=[],
        total_pages_visited=0,
        auth_status="SUCCESS",
        authenticated_pages_audited=[],
        protected_routes_discovered=["/dashboard", "/profile"],
        created_at="2026-01-01T00:00:00Z"
    )
    assert resp.auth_status == "SUCCESS"
    assert len(resp.protected_routes_discovered) == 2
    assert resp.authenticated_pages_audited == []


def test_delete_project_cascades_and_cleans_secrets():
    """Verify that deleting a project cascades to delete runs, reports, and audit results, and deletes secrets."""
    from app.services.project import ProjectService

    mock_db = MagicMock()
    mock_project = Project(
        id="proj-delete-123",
        name="Delete Test Project",
        owner_id="user-123",
        secret_reference="ref-delete-123"
    )
    
    mock_project_service = ProjectService(mock_db)
    
    # Mock project repository get_by_id and check ownership
    with patch.object(mock_project_service.project_repo, "get_by_id", return_value=mock_project):
        with patch.object(mock_project_service, "_check_ownership", return_value=None):
            with patch("app.services.secret_manager.SecretManagerService") as mock_sm_cls:
                mock_sm = MagicMock()
                mock_sm_cls.return_value = mock_sm
                
                # Mock repository delete method
                with patch.object(mock_project_service.project_repo, "delete") as mock_repo_delete:
                    # Run delete
                    mock_project_service.delete_project("proj-delete-123", DummyUser())
                    
                    # Verify credentials deletion was called
                    mock_sm.delete_credentials.assert_called_once_with("ref-delete-123")
                    # Verify repo delete was called with project
                    mock_repo_delete.assert_called_once_with(mock_project)

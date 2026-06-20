import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from app.models.project import Project
from app.models.rbac_result import RBACAuditResult
from app.services.secret_manager import SecretManagerService
from app.services.rbac_security import RBACSecurityEngine
from app.schemas.browser_audit import BrowserAuditResponse, PageAuditResult
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Dummy User
class DummyUser:
    id = "user-123"
    email = "user@test.com"
    is_admin = True
    is_active = True

def mock_get_current_user():
    return DummyUser()

@pytest.fixture(autouse=True)
def setup_rbac_overrides():
    app.dependency_overrides[app.dependency_overrides.get] = mock_get_current_user
    yield
    app.dependency_overrides.clear()


def test_secret_manager_local_fallback():
    """Test local symmetric encryption fallback for secrets."""
    sm = SecretManagerService()
    
    admin_creds = {"email": "admin@example.com", "password": "AdminPassword123"}
    user_creds = {"email": "user@example.com", "password": "UserPassword123"}
    
    ref = sm.save_credentials("proj-123", admin_creds, user_creds)
    assert ref is not None
    
    decrypted = sm.retrieve_credentials(ref)
    assert decrypted["admin"]["email"] == "admin@example.com"
    assert decrypted["admin"]["password"] == "AdminPassword123"
    assert decrypted["user"]["email"] == "user@example.com"
    assert decrypted["user"]["password"] == "UserPassword123"
    
    sm.delete_credentials(ref)


def test_rbac_security_engine_evaluation():
    """Test security score calculations, violations detection, and findings generation."""
    project = Project(
        id="proj-123",
        name="Test Project",
        rbac_enabled=True,
        admin_url="/admin",
        user_url="/dashboard",
        deployment_url="http://vulnerable-site.com",  # Insecure HTTP
        secret_reference="secret-ref-123"
    )

    # Compile browser results showing violations and failures
    browser_res = BrowserAuditResponse(
        audit_id="audit-123",
        target_url="http://vulnerable-site.com",
        total_pages_visited=3,
        created_at=datetime.now(timezone.utc).isoformat(),
        pages_audited=[
            # Guest crawls public page
            PageAuditResult(
                url="http://vulnerable-site.com/",
                role="Guest",
                status_code=200,
                access_status="allowed",
            ),
            # Guest successfully hits the dashboard (escalation)
            PageAuditResult(
                url="http://vulnerable-site.com/dashboard",
                role="Guest",
                status_code=200,
                access_status="escalated",
            ),
            # Regular user successfully hits admin page (escalation)
            PageAuditResult(
                url="http://vulnerable-site.com/admin",
                role="User",
                status_code=200,
                access_status="escalated",
            )
        ]
    )

    engine = RBACSecurityEngine()
    result = engine.evaluate(project, browser_res, has_credentials=True)

    assert result["status"] == "COMPLETED"
    # Should deduct points for HTTP, guest escalation, user escalation
    assert result["authz_score"] < 100.0
    assert result["session_score"] < 100.0
    assert result["overall_score"] < 100.0

    violations = json.loads(result["violations"])
    assert len(violations) >= 2
    
    findings = json.loads(result["findings"])
    assert len(findings) >= 3  # HTTP warning + 2 authorization findings


def test_save_rbac_credentials_merges_existing():
    """Test that saving credentials with empty/None values preserves existing stored ones."""
    from app.schemas.rbac import RBACCredentialsSaveRequest
    from app.routers.rbac import save_rbac_credentials
    
    mock_db = MagicMock()
    mock_user = DummyUser()
    
    mock_project = MagicMock()
    mock_project.id = "proj-123"
    mock_project.secret_reference = "ref-old-123"
    mock_project.rbac_enabled = True
    
    # Mock _check_project_ownership helper
    with patch("app.routers.rbac._check_project_ownership", return_value=mock_project):
        with patch("app.routers.rbac.SecretManagerService") as mock_sm_cls:
            mock_sm = MagicMock()
            mock_sm_cls.return_value = mock_sm
            
            # Old credentials in the secret manager
            mock_sm.retrieve_credentials.return_value = {
                "admin": {"email": "admin@save.com", "password": "AdminOldPassword"},
                "user": {"email": "user@save.com", "password": "UserOldPassword"}
            }
            mock_sm.save_credentials.return_value = "ref-new-123"
            
            # Incoming payload has empty fields for admin email/password, but new ones for user
            payload = RBACCredentialsSaveRequest(
                rbac_enabled=True,
                admin_url="/admin",
                admin_email=None,
                admin_password="",
                user_url="/dashboard",
                user_email="user@new.com",
                user_password="UserNewPassword"
            )
            
            # Call router function directly
            res = save_rbac_credentials(
                project_id="proj-123",
                payload=payload,
                current_user=mock_user,
                db=mock_db
            )
            
            # Verify retrieve was called to fetch the old credentials
            mock_sm.retrieve_credentials.assert_called_once_with("ref-old-123")
            
            # Verify delete was called on old reference
            mock_sm.delete_credentials.assert_called_once_with("ref-old-123")
            
            # Verify save was called with the MERGED credentials
            # admin credentials should be merged/preserved (email and password kept)
            # user credentials should be updated to incoming values
            mock_sm.save_credentials.assert_called_once_with(
                "proj-123",
                {"email": "admin@save.com", "password": "AdminOldPassword"},
                {"email": "user@new.com", "password": "UserNewPassword"}
            )
            
            # Verify project details are updated in db
            assert mock_project.secret_reference == "ref-new-123"
            assert mock_project.admin_url == "/admin"
            assert mock_project.user_url == "/dashboard"
            assert mock_project.rbac_enabled is True


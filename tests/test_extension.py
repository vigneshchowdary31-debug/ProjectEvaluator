import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta, timezone
from fastapi import WebSocket
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user, get_db
from app.services.auth import AuthService
from app.services.security_engine import AdvancedSecurityEngine
from app.services.readiness_evaluator import ProductionReadinessEvaluator
from app.utils.ws_manager import WebSocketManager
from app.models.refresh_token import RefreshToken
from app.models.evidence import Evidence
from app.utils.exceptions import UnauthorizedException, ConflictException

client = TestClient(app)

# Dummy User and Session mock fixtures
class DummyUser:
    id = "test-user-uuid"
    email = "developer@example.com"
    is_admin = False
    is_active = True

def mock_get_current_user():
    return DummyUser()

@pytest.fixture
def setup_overrides():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.clear()

# --- 1. WebSocket Manager Tests ---
@pytest.mark.anyio
async def test_websocket_manager_lifecycle():
    ws_manager = WebSocketManager()
    
    # Mock WebSocket
    mock_ws_1 = AsyncMock(spec=WebSocket)
    mock_ws_2 = AsyncMock(spec=WebSocket)
    
    run_id = "test-run-id"
    
    # Test Connect
    await ws_manager.connect(run_id, mock_ws_1)
    await ws_manager.connect(run_id, mock_ws_2)
    
    assert run_id in ws_manager.active_connections
    assert len(ws_manager.active_connections[run_id]) == 2
    mock_ws_1.accept.assert_called_once()
    mock_ws_2.accept.assert_called_once()
    
    # Test Broadcast
    message = {"status": "running", "log": "Step completed"}
    await ws_manager.broadcast(run_id, message)
    mock_ws_1.send_json.assert_called_once_with(message)
    mock_ws_2.send_json.assert_called_once_with(message)
    
    # Test Disconnect
    ws_manager.disconnect(run_id, mock_ws_1)
    assert len(ws_manager.active_connections[run_id]) == 1
    
    ws_manager.disconnect(run_id, mock_ws_2)
    assert run_id not in ws_manager.active_connections


# --- 2. Advanced Security Engine Tests ---
def test_security_engine_scanner_rules():
    engine = AdvancedSecurityEngine()
    
    file_paths = [
        "app/main.py",
        "secrets/.env",
        "ssh/id_rsa",
        "requirements.txt"
    ]
    
    manifest_contents = {
        "app/main.py": "allow_origins = ['*']\napi_key = 'sk_test_12345'",
        "requirements.txt": "requests==2.20.0\njinja2==2.11.1\n",
        "secrets/.env": "PORT=8000\n"
    }
    
    findings = engine.scan(file_paths, manifest_contents)
    
    # We should have findings for:
    # 1. .env committed (High/Misconfig)
    # 2. id_rsa committed (Critical/Misconfig)
    # 3. CORS wildcard allowed in main.py (Medium/Broken Access Control)
    # 4. Hardcoded api_key in main.py (High/Cryptographic Failures)
    # 5. Vulnerable requests dependency (High)
    # 6. Vulnerable jinja2 dependency (High)
    
    finding_titles = [f.title for f in findings]
    
    assert "Environment Configuration File (.env) Committed" in finding_titles
    assert "Sensitive Credentials File Committed" in finding_titles
    assert "Wildcard CORS Configuration" in finding_titles
    assert "Hardcoded API or Secret Key" in finding_titles
    assert "Vulnerable Dependency: Requests < 2.31.0" in finding_titles
    assert "Vulnerable Dependency: Jinja2 < 3.1.3" in finding_titles
    
    # Verify to_dict output format
    f_dict = findings[0].to_dict()
    assert "title" in f_dict
    assert "severity" in f_dict
    assert "owasp_category" in f_dict


# --- 3. Production Readiness Evaluator Tests ---
def test_production_readiness_evaluator():
    evaluator = ProductionReadinessEvaluator()
    
    # Case A: Minimal prototype with no test, Dockerfile, Sentry, or logging
    file_paths_a = ["main.py"]
    manifests_a = {"main.py": "print('hello')"}
    result_a = evaluator.evaluate(
        file_paths=file_paths_a,
        manifest_contents=manifests_a,
        security_findings_count=3,
        github_rating="poor"
    )
    assert result_a["classification"] == "Development Ready"
    assert result_a["categories"]["testing"] == 30.0
    assert result_a["categories"]["security"] == 55.0  # 100 - 3*15
    
    # Case B: Standard staging-ready application with Dockerfile, logging, and tests
    file_paths_b = ["Dockerfile", "README.md", "main.py", "tests/test_main.py"]
    manifests_b = {
        "main.py": "import logging\nlogger = logging.getLogger(__name__)\n",
        "requirements.txt": "requests==2.31.0\nsentry-sdk\n"
    }
    result_b = evaluator.evaluate(
        file_paths=file_paths_b,
        manifest_contents=manifests_b,
        security_findings_count=0,
        github_rating="good"
    )
    assert result_b["classification"] in ("Staging Ready", "Production Ready", "Enterprise Ready")
    assert result_b["categories"]["deployment_readiness"] == 100.0  # 60 + 25 + 15
    assert result_b["categories"]["security"] == 100.0
    assert result_b["categories"]["monitoring"] == 100.0  # sentry-sdk exists
    assert result_b["categories"]["testing"] == 100.0  # test exists


# --- 4. Refresh Token Flow & Rotation (AuthService) ---
def test_refresh_token_rotation_and_reuse():
    db_mock = MagicMock()
    auth_service = AuthService(db_mock)
    
    user_id = "test-user-id"
    user_email = "dev@example.com"
    
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.email = user_email
    mock_user.is_active = True
    mock_user.is_admin = False
    
    # Mock UserRepository
    auth_service.user_repo = MagicMock()
    auth_service.user_repo.get_by_id.return_value = mock_user
    
    # A. Test create_refresh_token
    raw_token = auth_service.create_refresh_token(user_id)
    assert raw_token is not None
    db_mock.add.assert_called_once()
    db_mock.commit.assert_called_once()
    
    # B. Test rotate_refresh_token - Successful rotation
    token_record = RefreshToken(
        id="parent-token-uuid",
        user_id=user_id,
        token_hash=auth_service._hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        is_revoked=False
    )
    
    # Mock DB query
    db_mock.query().filter().first.return_value = token_record
    
    with patch("app.services.auth.create_access_token") as mock_create_access:
        mock_create_access.return_value = "access-token-jwt"
        
        response = auth_service.rotate_refresh_token(raw_token)
        
        assert response.access_token == "access-token-jwt"
        assert response.refresh_token is not None
        assert token_record.is_revoked is True # Parent token revoked
        
    # C. Test rotate_refresh_token - Reuse Attack Detection
    reused_token_record = RefreshToken(
        id="used-token-uuid",
        user_id=user_id,
        token_hash=auth_service._hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        is_revoked=True  # ALREADY REVOKED!
    )
    db_mock.query().filter().first.return_value = reused_token_record
    
    # Reusing a revoked token should revoke all tokens for this user and raise UnauthorizedException
    with pytest.raises(UnauthorizedException) as exc_info:
        auth_service.rotate_refresh_token(raw_token)
        
    assert "Token reuse detected" in str(exc_info.value.detail)
    db_mock.commit.assert_called()


# --- 5. Evidence Router Tests ---
@patch("app.repositories.project.ProjectRepository.get_by_id")
@patch("app.repositories.user.UserRepository.get_by_id")
def test_evidence_endpoints(mock_user_get, mock_project_get, setup_overrides):
    # Setup App overrides to mock DB
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    
    # Mock Project & Access Verification
    mock_project = MagicMock()
    mock_project.id = "proj-uuid"
    mock_project.owner_id = "test-user-uuid"
    mock_project_get.return_value = mock_project
    
    # Mock database query results for evidence
    mock_evidence = MagicMock()
    mock_evidence.id = "ev-uuid"
    mock_evidence.project_id = "proj-uuid"
    mock_evidence.audit_run_id = "run-uuid"
    mock_evidence.file_path = "app/main.py"
    mock_evidence.function_name = "init"
    mock_evidence.line_range = "1-10"
    mock_evidence.evidence_type = "Code"
    mock_evidence.confidence_score = 0.95
    mock_evidence.screenshot_url = None
    mock_evidence.details = "{}"
    mock_evidence.created_at = datetime.now(timezone.utc)
    
    mock_db.execute().scalars().all.return_value = [mock_evidence]
    
    # Test project evidence endpoint
    response = client.get("/api/v1/evidence/project/proj-uuid")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "ev-uuid"
    assert data[0]["file_path"] == "app/main.py"
    
    # Clean overrides
    app.dependency_overrides.clear()

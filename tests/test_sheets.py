import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.main import app
from app.dependencies import get_current_user, get_db
from app.models.sheet_connection import SheetConnection
from app.models.import_job import ImportJob
from app.models.project import Project
from app.models.project_approval import ProjectApproval
from app.models.project_sync_history import ProjectSyncHistory

client = TestClient(app)

# Dummy admin user fixture
class DummyAdminUser:
    id = "admin-user-id"
    email = "admin@example.com"
    is_admin = True
    is_active = True

def mock_get_current_user():
    return DummyAdminUser()

# In-memory session mock helper
class MockSession:
    def __init__(self):
        self.added = []
        self.deleted = []
        self.committed = False
        
    def add(self, obj):
        # Auto-populate typical default attributes to avoid Pydantic response validation errors in tests
        if hasattr(obj, "id") and getattr(obj, "id") is None:
            import uuid
            obj.id = str(uuid.uuid4())
        if hasattr(obj, "created_at") and getattr(obj, "created_at") is None:
            from datetime import datetime, timezone
            obj.created_at = datetime.now(timezone.utc)
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at") is None:
            from datetime import datetime, timezone
            obj.updated_at = datetime.now(timezone.utc)
        if hasattr(obj, "started_at") and getattr(obj, "started_at") is None:
            from datetime import datetime, timezone
            obj.started_at = datetime.now(timezone.utc)
        if hasattr(obj, "row_count") and getattr(obj, "row_count") is None:
            obj.row_count = 0
        if hasattr(obj, "total_rows") and getattr(obj, "total_rows") is None:
            obj.total_rows = 0
        if hasattr(obj, "imported_count") and getattr(obj, "imported_count") is None:
            obj.imported_count = 0
        if hasattr(obj, "updated_count") and getattr(obj, "updated_count") is None:
            obj.updated_count = 0
        if hasattr(obj, "skipped_count") and getattr(obj, "skipped_count") is None:
            obj.skipped_count = 0
        if hasattr(obj, "error_count") and getattr(obj, "error_count") is None:
            obj.error_count = 0
        if hasattr(obj, "status") and getattr(obj, "status") is None:
            if obj.__class__.__name__ == "SheetConnection":
                obj.status = "active"
            elif obj.__class__.__name__ == "ImportJob":
                obj.status = "running"
            elif obj.__class__.__name__ == "AuditQueue":
                obj.status = "queued"
        self.added.append(obj)
        
    def delete(self, obj):
        self.deleted.append(obj)
        
    def commit(self):
        self.committed = True
        
    def refresh(self, obj):
        pass

    def close(self):
        pass
        
    def query(self, model):
        mock_query = MagicMock()
        if model == SheetConnection:
            def filter_side_effect(*args, **kwargs):
                filter_str = str(args[0]) if args else ""
                if "sheet_id" in filter_str:
                    # Connection check: return None so connect validation succeeds
                    mock_query.first.return_value = None
                else:
                    # Return standard connection object
                    mock_sheet = SheetConnection(
                        id="test-connection-id",
                        sheet_name="Test Sheet",
                        sheet_url="https://docs.google.com/spreadsheets/d/abc123xyz",
                        sheet_id="abc123xyz",
                        status="active",
                        sync_frequency="manual",
                        created_by="admin-user-id"
                    )
                    mock_query.first.return_value = mock_sheet
                return mock_query
                
            mock_query.filter = filter_side_effect
        else:
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = None
            
        mock_query.all.return_value = []
        return mock_query

    def execute(self, statement):
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = []
        mock_res.scalar_one_or_none.return_value = None
        return mock_res

    @property
    def bind(self):
        mock_bind = MagicMock()
        mock_bind.dialect.name = "sqlite"
        return mock_bind

def mock_get_db():
    return MockSession()

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db] = mock_get_db
    yield
    app.dependency_overrides.clear()


@patch("app.services.google_sheets.GoogleSheetsService.test_connection")
def test_connect_sheet_endpoint(mock_test_conn):
    mock_test_conn.return_value = (True, "Cohort 5 Projects Intake")

    payload = {
        "sheet_name": "Cohort 5 Projects Intake",
        "sheet_url": "https://docs.google.com/spreadsheets/d/abc123xyz/edit#gid=0",
        "sync_frequency": "manual"
    }
    
    response = client.post("/api/v1/sheets/connect", json=payload)
    
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["sheet_name"] == "Cohort 5 Projects Intake"
    assert json_data["sheet_id"] == "abc123xyz"
    assert json_data["status"] == "active"
    mock_test_conn.assert_called_once_with("abc123xyz")


@patch("app.services.google_sheets.GoogleSheetsService.test_connection")
def test_test_sheet_connection_endpoint(mock_test_conn):
    mock_test_conn.return_value = (True, "Cohort 5 Projects Intake")

    response = client.post("/api/v1/sheets/test-connection-id/test")
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_test_conn.assert_called_once_with("abc123xyz")


@patch("app.services.google_sheets.GoogleSheetsService.read_all_rows")
@patch("app.services.google_sheets.GoogleSheetsService.test_connection")
def test_import_engine_run(mock_test_conn, mock_read_rows):
    mock_test_conn.return_value = (True, "Test Sync Sheet")
    
    # Setup mock spreadsheet rows
    mock_rows = [
        {
            "_row_number": 2,
            "Project Name": "Student E-Commerce",
            "Description": "An online store.",
            "Repository URL": "https://github.com/student/ecom",
            "PRD URL": "https://docs.google.com/document/d/prd1",
            "Deployment URL": "https://ecom.student.app",
            "RBAC Enabled": "True",
            "Admin URL": "https://ecom.student.app/admin",
            "User URL": "https://ecom.student.app/shop",
            "Auth Required": "Yes",
            "Login URL": "https://ecom.student.app/login",
            "Student Name": "Alice Smith",
            "Company Name": "Stripe",
            "Admin Email": "admin@ecom.com",
            "Admin Password": "adminpassword123",
            "Test User Email": "user@ecom.com",
            "Test User Password": "userpassword123"
        }
    ]
    mock_read_rows.return_value = (mock_rows, list(mock_rows[0].keys()))

    db = MockSession()
    from app.services.import_engine import ImportEngine
    
    with patch("app.services.secret_manager.SecretManagerService.save_credentials") as mock_save_creds:
        mock_save_creds.return_value = "dummy-secret-uuid"
        
        engine = ImportEngine(db)
        job = engine.run_import("test-connection-id", "admin-user-id")
        
        assert job.status == "completed"
        assert job.total_rows == 1
        assert job.imported_count == 1
        assert job.error_count == 0
        
        # Verify created models in database session
        added_types = [type(x) for x in db.added]
        assert Project in added_types
        assert ProjectApproval in added_types
        assert ProjectSyncHistory in added_types
        
        # Check project details
        project_obj = next(x for x in db.added if isinstance(x, Project))
        assert project_obj.name == "Student E-Commerce"
        assert project_obj.student_name == "Alice Smith"
        assert project_obj.company_name == "Stripe"
        assert project_obj.source == "sheet_import"
        assert project_obj.sheet_row_number == 2
        assert project_obj.secret_reference == "dummy-secret-uuid"
        
        # Verify credentials save was called
        mock_save_creds.assert_called_once()

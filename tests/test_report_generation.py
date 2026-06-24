import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.main import app
from app.dependencies import get_current_user, get_db
from app.schemas.report_generation import ReportGenerationResponse, StudentReportSchema, CompanyReportSchema

client = TestClient(app)

# Dummy user fixture
class DummyUser:
    id = "test-user-uuid"
    email = "owner@example.com"
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

@patch("app.services.report_generation.ReportGenerationService.generate")
def test_generate_report_endpoint(mock_generate):
    # Setup mock response
    mock_response = ReportGenerationResponse(
        id="report-uuid",
        project_id="project-uuid",
        completion_percentage=75.0,
        student_report=StudentReportSchema(
            completion_percentage=75.0,
            features_implemented=["Auth"],
            missing_features=[],
            security_findings=[],
            ui_findings=[],
            code_quality_findings=[],
            recommendations=[],
            educational_notes="Good job."
        ),
        company_report=CompanyReportSchema(
            completion_percentage=75.0,
            features_implemented=["Auth"],
            missing_features=[],
            security_findings=[],
            ui_findings=[],
            code_quality_findings=[],
            recommendations=[],
            executive_summary="Code ready."
        ),
        created_at=datetime.now(timezone.utc).isoformat()
    )
    mock_generate.return_value = mock_response

    # Sample requests payload containing minimal valid findings fields
    payload = {
        "project_id": "project-uuid",
        "prd_analysis": {"pages": [], "features": [], "forms": [], "user_flows": []},
        "github_analysis": {
            "technologies": [], "frameworks": [], "pages": [], "components": [], "folder_structure": {}, "security_issues": [],
            "architecture_quality": {"rating": "good", "strengths": [], "weaknesses": [], "recommendations": []}
        },
        "browser_analysis": None,
        "requirement_analysis": {
            "implemented_features": [{"name": "Auth", "description": "Desc", "evidence": "Evid", "matched_files": []}],
            "partially_implemented_features": [],
            "missing_features": [],
            "confidence_score": 1.0,
            "summary": "OK"
        }
    }
    
    response = client.post("/api/v1/reports/generate", json=payload)
    
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["id"] == "report-uuid"
    assert json_data["completion_percentage"] == 75.0
    assert json_data["student_report"]["educational_notes"] == "Good job."
    mock_generate.assert_called_once()

@patch("app.repositories.project.ProjectRepository.get_by_id")
@patch("app.repositories.generated_report.GeneratedReportRepository.get_by_project_id")
def test_get_project_reports_endpoint(mock_get_by_proj_id, mock_get_proj):
    # Mock project checks
    mock_project = MagicMock()
    mock_project.id = "project-uuid"
    mock_project.owner_id = "test-user-uuid"  # Matches current user
    mock_get_proj.return_value = mock_project

    # Mock DB record
    mock_record = MagicMock()
    mock_record.id = "report-uuid"
    mock_record.project_id = "project-uuid"
    mock_record.completion_percentage = 80.0
    mock_record.student_report = {
        "completion_percentage": 80.0,
        "features_implemented": [], "missing_features": [], "security_findings": [], "ui_findings": [], "code_quality_findings": [], "recommendations": [],
        "educational_notes": "Learn more."
    }
    mock_record.company_report = {
        "completion_percentage": 80.0,
        "features_implemented": [], "missing_features": [], "security_findings": [], "ui_findings": [], "code_quality_findings": [], "recommendations": [],
        "executive_summary": "Stable."
    }
    mock_record.created_at = datetime.now(timezone.utc)
    mock_record.student_report_url = None
    mock_record.company_report_url = None
    
    mock_get_by_proj_id.return_value = [mock_record]

    response = client.get("/api/v1/reports/project/project-uuid")
    
    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data) == 1
    assert json_data[0]["completion_percentage"] == 80.0
    assert json_data[0]["student_report"]["educational_notes"] == "Learn more."
    mock_get_proj.assert_called_once_with("project-uuid")
    mock_get_by_proj_id.assert_called_once_with("project-uuid")

@patch("app.repositories.project.ProjectRepository.get_by_id")
@patch("app.repositories.generated_report.GeneratedReportRepository.create")
@patch("app.services.gemini.GeminiService.generate_project_reports")
def test_report_generation_sentinel_score(mock_generate_reports, mock_create_report, mock_get_proj):
    # 1. Setup mock project
    mock_project = MagicMock()
    mock_project.id = "project-uuid"
    mock_project.owner_id = "test-user-uuid"
    mock_get_proj.return_value = mock_project

    # 2. Setup mock Gemini response
    from app.schemas.report_generation import StudentReportSchema, CompanyReportSchema
    mock_student = StudentReportSchema(
        completion_percentage=-1.0,
        features_implemented=[],
        missing_features=[],
        security_findings=[],
        ui_findings=[],
        code_quality_findings=[],
        recommendations=[],
        educational_notes="Notes"
    )
    mock_company = CompanyReportSchema(
        completion_percentage=-1.0,
        features_implemented=[],
        missing_features=[],
        security_findings=[],
        ui_findings=[],
        code_quality_findings=[],
        recommendations=[],
        executive_summary="Summary"
    )
    mock_gemini_wrapper = MagicMock()
    mock_gemini_wrapper.student_report = mock_student
    mock_gemini_wrapper.company_report = mock_company
    mock_generate_reports.return_value = mock_gemini_wrapper

    def set_created_at(report):
        from datetime import datetime, timezone
        report.created_at = datetime.now(timezone.utc)
        report.id = "report-uuid"
    mock_create_report.side_effect = set_created_at

    # 3. Setup payload with 0 features to trigger sentinel logic
    payload = {
        "project_id": "project-uuid",
        "prd_analysis": {"pages": [], "features": [], "forms": [], "user_flows": []},
        "github_analysis": {
            "technologies": [], "frameworks": [], "pages": [], "components": [], "folder_structure": {}, "security_issues": [],
            "architecture_quality": {"rating": "good", "strengths": [], "weaknesses": [], "recommendations": []}
        },
        "browser_analysis": None,
        "requirement_analysis": {
            "implemented_features": [],
            "partially_implemented_features": [],
            "missing_features": [],
            "confidence_score": 1.0,
            "summary": "OK"
        }
    }
    
    from app.services.report_generation import ReportGenerationService
    from app.schemas.report_generation import ReportGenerationRequest
    
    db = MagicMock()
    service = ReportGenerationService(db)
    user = DummyUser()
    
    request = ReportGenerationRequest(**payload)
    response = service.generate(request, user)
    
    # 4. Verify completion percentage is set to -1.0
    assert response.completion_percentage == -1.0
    
    # Check that report_repo.create was called with -1.0 completion percentage
    mock_create_report.assert_called_once()
    saved_report = mock_create_report.call_args[0][0]
    assert saved_report.completion_percentage == -1.0


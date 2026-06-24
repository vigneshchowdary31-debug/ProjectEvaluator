"""
PRD Analysis router — analyze Product Requirements Documents via Google Docs URL.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.prd import (
    PRDAnalysisRequest,
    PRDAnalysisResponse,
    PRDAnalysisResult,
)
from app.services.prd_analysis import PRDAnalysisService

router = APIRouter(prefix="/api/v1/prd", tags=["PRD Analysis"])


@router.post(
    "/analyze",
    response_model=PRDAnalysisResponse,
    summary="Analyze a PRD from a Google Docs URL",
    description=(
        "Downloads a public Google Doc, extracts text, sends it to Gemini AI, "
        "and returns a structured analysis with pages, features, forms, and user flows."
    ),
)
def analyze_prd(
    request: PRDAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyze a Product Requirements Document.

    **Input**: A public Google Docs URL.

    **Process**:
    1. Download the document
    2. Extract text content
    3. Send to Gemini AI for analysis

    **Output**: Structured JSON with pages, features, forms, and user_flows.
    """
    service = PRDAnalysisService()
    return service.analyze(request)


@router.post(
    "/validate",
    response_model=PRDAnalysisResult,
    summary="Validate a PRD analysis result",
    description="Validate a raw PRD analysis JSON against the expected schema.",
)
def validate_prd_analysis(
    data: PRDAnalysisResult,
    _: User = Depends(get_current_user),
):
    """
    Validate a PRD analysis result against the Pydantic schema.

    Useful for testing or re-validating cached/stored analysis results.
    Returns the validated data if valid, or a 422 error with details if not.
    """
    return data

@router.get(
    "/diagnostics/{project_id}",
    summary="Run PRD Extraction Diagnostics",
    description="Tests Google Docs extraction and returns detailed PRD diagnostics."
)
def get_prd_diagnostics(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.repositories.project_repo import ProjectRepository
    from app.services.prd_parser import PRDParserService, ParserError
    from app.models.generated_report import GeneratedReport
    import json
    
    repo = ProjectRepository(db)
    project = repo.get_by_id(project_id)
    if not project:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Project not found")
        
    url = project.prd_url
    if not url:
        return {"error": "Project has no PRD URL configured."}
        
    parser = PRDParserService()
    
    diagnostic = {
        "project_id": project.id,
        "prd_url": url,
        "document_accessible": False,
        "document_downloaded": False,
        "text_extracted": False,
        "character_count": 0,
        "failure_reason": None,
        "features_found": 0,
        "pages_found": 0,
        "flows_found": 0,
    }
    
    # 1. Test extraction
    try:
        text, title = parser.extract_text(url)
        diagnostic["document_accessible"] = True
        diagnostic["document_downloaded"] = True
        diagnostic["text_extracted"] = True
        diagnostic["character_count"] = len(text)
    except ParserError as e:
        diagnostic["failure_reason"] = str(e)
    except Exception as e:
        diagnostic["failure_reason"] = f"Unknown Error: {str(e)}"
        
    # 2. Check DB for previously generated requirements
    report = db.query(GeneratedReport).filter(GeneratedReport.project_id == project_id).first()
    if report and report.student_report:
        # Assuming the generated report has a 'features' array embedded, or we check the matching results
        try:
            student_data = report.student_report
            if isinstance(student_data, str):
                student_data = json.loads(student_data)
            
            diagnostic["features_found"] = len(student_data.get("features", []))
            diagnostic["pages_found"] = len(student_data.get("pages", []))
            diagnostic["flows_found"] = len(student_data.get("user_flows", []))
            diagnostic["ai_analysis_status"] = "Completed" if diagnostic["features_found"] > 0 else "Empty/Skipped"
        except Exception:
            diagnostic["ai_analysis_status"] = "Parse Error"
    else:
        diagnostic["ai_analysis_status"] = "No Report Generated"
        
    return diagnostic

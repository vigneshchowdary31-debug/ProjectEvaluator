"""
GitHub Analysis Router — analyze GitHub repositories and check cached records.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.github import GithubAnalysisRequest, GithubAnalysisResponse
from app.services.github_analysis import GithubAnalysisService
from app.repositories.github_analysis import GithubAnalysisRepository

router = APIRouter(prefix="/api/v1/github", tags=["GitHub Analysis"])


@router.post(
    "/analyze",
    response_model=GithubAnalysisResponse,
    summary="Analyze a public GitHub repository",
    description=(
        "Fetches repository metadata, files directory structure, and manifest files "
        "from a public GitHub repository. Sends it to Gemini AI for technical analysis, "
        "and returns structural insights. Caches the result in SQLite by commit SHA."
    ),
)
def analyze_repository(
    request: GithubAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyze a GitHub Repository.

    **Input**: A public GitHub repository URL.
    **Process**: Checks database cache, queries GitHub API (commits/tree/contents), calls Gemini, and validates response schema.
    """
    service = GithubAnalysisService(db)
    return service.analyze(request)


@router.get(
    "/cached",
    summary="List cached repository analyses",
    description="List metadata of all previously analyzed and cached repositories.",
)
def list_cached_analyses(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List cached analyses in the system. Returns paginated records with metadata only.
    """
    repo = GithubAnalysisRepository(db)
    analyses, total = repo.get_all_cached(page, page_size)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": a.id,
                "repo_url": a.repo_url,
                "commit_sha": a.commit_sha,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
            }
            for a in analyses
        ]
    }

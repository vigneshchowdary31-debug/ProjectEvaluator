"""
Evidence Router — endpoints to retrieve structured audit evidence.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.evidence import EvidenceRepository
from app.utils.exceptions import ForbiddenException, NotFoundException

router = APIRouter(prefix="/api/v1/evidence", tags=["Evidence Engine"])


class EvidenceResponseSchema(BaseModel):
    id: str
    project_id: str
    audit_run_id: str
    file_path: Optional[str]
    function_name: Optional[str]
    line_range: Optional[str]
    evidence_type: str
    confidence_score: float
    screenshot_url: Optional[str]
    details: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


def check_project_owner(project_id: str, user: User, db: Session) -> None:
    proj_repo = ProjectRepository(db)
    project = proj_repo.get_by_id(project_id)
    if not project:
        raise NotFoundException(detail="Project not found")
    if project.owner_id != user.id and not user.is_admin:
        raise ForbiddenException(detail="You do not own this project")


@router.get("/project/{project_id}", response_model=List[EvidenceResponseSchema])
def get_project_evidence(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all logged evidence for a specific project."""
    check_project_owner(project_id, current_user, db)
    repo = EvidenceRepository(db)
    return repo.get_by_project_id(project_id)


@router.get("/run/{audit_run_id}", response_model=List[EvidenceResponseSchema])
def get_audit_run_evidence(
    audit_run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all logged evidence for a specific audit run."""
    repo = EvidenceRepository(db)
    # Find the run to get project_id
    from app.repositories.audit_run import AuditRunRepository
    run = AuditRunRepository(db).get_by_id(audit_run_id)
    if not run:
        raise NotFoundException(detail="Audit run not found")
    
    check_project_owner(run.project_id, current_user, db)
    return repo.get_by_audit_run_id(audit_run_id)

"""
Auth Audit Router — endpoints to configure authentication credentials
and fetch authenticated audit findings/routes/scores.
"""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.project import Project
from app.models.auth_audit_result import AuthAuditResult
from app.services.secret_manager import SecretManagerService
from app.services.project import ProjectService
from app.utils.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.schemas.auth_audit import (
    AuthAuditCredentialsSaveRequest,
    AuthAuditStatusResponse,
    AuthAuditFindingsResponse,
    AuthAuditFindingDetail,
    AuthAuditScoresResponse,
    AuthAuditProtectedRoutesResponse,
    AuthAuditProtectedRouteRow,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/auth", tags=["Authenticated Audit Framework"])


def _check_project_ownership(project_id: str, current_user: User, db: Session) -> Project:
    """Helper to verify if a project exists and current user has access to it."""
    project_service = ProjectService(db)
    project = project_service.get_project(project_id)
    project_service._check_ownership(project, current_user)
    return project


@router.post("/credentials", status_code=status.HTTP_200_OK)
def save_auth_credentials(
    project_id: str,
    payload: AuthAuditCredentialsSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Configure and save authentication credentials securely in Secret Manager.
    Credentials are encrypted on ingestion and never returned by any GET API.
    """
    project = _check_project_ownership(project_id, current_user, db)

    sm = SecretManagerService()

    # Load existing credentials to preserve RBAC creds
    existing_admin = {}
    existing_user = {}
    existing_auth = {}
    if project.secret_reference:
        try:
            old_creds = sm.retrieve_credentials(project.secret_reference)
            if old_creds:
                existing_admin = old_creds.get("admin", {})
                existing_user = old_creds.get("user", {})
                existing_auth = old_creds.get("auth", {})
        except Exception:
            pass

    auth_creds = {
        "email": payload.email if payload.email not in (None, "") else existing_auth.get("email", ""),
        "password": payload.password if payload.password not in (None, "") else existing_auth.get("password", "")
    }

    # Delete old secret reference if exists
    if project.secret_reference:
        try:
            sm.delete_credentials(project.secret_reference)
        except Exception:
            pass

    secret_ref = sm.save_credentials(
        project_id, existing_admin, existing_user, auth_creds=auth_creds
    )

    # Update Project database model properties
    project.auth_required = payload.auth_required
    project.login_url = payload.login_url
    project.secret_reference = secret_ref
    project.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(project)

    return {"message": "Authentication credentials saved successfully."}


@router.get("/status", response_model=AuthAuditStatusResponse)
def get_auth_status(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current authentication configuration and last run status of a project."""
    project = _check_project_ownership(project_id, current_user, db)

    # Check if credentials exist
    has_creds = False
    if project.secret_reference:
        sm = SecretManagerService()
        creds = sm.retrieve_credentials(project.secret_reference)
        if creds:
            auth = creds.get("auth", {})
            has_creds = bool(auth.get("email") and auth.get("password"))

    # Fetch latest audit run results
    stmt = select(AuthAuditResult).where(
        AuthAuditResult.project_id == project_id
    ).order_by(desc(AuthAuditResult.created_at)).limit(1)
    result = db.execute(stmt).scalar_one_or_none()

    return AuthAuditStatusResponse(
        project_id=project_id,
        auth_required=project.auth_required,
        status=result.status if result else "UNTESTED",
        has_credentials=has_creds,
        last_audit_run_id=result.audit_run_id if result else None,
        updated_at=result.created_at if result else None,
    )


@router.get("/findings", response_model=AuthAuditFindingsResponse)
def get_auth_findings(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed authentication quality findings for a project."""
    _check_project_ownership(project_id, current_user, db)

    stmt = select(AuthAuditResult).where(
        AuthAuditResult.project_id == project_id
    ).order_by(desc(AuthAuditResult.created_at)).limit(1)
    result = db.execute(stmt).scalar_one_or_none()

    if not result or not result.findings:
        return AuthAuditFindingsResponse(project_id=project_id, audit_run_id="", findings=[])

    try:
        findings_list = json.loads(result.findings)
        details = [AuthAuditFindingDetail.model_validate(item) for item in findings_list]
    except Exception as e:
        raise BadRequestException(detail=f"Failed to parse auth findings: {str(e)}")

    return AuthAuditFindingsResponse(
        project_id=project_id,
        audit_run_id=result.audit_run_id,
        findings=details
    )


@router.get("/routes", response_model=AuthAuditProtectedRoutesResponse)
def get_auth_protected_routes(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve discovered protected routes from the latest authenticated audit."""
    _check_project_ownership(project_id, current_user, db)

    stmt = select(AuthAuditResult).where(
        AuthAuditResult.project_id == project_id
    ).order_by(desc(AuthAuditResult.created_at)).limit(1)
    result = db.execute(stmt).scalar_one_or_none()

    if not result or not result.protected_routes:
        return AuthAuditProtectedRoutesResponse(project_id=project_id, audit_run_id="", protected_routes=[])

    try:
        routes_list = json.loads(result.protected_routes)
        rows = [AuthAuditProtectedRouteRow.model_validate(item) for item in routes_list]
    except Exception as e:
        raise BadRequestException(detail=f"Failed to parse protected routes: {str(e)}")

    return AuthAuditProtectedRoutesResponse(
        project_id=project_id,
        audit_run_id=result.audit_run_id,
        protected_routes=rows
    )


@router.get("/scores", response_model=AuthAuditScoresResponse)
def get_auth_scores(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve authentication security score for a project."""
    _check_project_ownership(project_id, current_user, db)

    stmt = select(AuthAuditResult).where(
        AuthAuditResult.project_id == project_id
    ).order_by(desc(AuthAuditResult.created_at)).limit(1)
    result = db.execute(stmt).scalar_one_or_none()

    if not result:
        return AuthAuditScoresResponse(
            project_id=project_id,
            audit_run_id="",
            auth_score=0.0
        )

    return AuthAuditScoresResponse(
        project_id=project_id,
        audit_run_id=result.audit_run_id,
        auth_score=result.auth_score
    )

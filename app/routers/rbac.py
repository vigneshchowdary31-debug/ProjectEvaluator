"""
RBAC Router — endpoints to configure role credentials and fetch access control matrices/findings.
"""

import json
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.project import Project
from app.models.rbac_result import RBACAuditResult
from app.services.secret_manager import SecretManagerService
from app.services.project import ProjectService
from app.utils.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.schemas.rbac import (
    RBACCredentialsSaveRequest,
    RBACStatusResponse,
    RBACCoverageResponse,
    RBACCoverageRow,
    RBACFindingsResponse,
    RBACFindingDetail,
    RBACScoresResponse,
    RBACViolationsResponse,
    RBACViolationDetail,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/rbac", tags=["RBAC Audit Framework"])


def _check_project_ownership(project_id: str, current_user: User, db: Session) -> Project:
    """Helper to verify if a project exists and current user has access to it."""
    project_service = ProjectService(db)
    project = project_service.get_project(project_id)
    project_service._check_ownership(project, current_user)
    return project


@router.post("/credentials", status_code=status.HTTP_200_OK)
def save_rbac_credentials(
    project_id: str,
    payload: RBACCredentialsSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Configure and save regular user and admin credentials securely in Secret Manager.
    Credentials are encrypted on ingestion and never returned by any GET API.
    """
    project = _check_project_ownership(project_id, current_user, db)
    
    # Store credentials in Google Secret Manager or local fallback
    sm = SecretManagerService()
    
    # Load existing credentials if any to prevent wiping them out on partial/empty updates
    existing_admin = {}
    existing_user = {}
    if project.secret_reference:
        try:
            old_creds = sm.retrieve_credentials(project.secret_reference)
            if old_creds:
                existing_admin = old_creds.get("admin", {})
                existing_user = old_creds.get("user", {})
        except Exception:
            pass

    admin_creds = {
        "email": payload.admin_email if payload.admin_email not in (None, "") else existing_admin.get("email", ""),
        "password": payload.admin_password if payload.admin_password not in (None, "") else existing_admin.get("password", "")
    }
    user_creds = {
        "email": payload.user_email if payload.user_email not in (None, "") else existing_user.get("email", ""),
        "password": payload.user_password if payload.user_password not in (None, "") else existing_user.get("password", "")
    }
    
    # If project already has a secret reference, update/overwrite it instead of creating new version key
    # Or delete old credentials to prevent leaks
    if project.secret_reference:
        try:
            sm.delete_credentials(project.secret_reference)
        except Exception:
            pass

    secret_ref = sm.save_credentials(project_id, admin_creds, user_creds)

    # Update Project database model properties
    project.rbac_enabled = payload.rbac_enabled
    project.admin_url = payload.admin_url
    project.user_url = payload.user_url
    project.secret_reference = secret_ref
    project.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(project)
    
    return {"message": "Audited project role credentials saved successfully."}


@router.get("/status", response_model=RBACStatusResponse)
def get_rbac_status(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current RBAC configuration and last run status of a project."""
    project = _check_project_ownership(project_id, current_user, db)
    
    # Check if credentials exist (references set and decryptable)
    has_admin = False
    has_user = False
    if project.secret_reference:
        sm = SecretManagerService()
        creds = sm.retrieve_credentials(project.secret_reference)
        if creds:
            has_admin = bool(creds.get("admin", {}).get("email") and creds.get("admin", {}).get("password"))
            has_user = bool(creds.get("user", {}).get("email") and creds.get("user", {}).get("password"))

    # Fetch latest audit run results for RBAC status
    stmt = select(RBACAuditResult).where(
        RBACAuditResult.project_id == project_id
    ).order_by(desc(RBACAuditResult.created_at)).limit(1)
    result = db.execute(stmt).scalar_one_or_none()

    return RBACStatusResponse(
        project_id=project_id,
        rbac_enabled=project.rbac_enabled,
        status=result.status if result else "UNTESTED",
        has_admin_credentials=has_admin,
        has_user_credentials=has_user,
        last_audit_run_id=result.audit_run_id if result else None,
        updated_at=result.created_at if result else None,
    )


@router.get("/coverage", response_model=RBACCoverageResponse)
def get_rbac_coverage(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve the role coverage matrix compiled from the latest audit run."""
    _check_project_ownership(project_id, current_user, db)
    
    stmt = select(RBACAuditResult).where(
        RBACAuditResult.project_id == project_id
    ).order_by(desc(RBACAuditResult.created_at)).limit(1)
    result = db.execute(stmt).scalar_one_or_none()
    
    if not result or not result.role_coverage_matrix:
        return RBACCoverageResponse(project_id=project_id, audit_run_id="", coverage=[])
        
    try:
        matrix_list = json.loads(result.role_coverage_matrix)
        coverage_rows = [RBACCoverageRow.model_validate(item) for item in matrix_list]
    except Exception as e:
        raise BadRequestException(detail=f"Failed to parse matrix logs: {str(e)}")

    return RBACCoverageResponse(
        project_id=project_id,
        audit_run_id=result.audit_run_id,
        coverage=coverage_rows
    )


@router.get("/findings", response_model=RBACFindingsResponse)
def get_rbac_findings(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed authentication and authorization findings for a project."""
    _check_project_ownership(project_id, current_user, db)
    
    stmt = select(RBACAuditResult).where(
        RBACAuditResult.project_id == project_id
    ).order_by(desc(RBACAuditResult.created_at)).limit(1)
    result = db.execute(stmt).scalar_one_or_none()
    
    if not result or not result.findings:
        return RBACFindingsResponse(project_id=project_id, audit_run_id="", findings=[])

    try:
        findings_list = json.loads(result.findings)
        details = [RBACFindingDetail.model_validate(item) for item in findings_list]
    except Exception as e:
        raise BadRequestException(detail=f"Failed to parse findings logs: {str(e)}")

    return RBACFindingsResponse(
        project_id=project_id,
        audit_run_id=result.audit_run_id,
        findings=details
    )


@router.get("/scores", response_model=RBACScoresResponse)
def get_rbac_scores(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve security ratings and overall RBAC score for a project."""
    _check_project_ownership(project_id, current_user, db)
    
    stmt = select(RBACAuditResult).where(
        RBACAuditResult.project_id == project_id
    ).order_by(desc(RBACAuditResult.created_at)).limit(1)
    result = db.execute(stmt).scalar_one_or_none()
    
    if not result:
        return RBACScoresResponse(
            project_id=project_id,
            audit_run_id="",
            auth_score=0.0,
            authz_score=0.0,
            session_score=0.0,
            overall_score=0.0
        )

    return RBACScoresResponse(
        project_id=project_id,
        audit_run_id=result.audit_run_id,
        auth_score=result.auth_score,
        authz_score=result.authz_score,
        session_score=result.session_score,
        overall_score=result.overall_score
    )


@router.get("/violations", response_model=RBACViolationsResponse)
def get_rbac_violations(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve all flagged authorization boundaries violations (privilege escalations)."""
    _check_project_ownership(project_id, current_user, db)
    
    stmt = select(RBACAuditResult).where(
        RBACAuditResult.project_id == project_id
    ).order_by(desc(RBACAuditResult.created_at)).limit(1)
    result = db.execute(stmt).scalar_one_or_none()
    
    if not result or not result.violations:
        return RBACViolationsResponse(project_id=project_id, audit_run_id="", violations=[])

    try:
        violations_list = json.loads(result.violations)
        details = [RBACViolationDetail.model_validate(item) for item in violations_list]
    except Exception as e:
        raise BadRequestException(detail=f"Failed to parse violations logs: {str(e)}")

    return RBACViolationsResponse(
        project_id=project_id,
        audit_run_id=result.audit_run_id,
        violations=details
    )

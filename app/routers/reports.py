"""
Reports router — CRUD for audit reports.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.report import ReportCreate, ReportListResponse, ReportResponse, ReportUpdate
from app.services.report import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


@router.get("/", response_model=ReportListResponse)
def list_reports(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_id: Optional[str] = Query(None),
    audit_run_id: Optional[str] = Query(None),
):
    """List reports with optional filters."""
    report_service = ReportService(db)
    reports, total = report_service.list_reports(
        page=page, page_size=page_size, project_id=project_id, audit_run_id=audit_run_id
    )
    return ReportListResponse(
        items=reports, total=total, page=page, page_size=page_size
    )


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a report by ID."""
    report_service = ReportService(db)
    return report_service.get_report(report_id)


@router.post("/", response_model=ReportResponse, status_code=201)
def create_report(
    data: ReportCreate,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new report."""
    report_service = ReportService(db)
    return report_service.create_report(data)


@router.put("/{report_id}", response_model=ReportResponse)
def update_report(
    report_id: str,
    data: ReportUpdate,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a report."""
    report_service = ReportService(db)
    return report_service.update_report(report_id, data)


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a report."""
    report_service = ReportService(db)
    report_service.delete_report(report_id)

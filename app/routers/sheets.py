"""
Sheets Router — endpoints to manage Google Sheets connections and trigger syncs.
"""

from typing import List
from fastapi import APIRouter, Depends, BackgroundTasks, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.sheet_connection import SheetConnection
from app.models.import_job import ImportJob
from app.models.project_sync_history import ProjectSyncHistory
from app.services.google_sheets import GoogleSheetsService
from app.services.import_engine import ImportEngine
from app.schemas.sheets import SheetConnectionCreate, SheetConnectionResponse, ImportJobResponse, ProjectSyncHistoryResponse
from app.utils.exceptions import NotFoundException, ForbiddenException, BadRequestException

router = APIRouter(prefix="/api/v1/sheets", tags=["Google Sheets Intake & Automation"])


def _check_admin(user: User) -> None:
    if not user.is_admin:
        raise ForbiddenException(detail="Admin privilege required for this action")


@router.post("/connect", response_model=SheetConnectionResponse, status_code=status.HTTP_201_CREATED)
def connect_sheet(
    payload: SheetConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Connect a Google Sheet. Extracts Sheet ID and validates access."""
    _check_admin(current_user)

    sheets_service = GoogleSheetsService()
    sheet_id = sheets_service.extract_sheet_id(payload.sheet_url)
    if not sheet_id:
        raise BadRequestException(detail="Could not extract a valid Google Sheet ID from URL.")

    # Test the connection to fetch sheet name
    success, title = sheets_service.test_connection(sheet_id)
    if not success:
        raise BadRequestException(detail=f"Connection validation failed: {title}. Ensure sheet is shared with the service account email.")

    # Check if already exists
    existing = db.query(SheetConnection).filter(SheetConnection.sheet_id == sheet_id).first()
    if existing:
        raise BadRequestException(detail="This Google Sheet is already connected.")

    sheet_conn = SheetConnection(
        sheet_name=title,
        sheet_url=payload.sheet_url,
        sheet_id=sheet_id,
        sync_frequency=payload.sync_frequency or "manual",
        status="active",
        created_by=current_user.id
    )
    db.add(sheet_conn)
    db.commit()
    db.refresh(sheet_conn)
    return sheet_conn


@router.get("/", response_model=List[SheetConnectionResponse])
def list_sheets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all connected Google Sheets."""
    _check_admin(current_user)
    stmt = select(SheetConnection).order_by(desc(SheetConnection.created_at))
    return list(db.execute(stmt).scalars().all())


@router.get("/{id}", response_model=SheetConnectionResponse)
def get_sheet_details(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve details of a specific sheet connection."""
    _check_admin(current_user)
    sheet = db.query(SheetConnection).filter(SheetConnection.id == id).first()
    if not sheet:
        raise NotFoundException(detail="Sheet connection not found")
    return sheet


@router.post("/{id}/test")
def test_sheet_connection(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Re-test access connection to the Google Sheet."""
    _check_admin(current_user)
    sheet = db.query(SheetConnection).filter(SheetConnection.id == id).first()
    if not sheet:
        raise NotFoundException(detail="Sheet connection not found")

    sheets_service = GoogleSheetsService()
    success, message = sheets_service.test_connection(sheet.sheet_id)
    
    if success:
        sheet.status = "active"
        sheet.last_sync_error = None
        db.commit()
        return {"status": "success", "message": f"Connected successfully to sheet '{message}'."}
    else:
        sheet.status = "error"
        sheet.last_sync_error = message
        db.commit()
        raise BadRequestException(detail=f"Connection failed: {message}")


@router.post("/{id}/sync")
def sync_sheet(
    id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger an asynchronous synchronization of projects from the Google Sheet."""
    _check_admin(current_user)
    sheet = db.query(SheetConnection).filter(SheetConnection.id == id).first()
    if not sheet:
        raise NotFoundException(detail="Sheet connection not found")

    # Check if a sync job is already running
    job = db.query(ImportJob).filter(
        ImportJob.sheet_connection_id == id,
        ImportJob.status == "running"
    ).first()
    if job:
        raise BadRequestException(detail="A synchronization job is already running for this sheet connection.")

    # Trigger async run using an isolated db session
    def _run_bg_import():
        from app.database import SessionLocal
        bg_db = SessionLocal()
        try:
            engine = ImportEngine(bg_db)
            engine.run_import(id, current_user.id)
        except Exception as bg_err:
            logger.error("Background sync error: %s", str(bg_err))
        finally:
            bg_db.close()

    background_tasks.add_task(_run_bg_import)
    return {"message": "Synchronization started in background.", "sheet_connection_id": id}


@router.post("/{id}/disconnect", status_code=status.HTTP_200_OK)
def disconnect_sheet(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect and delete a Google Sheet connection."""
    _check_admin(current_user)
    sheet = db.query(SheetConnection).filter(SheetConnection.id == id).first()
    if not sheet:
        raise NotFoundException(detail="Sheet connection not found")

    db.delete(sheet)
    db.commit()
    return {"message": "Google Sheet disconnected and deleted successfully."}


@router.get("/{id}/logs", response_model=List[ImportJobResponse])
def get_sync_logs(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get sync history logs for a sheet connection."""
    _check_admin(current_user)
    stmt = select(ImportJob).where(
        ImportJob.sheet_connection_id == id
    ).order_by(desc(ImportJob.started_at)).limit(20)
    return list(db.execute(stmt).scalars().all())

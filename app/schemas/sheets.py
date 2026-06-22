"""
Pydantic schemas for Google Sheets connections and synchronization.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SheetConnectionCreate(BaseModel):
    sheet_name: str = Field(..., description="Display name for the sheet")
    sheet_url: str = Field(..., description="Full Google Sheets URL")
    sync_frequency: Optional[str] = Field("manual", description="manual | hourly | daily")


class SheetConnectionResponse(BaseModel):
    id: str
    sheet_name: str
    sheet_url: str
    sheet_id: str
    status: str
    sync_frequency: str
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]
    last_sync_error: Optional[str]
    row_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ImportJobResponse(BaseModel):
    id: str
    sheet_connection_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    total_rows: int
    imported_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    errors: Optional[List[Dict[str, Any]]]
    triggered_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectSyncHistoryResponse(BaseModel):
    id: str
    project_id: str
    import_job_id: str
    action: str
    changes: Optional[Dict[str, Any]]
    sheet_row_number: int
    created_at: datetime

    model_config = {"from_attributes": True}

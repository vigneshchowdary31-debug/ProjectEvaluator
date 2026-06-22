"""
Pydantic schemas for project reviews and approvals.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.schemas.project import ProjectResponse


class ProjectApprovalResponse(BaseModel):
    id: str
    project_id: str
    status: str
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    project: Optional[ProjectResponse] = None

    model_config = {"from_attributes": True}


class ProjectApprovalReviewRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Review notes or rejection reasons")


class BulkApproveRequest(BaseModel):
    project_ids: List[str] = Field(..., description="List of project IDs to approve")

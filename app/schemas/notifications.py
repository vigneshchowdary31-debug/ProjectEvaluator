"""
Pydantic schemas for in-app notifications.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    message: str
    is_read: bool
    metadata_: Optional[Dict[str, Any]] = Field(None, serialization_alias="metadata", validation_alias="metadata")
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }

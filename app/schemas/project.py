"""
Project schemas.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    repository_url: Optional[str] = None
    prd_url: Optional[str] = None
    deployment_url: Optional[str] = None
    rbac_enabled: Optional[bool] = False
    admin_url: Optional[str] = None
    user_url: Optional[str] = None
    auth_required: Optional[bool] = False
    login_url: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    repository_url: Optional[str] = None
    prd_url: Optional[str] = None
    deployment_url: Optional[str] = None
    status: Optional[ProjectStatus] = None
    rbac_enabled: Optional[bool] = None
    admin_url: Optional[str] = None
    user_url: Optional[str] = None
    auth_required: Optional[bool] = None
    login_url: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    repository_url: Optional[str]
    prd_url: Optional[str]
    deployment_url: Optional[str]
    status: str
    owner_id: str
    rbac_enabled: bool
    admin_url: Optional[str]
    user_url: Optional[str]
    auth_required: bool
    login_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}



class ProjectListResponse(BaseModel):
    items: List[ProjectResponse]
    total: int
    page: int
    page_size: int

"""
Users router — admin-only user management.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_admin, get_db
from app.models.user import User
from app.schemas.user import UserListResponse, UserResponse, UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/", response_model=UserListResponse)
def list_users(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all users (admin only)."""
    user_service = UserService(db)
    users, total = user_service.list_users(page=page, page_size=page_size)
    return UserListResponse(items=users, total=total, page=page, page_size=page_size)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get a user by ID (admin only)."""
    user_service = UserService(db)
    return user_service.get_user(user_id)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    data: UserUpdate,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Update a user (admin only)."""
    user_service = UserService(db)
    return user_service.update_user(user_id, data)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Delete a user (admin only)."""
    user_service = UserService(db)
    user_service.delete_user(user_id)

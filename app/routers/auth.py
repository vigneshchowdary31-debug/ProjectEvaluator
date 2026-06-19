"""
Authentication router — login, register, current user.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, TokenRefreshRequest
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.auth import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate a user and return a JWT access token."""
    auth_service = AuthService(db)
    return auth_service.authenticate(login_data)


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """Register a new user account."""
    auth_service = AuthService(db)
    user = auth_service.register(user_data)
    return user


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the currently authenticated user's profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the currently authenticated user's profile (name, email, company, password)."""
    from app.services.user import UserService
    user_service = UserService(db)
    
    if data.email and data.email != current_user.email:
        from app.repositories.user import UserRepository
        user_repo = UserRepository(db)
        if user_repo.get_by_email(data.email):
            from app.utils.exceptions import ConflictException
            raise ConflictException(detail="Email already in use")
            
    # Don't let users toggle active/admin status themselves
    data.is_active = None
    return user_service.update_user(current_user.id, data)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    data: TokenRefreshRequest,
    db: Session = Depends(get_db),
):
    """Rotate the refresh token and issue a new access/refresh token pair."""
    auth_service = AuthService(db)
    return auth_service.rotate_refresh_token(data.refresh_token)


@router.post("/logout", status_code=204)
def logout(
    data: TokenRefreshRequest,
    db: Session = Depends(get_db),
):
    """Revoke a single refresh token (log out current session)."""
    auth_service = AuthService(db)
    auth_service.revoke_refresh_token(data.refresh_token)


@router.post("/logout-all", status_code=204)
def logout_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke all refresh tokens for the current user (log out all devices)."""
    auth_service = AuthService(db)
    auth_service.revoke_all_user_tokens(current_user.id)

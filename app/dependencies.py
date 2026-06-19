"""
Shared FastAPI dependencies.
"""

from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.repositories.user import UserRepository
from app.utils.exceptions import ForbiddenException, UnauthorizedException
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Database session ────────────────────────────────────────────────────────
def get_db():
    """Yield a database session and ensure it is closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Current user ────────────────────────────────────────────────────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT token."""
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedException()

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise UnauthorizedException()

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedException(detail="User no longer exists")
    if not user.is_active:
        raise UnauthorizedException(detail="Account is deactivated")

    return user


# ── Admin check ─────────────────────────────────────────────────────────────
def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user is an admin."""
    if not current_user.is_admin:
        raise ForbiddenException()
    return current_user

"""
Authentication service — login, token creation, user registration.
"""

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate
from app.utils.exceptions import ConflictException, UnauthorizedException
from app.utils.security import create_access_token, hash_password, verify_password


class AuthService:

    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def authenticate(self, login_data: LoginRequest) -> TokenResponse:
        """Validate credentials and return a JWT token."""
        user = self.user_repo.get_by_email(login_data.email)
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise UnauthorizedException(detail="Invalid email or password")
        if not user.is_active:
            raise UnauthorizedException(detail="Account is deactivated")

        token = create_access_token(
            data={"sub": user.id, "email": user.email, "is_admin": user.is_admin}
        )
        return TokenResponse(access_token=token)

    def register(self, data: UserCreate) -> User:
        """Register a new user."""
        existing = self.user_repo.get_by_email(data.email)
        if existing:
            raise ConflictException(detail="Email already registered")

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )
        return self.user_repo.create(user)

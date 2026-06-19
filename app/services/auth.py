import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate
from app.utils.exceptions import ConflictException, UnauthorizedException
from app.utils.security import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)


class AuthService:

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_refresh_token(self, user_id: str, parent_token_id: Optional[str] = None) -> str:
        """Create a new refresh token in database (valid for 7 days)."""
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        token_record = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            parent_token_id=parent_token_id,
            is_revoked=False
        )
        self.db.add(token_record)
        self.db.commit()
        return raw_token

    def rotate_refresh_token(self, raw_refresh_token: str) -> TokenResponse:
        """Rotate the refresh token: revoke current token and return a new access/refresh pair."""
        token_hash = self._hash_token(raw_refresh_token)
        token_record = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()

        if not token_record:
            logger.warning("Attempted rotation with non-existent token hash")
            raise UnauthorizedException(detail="Invalid refresh token")

        user = self.user_repo.get_by_id(token_record.user_id)
        if not user or not user.is_active:
            raise UnauthorizedException(detail="User is inactive or not found")

        # ── Reuse detection ──────────────────────────────────────────
        if token_record.is_revoked:
            logger.warning(
                "Potential token reuse attack detected for user %s! Revoking all refresh tokens.",
                user.email
            )
            # Revoke all tokens for this user
            self.db.query(RefreshToken).filter(
                RefreshToken.user_id == user.id
            ).update({"is_revoked": True})
            self.db.commit()
            raise UnauthorizedException(detail="Token reuse detected. All sessions revoked.")

        # ── Expiry detection ─────────────────────────────────────────
        now = datetime.now(timezone.utc)
        if token_record.expires_at < now:
            token_record.is_revoked = True
            self.db.commit()
            raise UnauthorizedException(detail="Refresh token expired")

        # Revoke the current used token
        token_record.is_revoked = True

        # Generate new pair
        new_access_token = create_access_token(
            data={"sub": user.id, "email": user.email, "is_admin": user.is_admin}
        )
        new_refresh_token = self.create_refresh_token(user.id, parent_token_id=token_record.id)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token
        )

    def revoke_refresh_token(self, raw_refresh_token: str) -> None:
        """Revoke a single refresh token (Logout)."""
        token_hash = self._hash_token(raw_refresh_token)
        token_record = self.db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()

        if token_record:
            token_record.is_revoked = True
            self.db.commit()

    def revoke_all_user_tokens(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user (Logout all devices)."""
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id
        ).update({"is_revoked": True})
        self.db.commit()

    def authenticate(self, login_data: LoginRequest) -> TokenResponse:
        """Validate credentials and return a new access/refresh token pair."""
        user = self.user_repo.get_by_email(login_data.email)
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise UnauthorizedException(detail="Invalid email or password")
        if not user.is_active:
            raise UnauthorizedException(detail="Account is deactivated")

        token = create_access_token(
            data={"sub": user.id, "email": user.email, "is_admin": user.is_admin}
        )
        refresh_token = self.create_refresh_token(user.id)
        return TokenResponse(
            access_token=token,
            refresh_token=refresh_token
        )

    def register(self, data: UserCreate) -> User:
        """Register a new user."""
        existing = self.user_repo.get_by_email(data.email)
        if existing:
            raise ConflictException(detail="Email already registered")

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            company_name=data.company_name
        )
        return self.user_repo.create(user)


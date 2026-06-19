"""
User service — business logic for user management.
"""

from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdate
from app.utils.exceptions import NotFoundException


class UserService:

    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def get_user(self, user_id: str) -> User:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException(detail="User not found")
        return user

    def list_users(
        self, page: int = 1, page_size: int = 20
    ) -> Tuple[List[User], int]:
        return self.user_repo.get_all(page=page, page_size=page_size)

    def update_user(self, user_id: str, data: UserUpdate) -> User:
        user = self.get_user(user_id)
        update_data = data.model_dump(exclude_unset=True)
        return self.user_repo.update(user, update_data)

    def delete_user(self, user_id: str) -> None:
        user = self.get_user(user_id)
        self.user_repo.delete(user)

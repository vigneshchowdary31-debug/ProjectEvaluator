"""
Project service — business logic for project management.
"""

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.utils.exceptions import ForbiddenException, NotFoundException


class ProjectService:

    def __init__(self, db: Session):
        self.project_repo = ProjectRepository(db)

    def get_project(self, project_id: str) -> Project:
        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(detail="Project not found")
        return project

    def list_projects(
        self,
        page: int = 1,
        page_size: int = 20,
        current_user: Optional[User] = None,
    ) -> Tuple[List[Project], int]:
        # Admins see all projects; regular users see only their own.
        owner_id = None if (current_user and current_user.is_admin) else (
            current_user.id if current_user else None
        )
        return self.project_repo.get_all(
            page=page, page_size=page_size, owner_id=owner_id
        )

    def create_project(self, data: ProjectCreate, owner_id: str) -> Project:
        project = Project(
            name=data.name,
            description=data.description,
            repository_url=data.repository_url,
            prd_url=data.prd_url,
            deployment_url=data.deployment_url,
            owner_id=owner_id,
        )
        return self.project_repo.create(project)

    def update_project(
        self, project_id: str, data: ProjectUpdate, current_user: User
    ) -> Project:
        project = self.get_project(project_id)
        self._check_ownership(project, current_user)
        update_data = data.model_dump(exclude_unset=True)
        # Convert enum values to strings for DB storage
        if "status" in update_data and update_data["status"] is not None:
            update_data["status"] = update_data["status"].value if hasattr(update_data["status"], "value") else update_data["status"]
        return self.project_repo.update(project, update_data)

    def delete_project(self, project_id: str, current_user: User) -> None:
        project = self.get_project(project_id)
        self._check_ownership(project, current_user)
        self.project_repo.delete(project)

    @staticmethod
    def _check_ownership(project: Project, user: User) -> None:
        """Ensure the user owns the project or is an admin."""
        if not user.is_admin and project.owner_id != user.id:
            raise ForbiddenException(detail="You do not own this project")

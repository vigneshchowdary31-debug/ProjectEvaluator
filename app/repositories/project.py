"""
Project repository — data-access layer for Project model.
"""

from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.project import Project


class ProjectRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, project_id: str) -> Optional[Project]:
        return self.db.get(Project, project_id)

    def get_all(
        self, page: int = 1, page_size: int = 20, owner_id: Optional[str] = None
    ) -> Tuple[List[Project], int]:
        count_stmt = select(func.count(Project.id))
        data_stmt = select(Project)

        if owner_id:
            count_stmt = count_stmt.where(Project.owner_id == owner_id)
            data_stmt = data_stmt.where(Project.owner_id == owner_id)

        total = self.db.execute(count_stmt).scalar() or 0
        offset = (page - 1) * page_size
        data_stmt = data_stmt.offset(offset).limit(page_size).order_by(
            Project.created_at.desc()
        )
        projects = list(self.db.execute(data_stmt).scalars().all())
        return projects, total

    def get_by_owner(self, owner_id: str) -> List[Project]:
        stmt = select(Project).where(Project.owner_id == owner_id)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, project: Project) -> Project:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update(self, project: Project, data: dict) -> Project:
        for key, value in data.items():
            setattr(project, key, value)
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete(self, project: Project) -> None:
        self.db.delete(project)
        self.db.commit()

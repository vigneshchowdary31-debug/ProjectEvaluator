"""
Import all models so that Base.metadata is fully populated.
"""

from app.models.user import User  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.audit_run import AuditRun  # noqa: F401

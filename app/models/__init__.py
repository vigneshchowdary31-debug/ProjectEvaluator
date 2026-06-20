"""
Import all models so that Base.metadata is fully populated.
"""

from app.models.user import User  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.audit_run import AuditRun  # noqa: F401
from app.models.github_analysis import GithubAnalysis  # noqa: F401
from app.models.generated_report import GeneratedReport  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.evidence import Evidence  # noqa: F401
from app.models.rbac_result import RBACAuditResult  # noqa: F401



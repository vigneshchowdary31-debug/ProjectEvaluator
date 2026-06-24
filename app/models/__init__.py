"""
Import all models so that Base.metadata is fully populated.
"""

from app.models.user import User  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.audit_run import AuditRun  # noqa: F401
from app.models.github_analysis import GithubAnalysis  # noqa: F401
from app.models.project_report import ProjectReport  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.evidence import Evidence  # noqa: F401
from app.models.rbac_result import RBACAuditResult  # noqa: F401
from app.models.auth_audit_result import AuthAuditResult  # noqa: F401
from app.models.sheet_connection import SheetConnection  # noqa: F401
from app.models.import_job import ImportJob  # noqa: F401
from app.models.project_sync_history import ProjectSyncHistory  # noqa: F401
from app.models.project_approval import ProjectApproval  # noqa: F401
from app.models.audit_queue import AuditQueue  # noqa: F401
from app.models.company_portfolio import CompanyPortfolio  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.llm_provider_config import LLMProviderConfig  # noqa: F401




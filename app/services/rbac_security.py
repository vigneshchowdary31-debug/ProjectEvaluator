"""
RBAC Security Engine — evaluates authentication, authorization, and session security
for audited projects based on Playwright crawl results and static scans.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from app.models.project import Project
from app.schemas.browser_audit import BrowserAuditResponse, PageAuditResult
from app.schemas.rbac import (
    RBACCoverageRow,
    RBACFindingDetail,
    RBACViolationDetail,
)

logger = logging.getLogger(__name__)


class RBACSecurityEngine:
    """Evaluates security ratings and builds matrices/findings for project RBAC controls."""

    def __init__(self) -> None:
        pass

    def evaluate(self, project: Project, browser_result: Optional[BrowserAuditResponse], has_credentials: bool = False) -> Dict[str, Any]:
        """
        Scan browser crawl outputs and project configurations to calculate security scores,
        compile role coverage matrices, identify privilege violations, and generate findings.
        """
        # If RBAC is disabled or no browser results are available or credentials missing, return defaults
        if not project.rbac_enabled or not browser_result or not has_credentials:
            return {
                "status": "UNTESTED",
                "auth_score": 0.0,
                "authz_score": 0.0,
                "session_score": 0.0,
                "overall_score": 0.0,
                "role_coverage_matrix": "[]",
                "violations": "[]",
                "findings": "[]",
            }


        # Initialize ratings
        auth_score = 100.0
        authz_score = 100.0
        session_score = 100.0

        findings: List[RBACFindingDetail] = []
        violations: List[RBACViolationDetail] = []
        coverage_rows: List[RBACCoverageRow] = []

        # Tracks login success
        user_login_success = False
        admin_login_success = False
        user_login_attempted = False
        admin_login_attempted = False

        # Gather page paths to build a role access mapping
        # E.g., map page path -> role -> PageAuditResult
        page_role_map: Dict[str, Dict[str, PageAuditResult]] = {}
        for p in browser_result.pages_audited:
            parsed = urlparse(p.url)
            path = parsed.path if parsed.path else "/"
            if path not in page_role_map:
                page_role_map[path] = {}
            page_role_map[path][p.role] = p

        # 1. Evaluate Authentication Security
        # We can infer login attempts/successes from crawled roles and console/error logs
        # Guest is always run. If User/Admin are present in crawled pages, those logins succeeded.
        roles_run = {p.role for p in browser_result.pages_audited}
        
        # If credentials were configured in DB (which we check via Project)
        if project.secret_reference:
            # We can check if any page was successfully visited under User/Admin roles
            user_login_attempted = True
            admin_login_attempted = True
            
            user_login_success = "User" in roles_run
            admin_login_success = "Admin" in roles_run

        if user_login_attempted and not user_login_success:
            auth_score -= 40.0
            findings.append(RBACFindingDetail(
                category="AUTH",
                title="Regular User Authentication Failure",
                description="The crawler was unable to log in as a regular user with the provided credentials. This could indicate a broken login endpoint, incorrect form input selectors, or invalid credentials.",
                severity="high",
                recommendation="Verify regular user login credentials and login page selectors. Ensure the authentication endpoint is functional."
            ))
        
        if admin_login_attempted and not admin_login_success:
            auth_score -= 40.0
            findings.append(RBACFindingDetail(
                category="AUTH",
                title="Admin Authentication Failure",
                description="The crawler was unable to log in as an administrator. This is critical as administrative screens could not be fully audited.",
                severity="high",
                recommendation="Verify administrative credentials and selectors. Ensure the admin authentication portal is accessible and functional."
            ))

        # Check for password toggle visibility
        # If we see any password toggle check in the crawler errors or logs
        # Or if we scan the console logs and find password-related issues
        password_toggle_missing = True
        for p in browser_result.pages_audited:
            for f in p.form_submission_results:
                for fd in f.fields_tested:
                    if fd.field_type == "password":
                        # If a password field was tested, we can assume a toggle exists or check if we can toggle it
                        # Since browser_audit does a toggle test, we check if it is logged
                        pass

        # Check console logs for login pages
        login_console_errors = 0
        for p in browser_result.pages_audited:
            if "login" in p.url.lower() or "signin" in p.url.lower():
                login_console_errors += len(p.console_errors)

        if login_console_errors > 0:
            auth_score -= min(15.0, login_console_errors * 5.0)
            findings.append(RBACFindingDetail(
                category="AUTH",
                title="Console Errors during Authentication",
                description=f"Detected {login_console_errors} console errors or exceptions during the authentication process.",
                severity="medium",
                recommendation="Investigate client-side exceptions during authentication and resolve console errors."
            ))

        # 2. Evaluate Authorization Security (Privilege boundaries)
        # Scan page results for access statuses
        for p in browser_result.pages_audited:
            parsed = urlparse(p.url)
            path = parsed.path if parsed.path else "/"
            
            # Map access status to coverage status
            status_str = "ALLOWED"
            if p.access_status == "blocked" or (p.status_code and p.status_code >= 400):
                status_str = "BLOCKED"
            elif p.access_status == "escalated":
                status_str = "PRIVILEGE_ESCALATION"

            coverage_rows.append(RBACCoverageRow(
                page=path,
                role=p.role,
                status=status_str,
                url=p.url,
                screenshot_url=p.desktop_screenshot_url
            ))

            # Detect Privilege Escalations
            # Escalation occurs if a regular User or Guest has status code < 400 on Admin pages,
            # or if `access_status` is explicitly set to `escalated` by Playwright crawler
            is_admin_path = project.admin_url and project.admin_url.lower() in p.url.lower()
            if not is_admin_path:
                # Also check common admin paths if project.admin_url is not configured
                is_admin_path = "/admin" in path.lower() or "/dashboard/admin" in path.lower()

            if is_admin_path and p.role in ("Guest", "User"):
                # If they got a successful response
                if p.status_code and p.status_code < 400 and status_str != "BLOCKED":
                    authz_score -= 40.0
                    violation_desc = f"{p.role} successfully accessed admin page at {path} (HTTP {p.status_code})."
                    violations.append(RBACViolationDetail(
                        source_role=p.role,
                        target_route=path,
                        result=f"HTTP {p.status_code} OK",
                        severity="critical",
                        description=violation_desc
                    ))
                    findings.append(RBACFindingDetail(
                        category="AUTHZ",
                        title=f"Administrative Privilege Escalation ({p.role} -> Admin)",
                        description=f"A {p.role} user is able to access the restricted path '{path}' without proper authorization checks.",
                        severity="critical",
                        recommendation="Implement backend router middleware / route guards to verify caller roles and restrict access to administrative API and page routes."
                    ))

            # Detect unauthorized access for Guest to dashboard
            is_dashboard_path = project.user_url and project.user_url.lower() in p.url.lower()
            if not is_dashboard_path:
                is_dashboard_path = "/dashboard" in path.lower() or "/profile" in path.lower() or "/settings" in path.lower()

            if is_dashboard_path and p.role == "Guest":
                if p.status_code and p.status_code < 400 and status_str != "BLOCKED":
                    authz_score -= 20.0
                    violation_desc = f"Guest successfully accessed user dashboard page at {path} (HTTP {p.status_code})."
                    violations.append(RBACViolationDetail(
                        source_role="Guest",
                        target_route=path,
                        result=f"HTTP {p.status_code} OK",
                        severity="high",
                        description=violation_desc
                    ))
                    findings.append(RBACFindingDetail(
                        category="AUTHZ",
                        title="Broken Authentication (Guest -> Dashboard)",
                        description=f"Unauthenticated Guest session allowed access to protected user route '{path}'.",
                        severity="high",
                        recommendation="Redirect unauthenticated sessions to the login portal and enforce session token verification on page load."
                    ))

        # 3. Evaluate Session Security
        # Enforce HTTPS
        parsed_deployment = urlparse(project.deployment_url)
        if parsed_deployment.scheme == "http":
            session_score -= 30.0
            findings.append(RBACFindingDetail(
                category="SESSION",
                title="Insecure Session Transmission (HTTP)",
                description="The deployment URL uses HTTP rather than HTTPS. Session tokens, cookies, and credentials are transmitted in plaintext and are vulnerable to interception.",
                severity="high",
                recommendation="Configure an SSL/TLS certificate and redirect all HTTP traffic to HTTPS. Enable 'Secure' flag on cookies."
            ))

        # Check console logs for localStorage / XSS indicators
        storage_warnings = 0
        for p in browser_result.pages_audited:
            for log in p.console_errors:
                if "localstorage" in log.lower() or "sessionstorage" in log.lower() or "jwt" in log.lower():
                    storage_warnings += 1

        if storage_warnings > 0:
            session_score -= min(15.0, storage_warnings * 5.0)
            findings.append(RBACFindingDetail(
                category="SESSION",
                title="Potential XSS Session Theft Risk",
                description="Console logs or scripts indicate session keys or JWTs are being stored in localStorage or sessionStorage, making them vulnerable to Cross-Site Scripting (XSS) extraction.",
                severity="medium",
                recommendation="Store authentication tokens in HttpOnly, Secure, SameSite=Strict cookies to protect against client-side script access."
            ))

        # Check for cookie issues in console logs
        cookie_warnings = 0
        for p in browser_result.pages_audited:
            for log in p.console_errors:
                if "samesite" in log.lower() or "cookie" in log.lower():
                    cookie_warnings += 1

        if cookie_warnings > 0:
            session_score -= min(10.0, cookie_warnings * 2.0)
            findings.append(RBACFindingDetail(
                category="SESSION",
                title="SameSite / Cookie Configuration Warnings",
                description="Browser console emitted SameSite cookie policy warnings. This may lead to sessions getting blocked on modern browsers.",
                severity="low",
                recommendation="Update session cookie attributes to explicitly define SameSite=Lax or SameSite=Strict and set Secure flag."
            ))

        # Clamp scores
        auth_score = max(0.0, min(100.0, auth_score))
        authz_score = max(0.0, min(100.0, authz_score))
        session_score = max(0.0, min(100.0, session_score))

        # Calculate Overall Score (Weighted)
        # 30% Auth, 50% Authz, 20% Session
        overall_score = (0.3 * auth_score) + (0.5 * authz_score) + (0.2 * session_score)
        overall_score = max(0.0, min(100.0, overall_score))

        # Convert outputs to JSON lists to match schema storage
        import json
        
        # Serialize to match DB model schema
        coverage_rows_serialized = json.dumps([row.model_dump() for row in coverage_rows])
        violations_serialized = json.dumps([v.model_dump() for v in violations])
        findings_serialized = json.dumps([f.model_dump() for f in findings])

        return {
            "status": "COMPLETED",
            "auth_score": auth_score,
            "authz_score": authz_score,
            "session_score": session_score,
            "overall_score": overall_score,
            "role_coverage_matrix": coverage_rows_serialized,
            "violations": violations_serialized,
            "findings": findings_serialized,
        }

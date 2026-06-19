"""
Advanced Security Engine — analyzes repositories for hardcoded secrets, weak configs,
CORS misconfigurations, vulnerable dependencies, and maps findings to OWASP Top 10.
"""

import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Heuristics & regexes for secret keys, credentials, tokens
SECRETS_REGEXES = [
    (re.compile(r"(?:api[_-]?key|apikey|secret[_-]?key|private[_-]?key|client[_-]?secret)\s*[:=]\s*['\"].+['\"]", re.IGNORECASE), "A02:2021-Cryptographic Failures", "Hardcoded API or Secret Key"),
    (re.compile(r"password\s*[:=]\s*['\"][^'\"]{6,}['\"]", re.IGNORECASE), "A07:2021-Identification and Authentication Failures", "Hardcoded Cleartext Password"),
    (re.compile(r"aws_[a-z_]*key[a-z_]*\s*[:=]\s*['\"].+['\"]", re.IGNORECASE), "A02:2021-Cryptographic Failures", "Hardcoded AWS Credentials"),
    (re.compile(r"jwt[_-]?secret\s*[:=]\s*['\"].+['\"]", re.IGNORECASE), "A02:2021-Cryptographic Failures", "Hardcoded JWT Secret String"),
    (re.compile(r"bearer\s+[a-f0-9\-_]{20,}", re.IGNORECASE), "A02:2021-Cryptographic Failures", "Exposed Bearer Token String"),
]

# Common vulnerable libraries (python/js)
VULNERABLE_DEPS = [
    (re.compile(r"pyjwt\s*(?:==|<=|<)\s*(?:[0-1]\..*|2\.[0-3]\..*)", re.IGNORECASE), "PyJWT < 2.4.0", "A02:2021-Cryptographic Failures", "Critical Key Confusion vulnerability in PyJWT signature validation."),
    (re.compile(r"requests\s*(?:==|<=|<)\s*(?:[0-1]\..*|2\.[0-2]\d\..*|2\.30\..*)", re.IGNORECASE), "Requests < 2.31.0", "A05:2021-Security Misconfiguration", "Requests leaks Authorization headers across cross-domain redirects."),
    (re.compile(r"urllib3\s*(?:==|<=|<)\s*(?:1\.[0-2][0-5]\..*|1\.26\.[0-9]\b|1\.26\.1[0-6]\b|2\.0\.[0-6]\b)", re.IGNORECASE), "urllib3 < 1.26.17 / 2.0.7", "A05:2021-Security Misconfiguration", "urllib3 Request Body Leakage during HTTP redirects."),
    (re.compile(r"jinja2\s*(?:==|<=|<)\s*(?:[0-2]\..*|3\.0\..*|3\.1\.[0-2]\b)", re.IGNORECASE), "Jinja2 < 3.1.3", "A03:2021-Injection", "Jinja2 HTML rendering sandbox escape vulnerability via crafted templates."),
    (re.compile(r"cryptography\s*(?:==|<=|<)\s*(?:[0-9]\..*|[0-3]\d\..*|41\.0\.[0-5]\b)", re.IGNORECASE), "cryptography < 41.0.6", "A02:2021-Cryptographic Failures", "Cryptography library memory corruption vulnerabilities in RSA key parsing."),
]


class SecurityFinding:
    def __init__(
        self,
        title: str,
        description: str,
        severity: str,
        impact: str,
        likelihood: str,
        recommendation: str,
        fix_priority: str,
        owasp_category: str,
        file_path: Optional[str] = None,
        line_range: Optional[str] = None,
    ):
        self.title = title
        self.description = description
        self.severity = severity  # low | medium | high | critical
        self.impact = impact
        self.likelihood = likelihood
        self.recommendation = recommendation
        self.fix_priority = fix_priority  # low | medium | high | immediate
        self.owasp_category = owasp_category  # e.g., A01:2021-Broken Access Control
        self.file_path = file_path
        self.line_range = line_range

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "impact": self.impact,
            "likelihood": self.likelihood,
            "recommendation": self.recommendation,
            "fix_priority": self.fix_priority,
            "owasp_category": self.owasp_category,
            "file_path": self.file_path,
            "line_range": self.line_range,
        }


class AdvancedSecurityEngine:
    """Analyzes codebase directory list and manifest contents for security flaws."""

    def __init__(self):
        pass

    def scan(self, file_paths: List[str], manifest_contents: Dict[str, str]) -> List[SecurityFinding]:
        findings: List[SecurityFinding] = []

        # 1. Scan file paths for exposed secrets, configurations or files checked in by mistake
        for path in file_paths:
            filename = path.split("/")[-1].lower()
            if filename == ".env":
                findings.append(SecurityFinding(
                    title="Environment Configuration File (.env) Committed",
                    description=f"The environment variables file '{path}' is checked into source control. This leaks production keys, secrets, and API credentials.",
                    severity="high",
                    impact="Exposes sensitive production API keys, database paths, and secrets.",
                    likelihood="high",
                    recommendation="Remove the '.env' file from the Git index and add it to your '.gitignore'. Re-generate any leaked credentials immediately.",
                    fix_priority="immediate",
                    owasp_category="A05:2021-Security Misconfiguration",
                    file_path=path
                ))
            elif filename in ("id_rsa", "id_dsa", "credentials.json", "service-account.json"):
                findings.append(SecurityFinding(
                    title="Sensitive Credentials File Committed",
                    description=f"Sensitive key/credentials file '{path}' is checked into repository.",
                    severity="critical",
                    impact="Enables malicious entities to directly authenticate as users/servers.",
                    likelihood="high",
                    recommendation="Delete this file from Git repository immediately. Add the filename to '.gitignore'. Revoke the exposed keys immediately.",
                    fix_priority="immediate",
                    owasp_category="A05:2021-Security Misconfiguration",
                    file_path=path
                ))

        # 2. Scan manifest file contents for vulnerable dependencies
        for path, content in manifest_contents.items():
            filename = path.split("/")[-1]
            lines = content.splitlines()

            # Process requirements.txt
            if filename == "requirements.txt":
                for i, line in enumerate(lines):
                    for pattern, lib_name, owasp, desc in VULNERABLE_DEPS:
                        if pattern.search(line):
                            findings.append(SecurityFinding(
                                title=f"Vulnerable Dependency: {lib_name}",
                                description=f"The dependency line '{line.strip()}' in '{path}' specifies a vulnerable version. {desc}",
                                severity="high",
                                impact="Exposes the running backend to known high-severity CVE vulnerabilities.",
                                likelihood="medium",
                                recommendation=f"Upgrade the '{lib_name.split()[0].lower()}' dependency to the latest secure release version.",
                                fix_priority="high",
                                owasp_category=owasp,
                                file_path=path,
                                line_range=f"{i+1}"
                            ))

            # Scan manifest files for hardcoded secrets or passwords using regexes
            for i, line in enumerate(lines):
                # Only check code lines or configurations, skipping massive lines
                if len(line) > 1000:
                    continue
                for regex, owasp, title in SECRETS_REGEXES:
                    match = regex.search(line)
                    if match:
                        findings.append(SecurityFinding(
                            title=title,
                            description=f"A possible secret string was matched in '{path}' on line {i+1}: '{line.strip()[:60]}...'",
                            severity="high",
                            impact="Hardcoded secrets can be extracted by anyone with access to the source code.",
                            likelihood="high",
                            recommendation="Remove the hardcoded secret and replace it with environment variables dynamically loaded at startup.",
                            fix_priority="immediate",
                            owasp_category=owasp,
                            file_path=path,
                            line_range=f"{i+1}"
                        ))

            # Check CORS configurations inside python files
            if filename.endswith(".py"):
                for i, line in enumerate(lines):
                    if "allow_origins" in line and ("*" in line or "all" in line.lower()):
                        findings.append(SecurityFinding(
                            title="Wildcard CORS Configuration",
                            description=f"Found permissive CORS configuration on line {i+1} in '{path}': '{line.strip()}'",
                            severity="medium",
                            impact="Allows malicious web domains to run client-side scripts against this API endpoint on behalf of users.",
                            likelihood="high",
                            recommendation="Define strict origins instead of wildcard('*') or load them dynamically from configuration settings.",
                            fix_priority="medium",
                            owasp_category="A01:2021-Broken Access Control",
                            file_path=path,
                            line_range=f"{i+1}"
                        ))

        # Add default architectural security checks if no specific secrets are found
        # (e.g. check for HTTPS validation, CSRF, secure cookie session)
        has_main_py = any(p.endswith("main.py") for p in file_paths)
        if has_main_py:
            # Look at main.py contents for standard security middlewares
            main_path = next(p for p in file_paths if p.endswith("main.py"))
            main_content = manifest_contents.get(main_path, "")
            
            # Check for security headers middleware (e.g. helmet in express, secureheader in fastpage)
            if "SecureHeader" not in main_content and "HTTPSRedirectMiddleware" not in main_content:
                findings.append(SecurityFinding(
                    title="Missing HTTP Security Headers / HTTPS Redirects",
                    description="The main entry point main.py does not enforce HTTPS redirects or attach standard HTTP security headers (CSP, X-Frame-Options, HSTS).",
                    severity="medium",
                    impact="Makes client browsers vulnerable to Clickjacking, MIME-sniffing, or protocol downgrade attacks.",
                    likelihood="medium",
                    recommendation="Add standard middleware to enforce HTTPS redirects and attach security headers (e.g. Content-Security-Policy: default-src 'self').",
                    fix_priority="high",
                    owasp_category="A05:2021-Security Misconfiguration",
                    file_path=main_path
                ))

        return findings

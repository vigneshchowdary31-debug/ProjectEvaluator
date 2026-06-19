"""
Gemini Integration Service — sends PRD text to Google Gemini
and parses the structured JSON response.

Uses the google-generativeai SDK with structured output (JSON mode).
"""

import json
import logging
from typing import Optional
from pydantic import BaseModel

from google import genai
from google.genai import types

from app.config import get_settings
from app.schemas.prd import PRDAnalysisResult
from app.schemas.github import GithubAnalysisResultSchema
from app.schemas.browser_audit import BrowserAuditResponse
from app.schemas.requirement_matching import RequirementMatchingResult
from app.schemas.report_generation import StudentReportSchema, CompanyReportSchema

# Wrapper schema for Gemini multi-report generation
class GeminiGeneratedReportWrapper(BaseModel):
    student_report: StudentReportSchema
    company_report: CompanyReportSchema

logger = logging.getLogger(__name__)

# ── Prompts ──────────────────────────────────────────────────────────────────

REPORT_GENERATOR_SYSTEM_INSTRUCTION = """You are an expert technical evaluator and professional software auditor.
Your task is to compile a detailed, audience-tailored project audit.
You MUST return valid JSON matching the schema provided containing both `student_report` and `company_report`. Do not include any text outside the JSON object.

Student Report focus: educational, highlighting programming mistakes, best practices, refactoring recommendations, and clear tutoring notes.
Company Report focus: executive-level progress, product readiness, risk profiles (dependencies/security), maintainability, and strategic release advice.
"""

REPORT_GENERATOR_PROMPT = """Create two separate, comprehensive project reports (one for a Student Developer, one for a corporate Client Company) based on these gathered audit findings:

1. **Expected requirements (PRD Findings)**:
- Pages expected: {prd_pages}
- Features expected: {prd_features}
- User flows expected: {prd_user_flows}

2. **Codebase details (GitHub Findings)**:
- Languages & Tools: {github_tech}
- Configured Frameworks: {github_frameworks}
- Discovered components: {github_components}
- Architectural findings: {github_rating}. Strengths: {github_strengths}. Weaknesses: {github_weaknesses}

3. **Live crawler execution (Browser Findings)**:
- Pages visited: {browser_pages}
- Errors intercepted: {browser_errors}
- Broken links: {browser_broken_links}
- Form test results: {browser_form_tests}

4. **Requirement gap analysis (Matching Findings)**:
- Implemented: {match_implemented}
- Partially implemented: {match_partial}
- Completely missing: {match_missing}
- Base implementation completion percentage: {calc_percentage:.1f}%

---

Ensure BOTH reports include detailed lists for:
- Completion Percentage (use {calc_percentage:.1f}% as your starting reference point)
- Features Implemented
- Missing Features
- Security Findings
- UI Findings
- Code Quality Findings
- Recommendations

For the Student Report, write an educational `educational_notes` section.
For the Company Report, write a professional executive-level `executive_summary` section.
"""

MATCHING_SYSTEM_INSTRUCTION = """You are an expert software quality assurance auditor and systems analyst.
Your task is to compare product requirements (PRD Findings) against codebase structure (GitHub Findings) and live web crawler logs (Browser Findings) to perform a gap analysis.

You MUST return valid JSON that conforms exactly to the schema provided. Do not include any text outside the JSON object.
Be objective and trace each requirement carefully to find corresponding files, features, or page components.
"""

MATCHING_ANALYSIS_PROMPT = """You are auditing a software implementation against its product specifications. Compare the requirements with the codebase and web browser findings:

1. **Expected Requirements (PRD Findings)**:
- Expected Pages/Screens: {prd_pages}
- Expected Features: {prd_features}
- Expected Forms: {prd_forms}
- Expected User Flows: {prd_user_flows}

2. **Codebase Implementation Details (GitHub Findings)**:
- Tech Stack: {github_tech}
- Codebase Components: {github_components}
- Codebase Pages: {github_pages}
- File Tree Structure: {github_tree}

3. **Live Site Crawl Details (Browser Findings)**:
- Visited URLs: {browser_pages}
- Encounted Console Errors: {browser_errors}
- Tested Forms: {browser_forms}

---

Your task is to perform a gap analysis. Classify each expected feature/page/form from the PRD findings into one of:
1. **implemented_features**: Fully implemented. Cite files or page links as evidence.
2. **partially_implemented_features**: Partially implemented (e.g., page exists, but some forms or validation rules are missing, or a user flow step failed). Describe what is completed and what is missing.
3. **missing_features**: Expected in PRD, but not found in codebase or crawler. State its priority.

Provide a `confidence_score` (between 0.0 and 1.0) based on the visibility and matches found, and an executive `summary` of the audit.
"""

GITHUB_SYSTEM_INSTRUCTION = """You are an expert software architect, security auditor, and codebase analyst.
Your task is to analyze a GitHub repository's folder structure, config/manifest files, and dependency list to extract detailed project insights.

You MUST return valid JSON that conforms exactly to the schema provided. Do not include any text outside the JSON object.
Be thorough and objective in your security issues and architectural quality rating.
"""

GITHUB_ANALYSIS_PROMPT = """Analyze the following GitHub repository details:

Repository Name: {repo_name}

1. **Folder Structure (JSON Tree)**:
{folder_tree_json}

2. **Package Manifest / Configuration Files**:
{manifest_contents_text}

---

Your task is to analyze these details and extract:
1. **technologies**: Languages, build tools, databases (e.g. Python, TypeScript, SQLite, PostgreSQL).
2. **frameworks**: Frameworks and major libraries (e.g. FastAPI, React, Angular, TailwindCSS, SQLAlchemy, JUnit).
3. **pages**: Main pages/screens (for frontends) or key API endpoints/routers (for backends). Include name, route/method, file_path, and a short description.
4. **components**: Reuseable UI components or backend modular services (repositories, services, context providers, controllers, hooks).
5. **folder_structure**: Recreate or simplify the nested directory structure provided to you.
6. **security_issues**: List potential vulnerabilities or configuration flaws evident from dependencies or folder structure (e.g. missing security headers, use of vulnerable dependencies, cleartext storage configs). For each, specify severity (high, medium, low), issue title, file_path, and description.
7. **architecture_quality**: Assess codebase organization, strengths (e.g., modularity, separation of concerns), weaknesses, and recommendations. Provide a rating (excellent, good, fair, poor).

Ensure all file paths cited correspond to actual files present in the folder structure.
"""

# ── PRD Prompts ──────────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = """You are an expert product analyst and software architect.
Your task is to analyze Product Requirements Documents (PRDs) and extract structured information.

You MUST return valid JSON that conforms exactly to the schema below. Do not include any text outside the JSON object.
Be thorough — extract every page, feature, form, and user flow mentioned or implied in the document.

If the document does not mention a category (e.g., no forms), return an empty array for that field.
"""

ANALYSIS_PROMPT = """Analyze the following Product Requirements Document (PRD) and extract ALL of the following into structured JSON:

1. **pages**: Every page/screen described or implied. For each page include:
   - name: Page name
   - route: Suggested route path (e.g., "/dashboard")
   - description: What this page does
   - components: List of UI components on the page, each with name, type, and description
   - connected_pages: Names of other pages this page links to

2. **features**: Every feature described. For each feature include:
   - name: Feature name
   - description: Detailed description
   - priority: One of "must_have", "should_have", "nice_to_have"
   - acceptance_criteria: List of testable acceptance criteria
   - related_pages: Which pages this feature appears on

3. **forms**: Every form described or implied. For each form include:
   - name: Form name
   - description: Purpose of the form
   - page: Which page the form is on
   - fields: List of form fields, each with:
     - name: Field label
     - field_type: One of "text", "email", "password", "number", "date", "select", "checkbox", "radio", "textarea", "file", "toggle", "other"
     - required: true/false
     - validation_rules: List of validation rules
     - options: List of options (for select/radio/checkbox)
   - submit_action: What happens when the form is submitted

4. **user_flows**: Every user flow/journey. For each flow include:
   - name: Flow name
   - description: High-level summary
   - actor: Who performs this flow (e.g., "User", "Admin")
   - preconditions: What must be true before the flow starts
   - steps: Ordered list of steps, each with step_number, action, page, and expected_result
   - postconditions: What is true after the flow completes

Return ONLY the JSON object with keys: pages, features, forms, user_flows.

---

PRD DOCUMENT:

{document_text}
"""


class GeminiError(Exception):
    """Raised when Gemini API interaction fails."""
    pass


class GeminiService:
    """Interact with Google Gemini to analyze PRD documents."""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL

        if not self.api_key:
            raise GeminiError(
                "GEMINI_API_KEY is not configured. "
                "Set it in your .env file."
            )

        self.client = genai.Client(api_key=self.api_key)

    def analyze_prd(self, document_text: str) -> PRDAnalysisResult:
        """
        Send PRD text to Gemini and return a validated PRDAnalysisResult.

        Args:
            document_text: The extracted text from the PRD document.

        Returns:
            PRDAnalysisResult with pages, features, forms, and user_flows.

        Raises:
            GeminiError: If the API call or response parsing fails.
        """
        if not document_text.strip():
            raise GeminiError("Document text is empty. Nothing to analyze.")

        # ── Truncate if excessively long ────────────────────────────────
        max_chars = 500_000  # ~125K tokens approx
        if len(document_text) > max_chars:
            logger.warning(
                "Document text truncated from %d to %d chars",
                len(document_text),
                max_chars,
            )
            document_text = document_text[:max_chars]

        prompt = ANALYSIS_PROMPT.format(document_text=document_text)

        logger.info(
            "Sending PRD to Gemini (%s) — %d chars",
            self.model_name,
            len(document_text),
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=PRDAnalysisResult,
                    temperature=0.1,  # Low temperature for structured output
                ),
            )

            if not response.text:
                raise GeminiError("Gemini returned an empty response.")

            logger.debug("Raw Gemini response: %s", response.text[:500])

        except Exception as e:
            if isinstance(e, GeminiError):
                raise
            raise GeminiError(f"Gemini API call failed: {str(e)}")

        # ── Parse and validate ──────────────────────────────────────────
        try:
            if hasattr(response, "parsed") and response.parsed is not None:
                return response.parsed
        except Exception as e:
            logger.warning("Failed to access response.parsed directly: %s. Falling back to manual JSON parsing.", str(e))

        return self._parse_response(response.text)

    def _parse_response(self, raw_response: str) -> PRDAnalysisResult:
        """
        Parse the raw Gemini response into a validated PRDAnalysisResult.

        Handles edge cases like markdown code fences in the response.
        """
        cleaned = self._clean_json_response(raw_response)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini response as JSON: %s", str(e))
            logger.debug("Raw response: %s", raw_response[:1000])
            raise GeminiError(
                f"Gemini returned invalid JSON: {str(e)}. "
                "This may be a transient issue — try again."
            )

        # Validate with Pydantic
        try:
            result = PRDAnalysisResult.model_validate(data)
        except Exception as e:
            logger.error("Pydantic validation failed: %s", str(e))
            raise GeminiError(
                f"Gemini response did not match expected schema: {str(e)}"
            )

        logger.info(
            "PRD analysis complete — %d pages, %d features, %d forms, %d user_flows",
            len(result.pages),
            len(result.features),
            len(result.forms),
            len(result.user_flows),
        )

        return result

    def analyze_github(self, repo_name: str, folder_tree: dict, manifest_contents: dict) -> GithubAnalysisResultSchema:
        """
        Send repository details to Gemini and return a validated GithubAnalysisResultSchema.
        """
        # Format inputs
        folder_tree_json = json.dumps(folder_tree, indent=2)
        
        manifests_list = []
        for path, content in manifest_contents.items():
            manifests_list.append(f"--- File: {path} ---\n{content}\n")
        manifest_contents_text = "\n".join(manifests_list) if manifests_list else "No manifest files found."

        prompt = GITHUB_ANALYSIS_PROMPT.format(
            repo_name=repo_name,
            folder_tree_json=folder_tree_json,
            manifest_contents_text=manifest_contents_text
        )

        logger.info("Sending GitHub repo info to Gemini — %d chars", len(prompt))

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=GITHUB_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=GithubAnalysisResultSchema,
                    temperature=0.1,
                ),
            )

            if not response.text:
                raise GeminiError("Gemini returned an empty response.")

            logger.debug("Raw Gemini response: %s", response.text[:500])

        except Exception as e:
            if isinstance(e, GeminiError):
                raise
            raise GeminiError(f"Gemini API call failed: {str(e)}")

        # ── Parse and validate ──────────────────────────────────────────
        try:
            if hasattr(response, "parsed") and response.parsed is not None:
                return response.parsed
        except Exception as e:
            logger.warning("Failed to access response.parsed directly for Github: %s. Falling back to manual JSON parsing.", str(e))

        return self._parse_github_response(response.text)

    def _parse_github_response(self, raw_response: str) -> GithubAnalysisResultSchema:
        cleaned = self._clean_json_response(raw_response)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini response as JSON: %s", str(e))
            raise GeminiError(f"Gemini returned invalid JSON for GitHub analysis: {str(e)}")

        # Validate with Pydantic
        try:
            result = GithubAnalysisResultSchema.model_validate(data)
        except Exception as e:
            logger.error("Pydantic validation failed for GitHub analysis: %s", str(e))
            raise GeminiError(f"Gemini response did not match expected schema: {str(e)}")

        logger.info(
            "GitHub analysis complete — %d technologies, %d frameworks, %d pages, %d components",
            len(result.technologies),
            len(result.frameworks),
            len(result.pages),
            len(result.components),
        )

        return result

    def analyze_requirement_matching(
        self, prd: PRDAnalysisResult, github: GithubAnalysisResultSchema, browser: Optional[BrowserAuditResponse]
    ) -> RequirementMatchingResult:
        """
        Compare requirements with codebase and web browser findings and return RequirementMatchingResult.
        """
        # Format PRD Inputs
        prd_pages = ", ".join([p.name for p in prd.pages]) or "None"
        prd_features = ", ".join([f.name for f in prd.features]) or "None"
        prd_forms = ", ".join([f.name for f in prd.forms]) or "None"
        prd_user_flows = ", ".join([uf.name for uf in prd.user_flows]) or "None"

        # Format GitHub Inputs
        github_tech = ", ".join(github.technologies) or "None"
        github_components = ", ".join([c.name for c in github.components]) or "None"
        github_pages = ", ".join([p.name for p in github.pages]) or "None"
        github_tree = json.dumps(github.folder_structure, indent=2)

        # Format Browser Inputs
        if browser:
            browser_pages = ", ".join([p.url for p in browser.pages_audited]) or "None"
            
            all_errors = []
            for p in browser.pages_audited:
                all_errors.extend(p.console_errors)
            browser_errors = "; ".join(all_errors) if all_errors else "None"
            
            all_forms = []
            for p in browser.pages_audited:
                all_forms.extend([f.form_action or f.form_id or "unnamed form" for f in p.form_submission_results])
            browser_forms = ", ".join(all_forms) if all_forms else "None"
        else:
            browser_pages = "No browser crawl findings provided."
            browser_errors = "No browser crawl findings provided."
            browser_forms = "No browser crawl findings provided."

        prompt = MATCHING_ANALYSIS_PROMPT.format(
            prd_pages=prd_pages,
            prd_features=prd_features,
            prd_forms=prd_forms,
            prd_user_flows=prd_user_flows,
            github_tech=github_tech,
            github_components=github_components,
            github_pages=github_pages,
            github_tree=github_tree,
            browser_pages=browser_pages,
            browser_errors=browser_errors,
            browser_forms=browser_forms
        )

        logger.info("Sending requirements matching request to Gemini — %d chars", len(prompt))

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=MATCHING_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=RequirementMatchingResult,
                    temperature=0.1,
                ),
            )

            if not response.text:
                raise GeminiError("Gemini returned an empty response.")

            logger.debug("Raw Gemini response: %s", response.text[:500])

        except Exception as e:
            if isinstance(e, GeminiError):
                raise
            raise GeminiError(f"Gemini API call failed: {str(e)}")

        # ── Parse and validate ──────────────────────────────────────────
        try:
            if hasattr(response, "parsed") and response.parsed is not None:
                return response.parsed
        except Exception as e:
            logger.warning("Failed to access response.parsed directly for matching: %s. Falling back to manual JSON parsing.", str(e))

        return self._parse_matching_response(response.text)

    def _parse_matching_response(self, raw_response: str) -> RequirementMatchingResult:
        cleaned = self._clean_json_response(raw_response)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini response as JSON: %s", str(e))
            raise GeminiError(f"Gemini returned invalid JSON for matching: {str(e)}")

        # Validate with Pydantic
        try:
            result = RequirementMatchingResult.model_validate(data)
        except Exception as e:
            logger.error("Pydantic validation failed for matching: %s", str(e))
            raise GeminiError(f"Gemini response did not match expected schema: {str(e)}")

        logger.info(
            "Requirement matching complete — %d implemented, %d partial, %d missing. Confidence: %.2f",
            len(result.implemented_features),
            len(result.partially_implemented_features),
            len(result.missing_features),
            result.confidence_score,
        )

        return result

    def generate_project_reports(
        self,
        prd: PRDAnalysisResult,
        github: GithubAnalysisResultSchema,
        browser: Optional[BrowserAuditResponse],
        matching: RequirementMatchingResult,
        calc_percentage: float
    ) -> GeminiGeneratedReportWrapper:
        """
        Synthesize PRD, GitHub, Browser, and Matching findings into Student and Company reports.
        """
        # Format PRD Inputs
        prd_pages = ", ".join([p.name for p in prd.pages]) or "None"
        prd_features = ", ".join([f.name for f in prd.features]) or "None"
        prd_user_flows = ", ".join([uf.name for uf in prd.user_flows]) or "None"

        # Format GitHub Inputs
        github_tech = ", ".join(github.technologies) or "None"
        github_frameworks = ", ".join(github.frameworks) or "None"
        github_components = ", ".join([c.name for c in github.components]) or "None"
        github_rating = github.architecture_quality.rating
        github_strengths = ", ".join(github.architecture_quality.strengths) or "None"
        github_weaknesses = ", ".join(github.architecture_quality.weaknesses) or "None"

        # Format Browser Inputs
        if browser:
            browser_pages = ", ".join([p.url for p in browser.pages_audited]) or "None"
            
            all_errors = []
            for p in browser.pages_audited:
                all_errors.extend(p.console_errors)
            browser_errors = "; ".join(all_errors) if all_errors else "None"
            
            all_broken = []
            for p in browser.pages_audited:
                all_broken.extend(p.broken_links)
            browser_broken_links = ", ".join(all_broken) if all_broken else "None"
            
            all_tests = []
            for p in browser.pages_audited:
                for f in p.form_submission_results:
                    all_tests.append(f"{f.form_id or 'form'}: {'success' if f.success else 'failed'} ({f.outcome})")
            browser_form_tests = "; ".join(all_tests) if all_tests else "None"
        else:
            browser_pages = "No browser crawl findings provided."
            browser_errors = "No browser crawl findings provided."
            browser_broken_links = "No browser crawl findings provided."
            browser_form_tests = "No browser crawl findings provided."

        # Format Matching Inputs
        match_implemented = ", ".join([f.name for f in matching.implemented_features]) or "None"
        match_partial = ", ".join([f.name for f in matching.partially_implemented_features]) or "None"
        match_missing = ", ".join([f.name for f in matching.missing_features]) or "None"

        prompt = REPORT_GENERATOR_PROMPT.format(
            prd_pages=prd_pages,
            prd_features=prd_features,
            prd_user_flows=prd_user_flows,
            github_tech=github_tech,
            github_frameworks=github_frameworks,
            github_components=github_components,
            github_rating=github_rating,
            github_strengths=github_strengths,
            github_weaknesses=github_weaknesses,
            browser_pages=browser_pages,
            browser_errors=browser_errors,
            browser_broken_links=browser_broken_links,
            browser_form_tests=browser_form_tests,
            match_implemented=match_implemented,
            match_partial=match_partial,
            match_missing=match_missing,
            calc_percentage=calc_percentage
        )

        logger.info("Sending report generation request to Gemini — %d chars", len(prompt))

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=REPORT_GENERATOR_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=GeminiGeneratedReportWrapper,
                    temperature=0.2,
                ),
            )

            if not response.text:
                raise GeminiError("Gemini returned an empty response.")

            logger.debug("Raw Gemini response: %s", response.text[:500])

        except Exception as e:
            if isinstance(e, GeminiError):
                raise
            raise GeminiError(f"Gemini API call failed: {str(e)}")

        # ── Parse and validate ──────────────────────────────────────────
        try:
            if hasattr(response, "parsed") and response.parsed is not None:
                return response.parsed
        except Exception as e:
            logger.warning("Failed to access response.parsed directly for report wrapper: %s. Falling back to manual JSON parsing.", str(e))

        return self._parse_report_wrapper_response(response.text)

    def _parse_report_wrapper_response(self, raw_response: str) -> GeminiGeneratedReportWrapper:
        cleaned = self._clean_json_response(raw_response)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini response as JSON: %s", str(e))
            raise GeminiError(f"Gemini returned invalid JSON for reports: {str(e)}")

        # Validate with Pydantic
        try:
            result = GeminiGeneratedReportWrapper.model_validate(data)
        except Exception as e:
            logger.error("Pydantic validation failed for report wrapper: %s", str(e))
            raise GeminiError(f"Gemini response did not match expected schema: {str(e)}")

        logger.info(
            "Report generation complete — Student completion: %.1f%%, Company completion: %.1f%%",
            result.student_report.completion_percentage,
            result.company_report.completion_percentage,
        )

        return result

    @staticmethod
    def _clean_json_response(text: str) -> str:
        """
        Strip markdown code fences and whitespace from Gemini response.

        Gemini sometimes wraps JSON in ```json ... ``` blocks.
        """
        text = text.strip()

        # Remove ```json or ``` wrapper
        if text.startswith("```"):
            # Remove opening fence
            first_newline = text.index("\n") if "\n" in text else 3
            text = text[first_newline + 1:]

            # Remove closing fence
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]

        return text.strip()

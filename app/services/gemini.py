"""
Gemini Integration Service — sends PRD text to Google Gemini
and parses the structured JSON response.

Uses the google-generativeai SDK with structured output (JSON mode).
"""

import json
import logging
from typing import Optional

from google import genai
from google.genai import types

from app.config import get_settings
from app.schemas.prd import PRDAnalysisResult
from app.schemas.github import GithubAnalysisResultSchema

logger = logging.getLogger(__name__)

# ── Prompts ──────────────────────────────────────────────────────────────────

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

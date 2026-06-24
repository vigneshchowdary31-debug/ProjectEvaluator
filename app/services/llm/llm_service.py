"""
LLM Service orchestrator with Failover logic.
"""

import logging
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

from app.config import get_settings
from app.services.llm.base_provider import BaseLLMProvider, LLMError
from app.services.llm.provider_factory import ProviderFactory

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, audit_run=None):
        """
        Initialize LLM Service.
        Optionally accepts an AuditRun SQLAlchemy model instance to record traceability.
        """
        self.settings = get_settings()
        self.audit_run = audit_run
        
        # Load configs
        self.default_provider_name = self.settings.DEFAULT_LLM_PROVIDER
        self.fallback_provider_name = self.settings.FALLBACK_LLM_PROVIDER
        self.failover_enabled = self.settings.LLM_FAILOVER_ENABLED

    def _execute_with_failover(self, method_name: str, *args, **kwargs) -> Any:
        """Executes a provider method with automatic failover."""
        # 1. Try Primary Provider
        try:
            provider = ProviderFactory.get_provider(self.default_provider_name)
            method = getattr(provider, method_name)
            result = method(*args, **kwargs)
            
            # Record Success trace
            if self.audit_run:
                self.audit_run.llm_provider_used = provider.provider_name()
                self.audit_run.llm_model_used = provider.model_name()
            
            return result
        except Exception as primary_e:
            logger.warning(
                f"[{self.default_provider_name}] Failed to execute '{method_name}': {primary_e}"
            )
            
            if not self.failover_enabled:
                logger.error("Failover is disabled. Aborting.")
                raise primary_e
                
            if not self.fallback_provider_name:
                logger.error("Failover is enabled but no FALLBACK_LLM_PROVIDER configured.")
                raise primary_e

            logger.info(f"Triggering failover to fallback provider: {self.fallback_provider_name}")

            # 2. Try Fallback Provider
            try:
                fallback_provider = ProviderFactory.get_provider(self.fallback_provider_name)
                method = getattr(fallback_provider, method_name)
                result = method(*args, **kwargs)
                
                # Record Failover trace
                if self.audit_run:
                    self.audit_run.llm_provider_used = fallback_provider.provider_name()
                    self.audit_run.llm_model_used = fallback_provider.model_name()
                    self.audit_run.llm_fallback_triggered = True
                
                return result
            except Exception as fallback_e:
                logger.error(
                    f"[{self.fallback_provider_name}] Fallback provider also failed to execute '{method_name}': {fallback_e}"
                )
                raise LLMError(
                    f"Both primary ({self.default_provider_name}) and fallback "
                    f"({self.fallback_provider_name}) providers failed."
                ) from fallback_e

    def generate_content(self, prompt: str, system_instruction: str, **kwargs) -> str:
        return self._execute_with_failover(
            "generate_content", prompt, system_instruction, **kwargs
        )

    def generate_structured_output(
        self, prompt: str, system_instruction: str, response_schema: Type[BaseModel], **kwargs
    ) -> BaseModel:
        return self._execute_with_failover(
            "generate_structured_output", prompt, system_instruction, response_schema, **kwargs
        )

    # ── Domain specific methods (moved from gemini.py) ──────────────────────

    def analyze_prd(self, document_text: str) -> "PRDAnalysisResult":
        from app.schemas.prd import PRDAnalysisResult
        from app.services.llm.prompts import PRD_ANALYSIS_PROMPT, PRD_SYSTEM_INSTRUCTION
        
        if not document_text.strip():
            raise LLMError("Document text is empty. Nothing to analyze.")

        max_chars = 500_000
        if len(document_text) > max_chars:
            logger.warning("Document text truncated from %d to %d chars", len(document_text), max_chars)
            document_text = document_text[:max_chars]

        prompt = PRD_ANALYSIS_PROMPT.format(document_text=document_text)
        logger.info("Sending PRD to LLM Service — %d chars", len(document_text))

        return self.generate_structured_output(
            prompt=prompt,
            system_instruction=PRD_SYSTEM_INSTRUCTION,
            response_schema=PRDAnalysisResult,
        )

    def analyze_github(self, repo_name: str, folder_tree: dict, manifest_contents: dict) -> "GithubAnalysisResultSchema":
        import json
        from app.schemas.github import GithubAnalysisResultSchema
        from app.services.llm.prompts import GITHUB_ANALYSIS_PROMPT, GITHUB_SYSTEM_INSTRUCTION

        folder_tree_json = json.dumps(folder_tree, indent=2)
        manifests_list = []
        for path, content in manifest_contents.items():
            manifests_list.append(f"--- File: {path} ---\\n{content}\\n")
        manifest_contents_text = "\\n".join(manifests_list) if manifests_list else "No manifest files found."

        prompt = GITHUB_ANALYSIS_PROMPT.format(
            repo_name=repo_name,
            folder_tree_json=folder_tree_json,
            manifest_contents_text=manifest_contents_text
        )

        logger.info("Sending GitHub repo info to LLM Service — %d chars", len(prompt))

        return self.generate_structured_output(
            prompt=prompt,
            system_instruction=GITHUB_SYSTEM_INSTRUCTION,
            response_schema=GithubAnalysisResultSchema,
        )

    def analyze_requirement_matching(
        self, prd: "PRDAnalysisResult", github: "GithubAnalysisResultSchema", browser: Optional["BrowserAuditResponse"]
    ) -> "RequirementMatchingResult":
        import json
        from app.schemas.requirement_matching import RequirementMatchingResult
        from app.services.llm.prompts import MATCHING_ANALYSIS_PROMPT, MATCHING_SYSTEM_INSTRUCTION

        # Format PRD Inputs
        prd_pages = ", ".join([p.name for p in prd.pages]) or "None"
        prd_features = ", ".join([f.name for f in prd.features]) or "None"
        prd_forms = ", ".join([f.name for f in prd.forms]) or "None"
        prd_user_flows = ", ".join([uf.name for uf in prd.user_flows]) or "None"

        # Format GitHub Inputs
        github_tech = ", ".join(github.technologies) or "None"
        github_components = ", ".join([c.name for c in github.components]) or "None"
        github_pages = ", ".join([p.name for p in github.pages]) or "None"
        github_tree = github.folder_structure if isinstance(github.folder_structure, str) else json.dumps(github.folder_structure, indent=2)

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
            prd_pages=prd_pages, prd_features=prd_features, prd_forms=prd_forms, prd_user_flows=prd_user_flows,
            github_tech=github_tech, github_components=github_components, github_pages=github_pages, github_tree=github_tree,
            browser_pages=browser_pages, browser_errors=browser_errors, browser_forms=browser_forms
        )

        logger.info("Sending requirements matching request to LLM Service — %d chars", len(prompt))

        return self.generate_structured_output(
            prompt=prompt,
            system_instruction=MATCHING_SYSTEM_INSTRUCTION,
            response_schema=RequirementMatchingResult,
        )

    def generate_project_reports(
        self,
        prd: "PRDAnalysisResult",
        github: "GithubAnalysisResultSchema",
        browser: Optional["BrowserAuditResponse"],
        matching: "RequirementMatchingResult",
        calc_percentage: float,
        readiness_score: float = 0.0,
        readiness_classification: str = "Prototype"
    ) -> Any:
        from app.schemas.report_generation import ProjectAuditReportSchema
        from app.services.llm.prompts import REPORT_GENERATOR_PROMPT, REPORT_GENERATOR_SYSTEM_INSTRUCTION

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
            prd_pages=prd_pages, prd_features=prd_features, prd_user_flows=prd_user_flows,
            github_tech=github_tech, github_frameworks=github_frameworks, github_components=github_components,
            github_rating=github_rating, github_strengths=github_strengths, github_weaknesses=github_weaknesses,
            browser_pages=browser_pages, browser_errors=browser_errors, browser_broken_links=browser_broken_links, browser_form_tests=browser_form_tests,
            match_implemented=match_implemented, match_partial=match_partial, match_missing=match_missing,
            calc_percentage=calc_percentage, readiness_score=readiness_score, readiness_classification=readiness_classification
        )

        logger.info("Sending report generation request to LLM Service — %d chars", len(prompt))

        return self.generate_structured_output(
            prompt=prompt,
            system_instruction=REPORT_GENERATOR_SYSTEM_INSTRUCTION,
            response_schema=ProjectAuditReportSchema,
        )

    def discover_roles(self, url: str, html_content: str) -> "RoleDiscoveryResult":
        from app.schemas.rbac import RoleDiscoveryResult
        from app.services.llm.prompts import ROLE_DISCOVERY_PROMPT, ROLE_DISCOVERY_SYSTEM_INSTRUCTION

        if len(html_content) > 100_000:
            html_content = html_content[:100_000]

        prompt = ROLE_DISCOVERY_PROMPT.format(url=url, html_content=html_content)
        logger.info("Sending role discovery request to LLM Service — %d chars", len(prompt))

        return self.generate_structured_output(
            prompt=prompt,
            system_instruction=ROLE_DISCOVERY_SYSTEM_INSTRUCTION,
            response_schema=RoleDiscoveryResult,
        )


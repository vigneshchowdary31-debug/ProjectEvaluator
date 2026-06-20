"""
Orchestrator Service — coordinates running all audit stages sequentially in background,
broadcasting progress over WebSockets, and saving findings/evidence/reports in the DB.
"""

import os
import json
import logging
import asyncio
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.audit_run import AuditRun
from app.models.evidence import Evidence
from app.models.report import Report
from app.repositories.project import ProjectRepository
from app.repositories.audit_run import AuditRunRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.report import ReportRepository

from app.schemas.audit_run import AuditRunStatusUpdate
from app.schemas.prd import PRDAnalysisRequest, PRDAnalysisResult, PRDAnalysisResponse
from app.schemas.github import GithubAnalysisRequest, GithubAnalysisResponse, GithubAnalysisResultSchema
from app.schemas.browser_audit import BrowserAuditRequest, BrowserAuditResponse
from app.schemas.requirement_matching import RequirementMatchingRequest, RequirementMatchingResult
from app.schemas.report import ReportCreate

from app.services.prd_analysis import PRDAnalysisService
from app.services.github_analysis import GithubAnalysisService
from app.services.github_parser import GithubParserService
from app.services.browser_audit import BrowserAuditService
from app.services.requirement_matching import RequirementMatchingService
from app.services.report_generation import ReportGenerationService
from app.services.google_drive import GoogleDriveService
from app.services.security_engine import AdvancedSecurityEngine
from app.services.readiness_evaluator import ProductionReadinessEvaluator

from app.utils.ws_manager import ws_manager
from app.utils.exceptions import NotFoundException

logger = logging.getLogger(__name__)


class OrchestratorService:

    def __init__(self, db: Session):
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.audit_run_repo = AuditRunRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.report_repo = ReportRepository(db)
        
        self.prd_service = PRDAnalysisService()
        self.github_service = GithubAnalysisService(db)
        self.github_parser = GithubParserService()
        self.browser_service = BrowserAuditService()
        self.matching_service = RequirementMatchingService()
        self.report_gen_service = ReportGenerationService(db)
        self.drive_service = GoogleDriveService()
        self.security_engine = AdvancedSecurityEngine()
        self.readiness_evaluator = ProductionReadinessEvaluator()

    def trigger_audit(self, project_id: str, background_tasks: BackgroundTasks, user_id: str) -> AuditRun:
        """Create a pending audit run and trigger background execution."""
        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundException(detail="Project not found")

        audit_run = AuditRun(
            project_id=project_id,
            triggered_by=user_id,
            trigger="manual",
            status="pending",
            config={}
        )
        self.audit_run_repo.create(audit_run)

        # Queue background task
        # Since the task is async, we run it in a thread or task loop
        background_tasks.add_task(self._run_audit_async_wrapper, audit_run.id, project_id, user_id)
        return audit_run

    def _run_audit_async_wrapper(self, run_id: str, project_id: str, user_id: str):
        """Sync wrapper to run async run_audit_task within FastAPI background worker."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.run_audit_task(run_id, project_id, user_id))
        finally:
            loop.close()

    async def run_audit_task(self, run_id: str, project_id: str, user_id: str) -> None:
        """Asynchronous execution task running each audit stage sequentially."""
        logger.info("Starting background audit task %s", run_id)
        
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Instantiate local repositories/services with the background db session
            project_repo = ProjectRepository(db)
            audit_run_repo = AuditRunRepository(db)
            evidence_repo = EvidenceRepository(db)
            report_repo = ReportRepository(db)
            github_service = GithubAnalysisService(db)

            # Initialize run status in DB
            run = audit_run_repo.get_by_id(run_id)
            if not run:
                logger.error("Audit run %s not found in database", run_id)
                return

            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            db.commit()

            start_time = datetime.now(timezone.utc)
            
            # WebSocket broadcast helper
            async def log_step(step: str, progress: int, msg: str, is_error: bool = False) -> None:
                payload = {
                    "audit_run_id": run_id,
                    "step": step,
                    "progress": progress,
                    "message": msg,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "is_error": is_error,
                    "elapsed_seconds": (datetime.now(timezone.utc) - start_time).total_seconds()
                }
                await ws_manager.broadcast(run_id, payload)
                logger.info("AuditRun %s [%d%%] - %s: %s", run_id, progress, step.upper(), msg)

            await log_step("starting", 5, "Initiating comprehensive project audit...")

            project = project_repo.get_by_id(project_id)
            if not project:
                await log_step("failed", 100, "Project not found.", is_error=True)
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

            # ── Setup Google Drive Hierarchical Folder ──────────────────────
            drive_folder_id = None
            screenshots_folder_id = None
            reports_folder_id = None
            
            if self.drive_service.enabled:
                try:
                    await log_step("drive", 10, "Setting up Google Drive directories...")
                    # 1. Projects Root folder
                    projects_root_id = self.drive_service.create_folder("Projects")
                    # 2. Project name folder
                    project_folder_id = self.drive_service.create_folder(project.name, parent_id=projects_root_id)
                    # 3. Audit run folder
                    timestamp_str = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                    drive_folder_id = self.drive_service.create_folder(f"Audit - {timestamp_str}", parent_id=project_folder_id)
                    
                    if drive_folder_id:
                        screenshots_folder_id = self.drive_service.create_folder("Screenshots", parent_id=drive_folder_id)
                        reports_folder_id = self.drive_service.create_folder("Reports", parent_id=drive_folder_id)
                except Exception as e:
                    logger.error("Failed to setup Drive directories: %s", str(e))
                    await log_step("drive", 10, f"Drive directories failed: {str(e)}. Falling back to local storage.")

            prd_result = None
            github_result = None
            browser_result = None
            matching_result = None
            
            # ── Step 1: PRD Requirements Analysis ───────────────────────────
            if project.prd_url:
                await log_step("prd", 15, "Downloading and parsing PRD Google Doc...")
                try:
                    prd_response = self.prd_service.analyze(PRDAnalysisRequest(google_doc_url=project.prd_url, project_id=project_id))
                    prd_result = prd_response.analysis
                    await log_step("prd", 30, f"PRD parsed successfully. Found {len(prd_result.features)} expected features.")
                except Exception as e:
                    await log_step("prd", 30, f"PRD analysis failed: {str(e)}. Proceeding without spec requirements.", is_error=True)
            else:
                await log_step("prd", 30, "No PRD Google Doc link configured. Skipping specs extraction.")

            # Default empty PRD findings if skipped or failed
            if not prd_result:
                prd_result = PRDAnalysisResult(pages=[], features=[], forms=[], user_flows=[])

            # ── Step 2: GitHub Static Codebase Analysis ──────────────────────
            file_paths: List[str] = []
            manifest_contents: Dict[str, str] = {}
            github_rating = "fair"
            
            if project.repository_url:
                await log_step("github", 35, "Fetching repository structure and manifest files from GitHub...")
                try:
                    # Retrieve files tree and manifest contents
                    owner, repo_name = self.github_parser.parse_repo_url(project.repository_url)
                    metadata = self.github_parser.fetch_repo_metadata(owner, repo_name)
                    default_branch = metadata.get("default_branch", "main")
                    commit_sha = self.github_parser.fetch_latest_commit(owner, repo_name, default_branch)
                    tree_nodes = self.github_parser.fetch_git_tree(owner, repo_name, commit_sha or default_branch)
                    
                    for node in tree_nodes:
                        path = node.get("path", "")
                        type_ = node.get("type", "")
                        if path and type_ == "blob":
                            file_paths.append(path)
                            filename = path.split("/")[-1]
                            if filename in self.github_parser.MANIFEST_FILENAMES:
                                if len(path.split("/")) <= 3:
                                    content = self.github_parser.fetch_raw_file(owner, repo_name, commit_sha or default_branch, path)
                                    if content:
                                        manifest_contents[path] = content[:20000]

                    # Run Gemini code analyzer
                    github_response = github_service.analyze(GithubAnalysisRequest(repo_url=project.repository_url, force_refresh=True))
                    github_result = github_response.analysis
                    github_rating = github_result.architecture_quality.rating
                    
                    await log_step("github", 50, f"GitHub codebase analyzed. Rating: {github_rating.upper()}.")
                except Exception as e:
                    await log_step("github", 50, f"GitHub analysis failed: {str(e)}.", is_error=True)
                    run.status = "failed"
                    run.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    return
            else:
                await log_step("github", 50, "No GitHub repository URL configured. Audit cannot proceed.", is_error=True)
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

            # ── Step 3: Headless Playwright crawling & mobile testing ───────
            if project.deployment_url:
                await log_step("browser", 55, "Launching headless Playwright crawler on deployment URL...")
                try:
                    # We need to temporarily mock/override drive service folder ID inside browser service
                    old_enabled = self.browser_service.drive_service.enabled
                    if screenshots_folder_id:
                        self.browser_service.drive_service.enabled = True
                        self.browser_service.drive_service.parent_folder_id = screenshots_folder_id
                    else:
                        self.browser_service.drive_service.enabled = False

                    browser_result = await self.browser_service.audit(BrowserAuditRequest(url=project.deployment_url, max_pages=5, test_forms=True))
                    
                    # Restore drive configuration
                    self.browser_service.drive_service.enabled = old_enabled

                    await log_step("browser", 70, f"Crawler execution complete. Visited {len(browser_result.pages_audited)} link viewports.")
                except Exception as e:
                    await log_step("browser", 70, f"Crawler failed: {str(e)}.", is_error=True)
            else:
                await log_step("browser", 70, "No Deployment URL configured. Skipping web crawl testing.")

            # ── Step 4: Advanced Security Scan ──────────────────────────────
            await log_step("security", 75, "Running static security engine and vulnerability checks...")
            security_findings = []
            try:
                security_findings = self.security_engine.scan(file_paths, manifest_contents)
                
                # Save findings in Reports table and create Evidences
                for f in security_findings:
                    # Save finding as DB Report
                    db_report = Report(
                        title=f.title,
                        summary=f.description,
                        findings=f.to_dict(),
                        severity=f.severity,
                        project_id=project_id,
                        audit_run_id=run_id
                    )
                    report_repo.create(db_report)

                    # Save corresponding Code Evidence
                    evidence_rec = Evidence(
                        project_id=project_id,
                        audit_run_id=run_id,
                        file_path=f.file_path,
                        line_range=f.line_range,
                        evidence_type="Code",
                        confidence_score=1.0,
                        details=json.dumps(f.to_dict())
                    )
                    evidence_repo.create(evidence_rec)

                await log_step("security", 80, f"Security engine scanned manifests. Logged {len(security_findings)} vulnerabilities.")
            except Exception as e:
                await log_step("security", 80, f"Security checks failed: {str(e)}.", is_error=True)

            # ── Step 5: Production Readiness Score ──────────────────────────
            await log_step("readiness", 85, "Evaluating production readiness and health indices...")
            readiness_report = {
                "overall_readiness_percentage": 50.0,
                "classification": "Prototype",
                "categories": {}
            }
            try:
                readiness_report = self.readiness_evaluator.evaluate(
                    file_paths, manifest_contents, len(security_findings), github_rating
                )
                await log_step("readiness", 88, f"Maturity rating: {readiness_report['overall_readiness_percentage']}% ({readiness_report['classification']}).")
            except Exception as e:
                await log_step("readiness", 88, f"Readiness scoring failed: {str(e)}.", is_error=True)

            # ── Step 6: Requirement Matching (Gap Analysis) ─────────────────
            await log_step("matching", 90, "Comparing PRD specs against implementation details...")
            try:
                matching_result = self.matching_service.match(RequirementMatchingRequest(
                    prd_findings=prd_result,
                    github_findings=github_result,
                    browser_findings=browser_result
                ))
                await log_step("matching", 93, f"Gap analysis complete. Confidence: {matching_result.confidence_score:.2f}.")
            except Exception as e:
                await log_step("matching", 93, f"Gap analysis failed: {str(e)}.", is_error=True)

            # Default empty matching if failed
            if not matching_result:
                matching_result = RequirementMatchingResult(
                    implemented_features=[], partially_implemented_features=[], missing_features=[],
                    confidence_score=0.5, summary="Error running gap analysis matching"
                )

            # ── Save Evidences (Code/Screenshots/Logs) ──────────────────────
            # Code evidence from matched features
            for f in matching_result.implemented_features:
                files_str = ", ".join(f.matched_files) if f.matched_files else ""
                evidence_rec = Evidence(
                    project_id=project_id,
                    audit_run_id=run_id,
                    file_path=files_str[:512],
                    evidence_type="Requirement",
                    confidence_score=matching_result.confidence_score,
                    details=json.dumps({"feature_name": f.name, "description": f.description, "evidence": f.evidence})
                )
                evidence_repo.create(evidence_rec)

            # Screenshots evidence
            if browser_result:
                for p in browser_result.pages_audited:
                    if p.desktop_screenshot_url:
                        evidence_rec = Evidence(
                            project_id=project_id,
                            audit_run_id=run_id,
                            evidence_type="Screenshot",
                            screenshot_url=p.desktop_screenshot_url,
                            details=json.dumps({"url": p.url, "viewport": "desktop"})
                        )
                        evidence_repo.create(evidence_rec)
                    if p.mobile_screenshot_url:
                        evidence_rec = Evidence(
                            project_id=project_id,
                            audit_run_id=run_id,
                            evidence_type="Screenshot",
                            screenshot_url=p.mobile_screenshot_url,
                            details=json.dumps({"url": p.url, "viewport": "mobile"})
                        )
                        evidence_repo.create(evidence_rec)
                    
                    # Console error logs evidence
                    if p.console_errors:
                        evidence_rec = Evidence(
                            project_id=project_id,
                            audit_run_id=run_id,
                            evidence_type="Console",
                            details=json.dumps({"url": p.url, "errors": p.console_errors})
                        )
                        evidence_repo.create(evidence_rec)

            # ── Step 7: Audience-Tailored Report Generation & Upload ────────
            await log_step("reports", 95, "Synthesizing Student and Company audit reports...")
            try:
                # Pre-calculate base completion percentage
                implemented = matching_result.implemented_features
                partial = matching_result.partially_implemented_features
                missing = matching_result.missing_features
                total_features = len(implemented) + len(partial) + len(missing)
                calc_percentage = 0.0
                if total_features > 0:
                    calc_percentage = ((len(implemented) + 0.5 * len(partial)) / total_features) * 100.0

                # Generate reports using updated Gemini API call containing readiness ratings
                gemini_wrapper = github_service.gemini.generate_project_reports(
                    prd=prd_result,
                    github=github_result,
                    browser=browser_result,
                    matching=matching_result,
                    calc_percentage=calc_percentage,
                    readiness_score=readiness_report["overall_readiness_percentage"],
                    readiness_classification=readiness_report["classification"]
                )
                
                # Manually inject readiness scores into Pydantic structures for database dump compatibility
                gemini_wrapper.student_report.production_readiness_score = readiness_report["overall_readiness_percentage"]
                gemini_wrapper.student_report.production_readiness_classification = readiness_report["classification"]
                gemini_wrapper.company_report.production_readiness_score = readiness_report["overall_readiness_percentage"]
                gemini_wrapper.company_report.production_readiness_classification = readiness_report["classification"]

                # Save the synthesized report to DB
                from app.models.generated_report import GeneratedReport
                db_report = GeneratedReport(
                    project_id=project_id,
                    completion_percentage=calc_percentage,
                    student_report=gemini_wrapper.student_report.model_dump(),
                    company_report=gemini_wrapper.company_report.model_dump()
                )
                db.add(db_report)
                db.commit()

                # Upload generated report to Google Drive Reports directory
                if reports_folder_id:
                    try:
                        # Write to temporary file
                        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as temp_file:
                            json.dump(gemini_wrapper.company_report.model_dump(), temp_file, indent=2)
                            temp_path = temp_file.name
                        
                        drive_report_url = self.drive_service.upload_file(
                            temp_path, 
                            f"Company_Report_Run_{run_id}.json", 
                            "application/json", 
                            reports_folder_id
                        )
                        os.unlink(temp_path)
                        
                        # Update report run reference with Drive folder URL if wanted
                        logger.info("Uploaded generated report to Google Drive: %s", drive_report_url)
                    except Exception as ex:
                        logger.warning("Failed to upload report to Drive: %s", str(ex))

                await log_step("reports", 98, "Synthesized reports and saved successfully.")
            except Exception as e:
                await log_step("reports", 98, f"Report synthesis failed: {str(e)}.", is_error=True)

            # ── Step 8: Complete Audit Run ──────────────────────────────────
            await log_step("complete", 100, "Audit run completed successfully!")
            
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.result_summary = f"Audit complete. Completion percentage: {calc_percentage:.1f}%. Maturity: {readiness_report['classification']}."
            db.commit()

        except Exception as e:
            logger.error("Audit run %s encountered unhandled error: %s", run_id, str(e))
            try:
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                pass
        finally:
            db.close()

"""
Sheet Writeback Service — updates Google Sheets with audit metrics, scores,
report links, and statuses upon audit run completion/failure.
"""

import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.sheet_connection import SheetConnection
from app.models.audit_run import AuditRun
from app.models.generated_report import GeneratedReport
from app.models.report import Report
from app.services.google_sheets import GoogleSheetsService
from app.config import get_settings

logger = logging.getLogger(__name__)


class SheetWritebackService:
    """Service to automatically update source Google Sheet rows with audit outcomes."""

    def __init__(self, db: Session):
        self.db = db
        self.sheets_service = GoogleSheetsService()
        self.settings = get_settings()

    def writeback(self, project_id: str) -> None:
        """Reads latest audit results and writes them back to the project's row in the Google Sheet."""
        if not self.settings.SHEET_WRITEBACK_ENABLED:
            logger.info("Sheet writeback is disabled in configuration.")
            return

        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.sheet_connection_id or not project.sheet_row_number:
            logger.info("Project %s is not linked to any Google Sheet row.", project_id)
            return

        sheet_conn = self.db.query(SheetConnection).filter(SheetConnection.id == project.sheet_connection_id).first()
        if not sheet_conn:
            logger.warning("Sheet connection %s not found for project %s", project.sheet_connection_id, project_id)
            return

        # Fetch latest audit run
        latest_run = self.db.query(AuditRun).filter(
            AuditRun.project_id == project_id
        ).order_by(AuditRun.created_at.desc()).first()

        if not latest_run:
            logger.info("No audit runs found to write back for project %s", project_id)
            return

        # Fetch latest generated report
        latest_report = self.db.query(GeneratedReport).filter(
            GeneratedReport.project_id == project_id
        ).order_by(GeneratedReport.created_at.desc()).first()

        status = latest_run.status.upper()
        completion = 0.0
        readiness = 0.0
        security = 100.0
        risk_level = "Unknown"
        failure_reason = latest_run.result_summary if status == "FAILED" else ""

        if status == "COMPLETED":
            if latest_report:
                completion = latest_report.completion_percentage
                readiness = latest_report.student_report.get("production_readiness_score", 0.0)

            # Security score calculation
            reports = self.db.query(Report).filter(Report.audit_run_id == latest_run.id).all()
            for r in reports:
                sev = r.severity.lower()
                if sev == "critical":
                    security -= 25.0
                elif sev == "high":
                    security -= 15.0
                elif sev == "medium":
                    security -= 10.0
                elif sev == "low":
                    security -= 5.0
            security = max(0.0, security)

            # Health score
            health_score = (completion * 0.5) + (readiness * 0.5) - (len(reports) * 5)
            health_score = max(0.0, min(100.0, health_score))
            if health_score >= 80:
                risk_level = "Low"
            elif health_score >= 50:
                risk_level = "Medium"
            else:
                risk_level = "High"

        # URLs in the dashboard
        student_url = f"http://localhost:3001/#/projects/{project_id}"
        company_url = f"http://localhost:3001/#/projects/{project_id}"

        update_dict = {
            "Audit Status": status,
            "Completion %": completion,
            "Security Score": security,
            "Readiness Score": readiness,
            "Last Audit Date": (latest_run.completed_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S"),
            "Audit Run ID": latest_run.id,
            "Risk Level": risk_level,
            "Student Report URL": student_url,
            "Company Report URL": company_url,
            "Failure Reason": failure_reason or ""
        }

        try:
            sheet_id = self.sheets_service.extract_sheet_id(sheet_conn.sheet_url)
            # Read current headers to map columns
            _, headers = self.sheets_service.read_all_rows(sheet_id)
            self.sheets_service.write_row_data(
                sheet_id=sheet_id,
                sheet_name=None,
                row_number=project.sheet_row_number,
                headers=headers,
                update_dict=update_dict
            )
            logger.info("Successfully completed sheet writeback for project %s to row %d", project_id, project.sheet_row_number)
        except Exception as e:
            logger.error("Failed to write back results to Google Sheets for project %s: %s", project_id, str(e))

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
from app.models.project_report import ProjectReport
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
        latest_report = self.db.query(ProjectReport).filter(
            ProjectReport.project_id == project_id
        ).order_by(ProjectReport.generated_at.desc()).first()

        status = latest_run.status.upper()
        completion = 0.0
        readiness = 0.0
        security = 100.0
        risk_level = "Unknown"
        failure_reason = latest_run.result_summary if status == "FAILED" else ""

        if status == "COMPLETED" and latest_report:
            completion = latest_report.completion_score
            readiness = latest_report.report_data.get("production_readiness_score", 0.0)
            security = latest_report.security_score

            # Health score
            health_score = latest_report.overall_score
            if health_score >= 80:
                risk_level = "Low"
            elif health_score >= 50:
                risk_level = "Medium"
            else:
                risk_level = "High"

        # Ensure we never write localhost URLs to Google Sheets
        report_url = "UPLOAD_FAILED"
        pdf_url = "UPLOAD_FAILED"
        json_url = "UPLOAD_FAILED"

        if latest_report:
            if getattr(latest_report, "report_url", None):
                report_url = latest_report.report_url
            if getattr(latest_report, "pdf_url", None):
                pdf_url = latest_report.pdf_url
            if getattr(latest_report, "json_url", None):
                json_url = latest_report.json_url
        else:
            report_url = "NO_REPORT"
            pdf_url = "NO_REPORT"
            json_url = "NO_REPORT"

        update_dict = {
            "Audit Status": status,
            "Completion %": completion,
            "Security Score": security,
            "Readiness Score": readiness,
            "Last Audit Date": (latest_run.completed_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S"),
            "Audit Run ID": latest_run.id,
            "Risk Level": risk_level,
            "Project Report URL": report_url,
            "PDF Report URL": pdf_url,
            "JSON Report URL": json_url,
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

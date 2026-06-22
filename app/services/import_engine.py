"""
Import Engine Service — reads rows from Google Sheets, maps columns to Projects,
handles deduplication, encryption of credentials, and logs sync histories.
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.sheet_connection import SheetConnection
from app.models.import_job import ImportJob
from app.models.project import Project
from app.models.project_approval import ProjectApproval
from app.models.project_sync_history import ProjectSyncHistory
from app.services.google_sheets import GoogleSheetsService
from app.services.secret_manager import SecretManagerService
from app.services.notification_service import NotificationService
from app.utils.exceptions import NotFoundException

logger = logging.getLogger(__name__)


class ImportEngine:
    """Core engine to synchronize project inventories from Google Sheets."""

    def __init__(self, db: Session):
        self.db = db
        self.sheets_service = GoogleSheetsService()
        self.secret_manager = SecretManagerService()
        self.notification_service = NotificationService(db)

    @staticmethod
    def _get_val(row: Dict[str, Any], headers: List[str], default: Any = None) -> Any:
        """Helper to get a column value from a row using list of potential matching headers."""
        # Clean keys for robust matching (case-insensitive and stripped)
        row_clean = {k.strip().lower(): v for k, v in row.items()}
        for header in headers:
            header_clean = header.strip().lower()
            if header_clean in row_clean:
                val = row_clean[header_clean]
                return val if val not in (None, "") else default
        return default

    def run_import(self, sheet_connection_id: str, triggered_by_user_id: str) -> ImportJob:
        """Connect to the sheet, read all rows, and create/update projects."""
        sheet_conn = self.db.query(SheetConnection).filter(SheetConnection.id == sheet_connection_id).first()
        if not sheet_conn:
            raise NotFoundException(detail="Sheet connection not found")

        # Create running import job
        job = ImportJob(
            sheet_connection_id=sheet_connection_id,
            status="running",
            triggered_by=triggered_by_user_id,
            total_rows=0,
            imported_count=0,
            updated_count=0,
            skipped_count=0,
            error_count=0,
            errors=[]
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        errors_log = []
        try:
            sheet_id = self.sheets_service.extract_sheet_id(sheet_conn.sheet_url)
            if not sheet_id:
                raise Exception("Invalid Google Sheet URL format")

            # Test/connect
            success, sheet_title = self.sheets_service.test_connection(sheet_id)
            if not success:
                raise Exception(f"Failed to connect to Google Sheets: {sheet_title}")

            # Update sheet title if it was changed
            sheet_conn.sheet_name = sheet_title
            self.db.commit()

            # Read all rows
            data_rows, headers = self.sheets_service.read_all_rows(sheet_id)
            job.total_rows = len(data_rows)
            sheet_conn.row_count = len(data_rows)
            self.db.commit()

            # Process each row
            for row in data_rows:
                row_num = row.get("_row_number", 0)
                try:
                    name = self._get_val(row, ["Project Name", "Name", "Title"])
                    if not name:
                        raise ValueError("Project Name is a required field and was missing.")

                    description = self._get_val(row, ["Description", "Project Description"])
                    repository_url = self._get_val(row, ["Repository URL", "Repo URL", "GitHub URL", "GitHub Repository"])
                    prd_url = self._get_val(row, ["PRD URL", "PRD Link", "PRD"])
                    deployment_url = self._get_val(row, ["Deployment URL", "URL", "App URL"])
                    
                    rbac_enabled_raw = self._get_val(row, ["RBAC Enabled", "RBAC"], "False")
                    rbac_enabled = str(rbac_enabled_raw).lower() in ("true", "yes", "1", "y", "enabled")
                    
                    admin_url = self._get_val(row, ["Admin URL"])
                    user_url = self._get_val(row, ["User URL"])
                    
                    auth_required_raw = self._get_val(row, ["Auth Required", "Authentication Required", "Auth"], "False")
                    auth_required = str(auth_required_raw).lower() in ("true", "yes", "1", "y", "required")
                    
                    login_url = self._get_val(row, ["Login URL"])
                    student_name = self._get_val(row, ["Student Name", "Student", "Owner Name"])
                    company_name = self._get_val(row, ["Company Name", "Company", "Organization"])

                    # Credentials
                    admin_email = self._get_val(row, ["Admin Email", "Admin Username", "Admin User"])
                    admin_password = self._get_val(row, ["Admin Password"])
                    user_email = self._get_val(row, ["Test User Email", "Test User Username", "User Email", "User Username"])
                    user_password = self._get_val(row, ["Test User Password", "User Password"])
                    auth_email = self._get_val(row, ["Auth Email", "Auth Username"])
                    auth_password = self._get_val(row, ["Auth Password"])

                    # Check if project already exists under the connection owner
                    project = None
                    if repository_url:
                        project = self.db.query(Project).filter(
                            Project.owner_id == sheet_conn.created_by,
                            Project.repository_url == repository_url
                        ).first()
                    
                    if not project:
                        project = self.db.query(Project).filter(
                            Project.owner_id == sheet_conn.created_by,
                            Project.name == name
                        ).first()

                    fields_to_check = {
                        "name": name,
                        "description": description,
                        "repository_url": repository_url,
                        "prd_url": prd_url,
                        "deployment_url": deployment_url,
                        "rbac_enabled": rbac_enabled,
                        "admin_url": admin_url,
                        "user_url": user_url,
                        "auth_required": auth_required,
                        "login_url": login_url,
                        "student_name": student_name,
                        "company_name": company_name,
                        "sheet_row_number": row_num,
                        "sheet_connection_id": sheet_connection_id,
                    }

                    if project:
                        # Existing project - Update logic
                        changes = {}
                        for field, new_val in fields_to_check.items():
                            old_val = getattr(project, field)
                            if old_val != new_val:
                                changes[field] = {"old": old_val, "new": new_val}

                        # Check credentials changes
                        existing_admin = {}
                        existing_user = {}
                        existing_auth = {}
                        if project.secret_reference:
                            try:
                                old_creds = self.secret_manager.retrieve_credentials(project.secret_reference)
                                if old_creds:
                                    existing_admin = old_creds.get("admin", {})
                                    existing_user = old_creds.get("user", {})
                                    existing_auth = old_creds.get("auth", {})
                            except Exception:
                                pass

                        admin_email_final = admin_email if admin_email not in (None, "") else existing_admin.get("email", "")
                        admin_password_final = admin_password if admin_password not in (None, "") else existing_admin.get("password", "")
                        user_email_final = user_email if user_email not in (None, "") else existing_user.get("email", "")
                        user_password_final = user_password if user_password not in (None, "") else existing_user.get("password", "")
                        auth_email_final = auth_email if auth_email not in (None, "") else existing_auth.get("email", "")
                        auth_password_final = auth_password if auth_password not in (None, "") else existing_auth.get("password", "")

                        creds_changed = (
                            admin_email_final != existing_admin.get("email") or
                            admin_password_final != existing_admin.get("password") or
                            user_email_final != existing_user.get("email") or
                            user_password_final != existing_user.get("password") or
                            auth_email_final != existing_auth.get("email") or
                            auth_password_final != existing_auth.get("password")
                        )

                        if creds_changed:
                            changes["credentials"] = {"old": "***", "new": "***"}

                        if changes:
                            # Update properties
                            for field, new_val in fields_to_check.items():
                                setattr(project, field, new_val)

                            # Save merged credentials
                            if any([admin_email_final, admin_password_final, user_email_final, user_password_final, auth_email_final, auth_password_final]):
                                if project.secret_reference:
                                    try:
                                        self.secret_manager.delete_credentials(project.secret_reference)
                                    except Exception:
                                        pass
                                secret_ref = self.secret_manager.save_credentials(
                                    project.id,
                                    {"email": admin_email_final, "password": admin_password_final},
                                    {"email": user_email_final, "password": user_password_final},
                                    auth_creds={"email": auth_email_final, "password": auth_password_final}
                                )
                                project.secret_reference = secret_ref

                            # Reset approval if repository_url, prd_url, rbac_enabled, or auth_required changed
                            reset_triggers = ["repository_url", "prd_url", "rbac_enabled", "auth_required"]
                            if any(trigger in changes for trigger in reset_triggers):
                                if project.approval:
                                    project.approval.status = "pending"
                                    project.approval.reviewed_by = None
                                    project.approval.reviewed_at = None
                                    project.approval.notes = "Reset to pending because configuration changed via sync."

                            project.updated_at = datetime.now(timezone.utc)
                            self.db.commit()

                            # Sync history
                            sync_hist = ProjectSyncHistory(
                                project_id=project.id,
                                import_job_id=job.id,
                                action="updated",
                                changes=changes,
                                sheet_row_number=row_num
                            )
                            self.db.add(sync_hist)
                            job.updated_count += 1
                        else:
                            # Unchanged
                            sync_hist = ProjectSyncHistory(
                                project_id=project.id,
                                import_job_id=job.id,
                                action="unchanged",
                                changes=None,
                                sheet_row_number=row_num
                            )
                            self.db.add(sync_hist)
                            job.skipped_count += 1

                        self.db.commit()

                    else:
                        # New Project - Create flow
                        project = Project(
                            name=name,
                            description=description,
                            repository_url=repository_url,
                            prd_url=prd_url,
                            deployment_url=deployment_url,
                            rbac_enabled=rbac_enabled,
                            admin_url=admin_url,
                            user_url=user_url,
                            auth_required=auth_required,
                            login_url=login_url,
                            student_name=student_name,
                            company_name=company_name,
                            source="sheet_import",
                            sheet_row_number=row_num,
                            sheet_connection_id=sheet_connection_id,
                            owner_id=sheet_conn.created_by
                        )
                        self.db.add(project)
                        self.db.commit()
                        self.db.refresh(project)

                        # Create pending approval
                        approval = ProjectApproval(
                            project_id=project.id,
                            status="pending"
                        )
                        self.db.add(approval)

                        # Save credentials if any
                        admin_creds = {"email": admin_email or "", "password": admin_password or ""}
                        user_creds = {"email": user_email or "", "password": user_password or ""}
                        auth_creds = {"email": auth_email or "", "password": auth_password or ""}
                        if any([admin_email, admin_password, user_email, user_password, auth_email, auth_password]):
                            secret_ref = self.secret_manager.save_credentials(
                                project.id, admin_creds, user_creds, auth_creds=auth_creds
                            )
                            project.secret_reference = secret_ref

                        # Sync history
                        sync_hist = ProjectSyncHistory(
                            project_id=project.id,
                            import_job_id=job.id,
                            action="created",
                            changes=None,
                            sheet_row_number=row_num
                        )
                        self.db.add(sync_hist)
                        self.db.commit()

                        job.imported_count += 1

                except Exception as row_error:
                    logger.warning("Error processing row %d: %s", row_num, str(row_error))
                    errors_log.append({
                        "row": row_num,
                        "error": str(row_error)
                    })
                    job.error_count += 1
                    self.db.commit()

            # Finish job
            job.status = "completed"
            job.errors = errors_log
            job.completed_at = datetime.now(timezone.utc)
            
            # Update sheet connection sync status
            sheet_conn.last_sync_at = datetime.now(timezone.utc)
            sheet_conn.last_sync_status = "success"
            sheet_conn.last_sync_error = None
            self.db.commit()

            # Create in-app notification
            self.notification_service.notify(
                user_id=triggered_by_user_id,
                notification_type="import_complete",
                title="Google Sheet Sync Completed",
                message=f"Synced successfully from '{sheet_conn.sheet_name}'. Imported: {job.imported_count}, Updated: {job.updated_count}, Skipped: {job.skipped_count}, Errors: {job.error_count}.",
                metadata={"sheet_connection_id": sheet_connection_id, "import_job_id": job.id}
            )

        except Exception as e:
            logger.error("Import job failed: %s", str(e))
            job.status = "failed"
            job.errors = [{"global_error": str(e)}] + errors_log
            job.completed_at = datetime.now(timezone.utc)

            sheet_conn.last_sync_at = datetime.now(timezone.utc)
            sheet_conn.last_sync_status = "failed"
            sheet_conn.last_sync_error = str(e)
            self.db.commit()

            # Create error notification
            self.notification_service.notify(
                user_id=triggered_by_user_id,
                notification_type="import_complete",
                title="Google Sheet Sync Failed",
                message=f"Sync failed for '{sheet_conn.sheet_name}'. Error: {str(e)}",
                metadata={"sheet_connection_id": sheet_connection_id, "import_job_id": job.id}
            )

        return job

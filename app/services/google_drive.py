"""
Google Drive Service — authenticates using a Service Account
and uploads screenshots to Google Drive.
"""

import os
import logging
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import get_settings

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """Service to handle folder creation and file uploads to Google Drive."""

    def __init__(self):
        settings = get_settings()
        self.creds_path = settings.GOOGLE_CREDENTIALS_JSON
        self.parent_folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
        self.service = None
        self.enabled = False

        if self.creds_path:
            # Check if file exists (relative or absolute)
            if os.path.exists(self.creds_path):
                try:
                    scopes = [
                        "https://www.googleapis.com/auth/drive.file",
                        "https://www.googleapis.com/auth/drive",
                    ]
                    self.creds = service_account.Credentials.from_service_account_file(
                        self.creds_path, scopes=scopes
                    )
                    self.service = build("drive", "v3", credentials=self.creds)
                    self.enabled = True
                    logger.info("Google Drive API initialized successfully with service account.")
                except Exception as e:
                    logger.error("Failed to initialize Google Drive client: %s", str(e))
            else:
                logger.warning(
                    "Google Drive credentials file not found at: %s. "
                    "Screenshots will be saved locally on disk.",
                    self.creds_path
                )
        else:
            logger.info("Google Drive service disabled (no GITHUB_CREDENTIALS_JSON path configured).")

    def create_folder(self, name: str) -> Optional[str]:
        """
        Create a new folder in Google Drive.
        
        Returns:
            The folder ID string if successful, else None.
        """
        if not self.enabled or not self.service:
            return None

        try:
            file_metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder"
            }
            # Attach parent folder if defined
            if self.parent_folder_id:
                file_metadata["parents"] = [self.parent_folder_id]

            folder = self.service.files().create(
                body=file_metadata, 
                fields="id"
            ).execute()
            folder_id = folder.get("id")
            
            # Make the folder public so anyone with the link can view screenshots
            try:
                permission = {
                    "role": "reader",
                    "type": "anyone"
                }
                self.service.permissions().create(
                    fileId=folder_id,
                    body=permission
                ).execute()
                logger.debug("Google Drive folder '%s' set to public-reader viewable.", name)
            except Exception as pe:
                logger.warning("Could not set folder permissions: %s", str(pe))

            return folder_id
        except Exception as e:
            logger.error("Failed to create Google Drive folder '%s': %s", name, str(e))
            return None

    def upload_screenshot(self, file_path: str, file_name: str, folder_id: Optional[str] = None) -> Optional[str]:
        """
        Upload a local screenshot PNG file to Google Drive.

        Returns:
            webViewLink string if successful, else None.
        """
        if not self.enabled or not self.service:
            return None

        if not os.path.exists(file_path):
            logger.error("Cannot upload: file does not exist at %s", file_path)
            return None

        try:
            file_metadata = {
                "name": file_name
            }
            if folder_id:
                file_metadata["parents"] = [folder_id]

            media = MediaFileUpload(file_path, mimetype="image/png", resumable=True)
            uploaded_file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, webViewLink"
            ).execute()

            logger.info("Successfully uploaded '%s' to Google Drive.", file_name)
            return uploaded_file.get("webViewLink")
        except Exception as e:
            logger.error("Failed to upload file '%s' to Google Drive: %s", file_name, str(e))
            return None

    def get_folder_link(self, folder_id: str) -> str:
        """Get the web view URL of a Google Drive folder."""
        return f"https://drive.google.com/drive/folders/{folder_id}"

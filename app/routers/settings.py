"""
Settings router — checks the status of system integrations and keys.
"""

import os
from fastapi import APIRouter, Depends

from app.config import get_settings
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


@router.get("/status")
def get_settings_status(
    _: User = Depends(get_current_user),
):
    """
    Check configuration statuses of Gemini, GitHub, and Google Drive.
    """
    settings = get_settings()
    
    # Google Drive status
    gdrive_configured = False
    gdrive_error = None
    if settings.GOOGLE_CREDENTIALS_JSON:
        if os.path.exists(settings.GOOGLE_CREDENTIALS_JSON):
            gdrive_configured = True
        else:
            gdrive_error = f"Credentials file not found at: {settings.GOOGLE_CREDENTIALS_JSON}"
    else:
        gdrive_error = "GOOGLE_CREDENTIALS_JSON is empty"

    return {
        "gemini": {
            "configured": bool(settings.GEMINI_API_KEY),
            "model": settings.GEMINI_MODEL,
        },
        "github": {
            "configured": bool(settings.GITHUB_TOKEN),
        },
        "google_drive": {
            "configured": gdrive_configured,
            "folder_id": settings.GOOGLE_DRIVE_FOLDER_ID or "Not configured",
            "error": gdrive_error,
        },
        "app": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "debug": settings.DEBUG,
        }
    }

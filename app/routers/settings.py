"""
Settings router — checks the status of system integrations and keys.
"""

import os
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
import dotenv

from app.config import get_settings
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])

class LLMConfigUpdate(BaseModel):
    default_provider: str
    fallback_provider: str
    gemini_model: str
    openai_model: str
    failover_enabled: bool

@router.put("/llm/config")
def update_llm_config(
    payload: LLMConfigUpdate,
    _: User = Depends(get_current_user),
):
    """
    Update LLM provider and model configurations dynamically in .env
    """
    settings = get_settings()
    env_file = ".env"
    if not os.path.exists(env_file):
        raise HTTPException(status_code=500, detail=".env file not found")

    # Update the .env file
    dotenv.set_key(env_file, "DEFAULT_LLM_PROVIDER", payload.default_provider)
    dotenv.set_key(env_file, "FALLBACK_LLM_PROVIDER", payload.fallback_provider)
    dotenv.set_key(env_file, "GEMINI_MODEL", payload.gemini_model)
    dotenv.set_key(env_file, "OPENAI_MODEL", payload.openai_model)
    dotenv.set_key(env_file, "LLM_FAILOVER_ENABLED", str(payload.failover_enabled).lower())

    # Update the in-memory settings singleton
    settings.DEFAULT_LLM_PROVIDER = payload.default_provider
    settings.FALLBACK_LLM_PROVIDER = payload.fallback_provider
    settings.GEMINI_MODEL = payload.gemini_model
    settings.OPENAI_MODEL = payload.openai_model
    settings.LLM_FAILOVER_ENABLED = payload.failover_enabled

    return {"message": "LLM configuration updated successfully"}

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
        "openai": {
            "configured": bool(settings.OPENAI_API_KEY),
            "model": settings.OPENAI_MODEL,
        },
        "llm_config": {
            "default_provider": settings.DEFAULT_LLM_PROVIDER,
            "fallback_provider": settings.FALLBACK_LLM_PROVIDER,
            "failover_enabled": settings.LLM_FAILOVER_ENABLED,
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


@router.get("/llm/health")
def get_llm_health(
    _: User = Depends(get_current_user),
):
    """
    Check the health and latency of all configured LLM providers.
    """
    from app.services.llm.provider_factory import ProviderFactory, PROVIDERS
    
    health_results = []
    for provider_name in PROVIDERS.keys():
        try:
            provider = ProviderFactory.get_provider(provider_name)
            health = provider.health_check()
            health_results.append(health)
        except Exception as e:
            health_results.append({
                "provider": provider_name,
                "status": "unhealthy",
                "latency_ms": None,
                "error": str(e)
            })
            
    return {"providers": health_results}

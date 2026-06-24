"""
Gemini Provider implementation.
"""

import json
import logging
import time
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

from google import genai
from google.genai import types

from app.config import get_settings
from app.services.llm.base_provider import BaseLLMProvider, LLMError

logger = logging.getLogger(__name__)


class GeminiError(LLMError):
    """Raised when Gemini API interaction fails."""
    pass


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.GEMINI_API_KEY
        self._model_name = settings.GEMINI_MODEL

        if not self.api_key:
            raise GeminiError("GEMINI_API_KEY is not configured.")

        self.client = genai.Client(api_key=self.api_key)

    def provider_name(self) -> str:
        return "gemini"

    def model_name(self) -> str:
        return self._model_name

    def _generate_content_with_retry(self, **kwargs):
        """Invoke generate_content with tenacity retry logic for reliability."""
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1.5, min=2, max=12),
            reraise=True
        )
        def _call():
            logger.info(f"[{self.provider_name()}] Attempting API call...")
            return self.client.models.generate_content(**kwargs)

        return _call()

    def generate_content(self, prompt: str, system_instruction: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.7)
        try:
            response = self._generate_content_with_retry(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                ),
            )
            if not response.text:
                raise GeminiError("Gemini returned an empty response.")
            return response.text
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise GeminiError(f"Gemini API call failed: {str(e)}")

    def generate_structured_output(
        self, prompt: str, system_instruction: str, response_schema: Type[BaseModel], **kwargs
    ) -> BaseModel:
        temperature = kwargs.get("temperature", 0.1)
        try:
            response = self._generate_content_with_retry(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=temperature,
                ),
            )
            if not response.text:
                raise GeminiError("Gemini returned an empty response.")
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise GeminiError(f"Gemini API call failed: {str(e)}")

        try:
            if hasattr(response, "parsed") and response.parsed is not None:
                return response.parsed
        except Exception as e:
            logger.warning("Failed to access response.parsed directly: %s. Falling back to manual JSON parsing.", str(e))

        cleaned = self._clean_json_response(response.text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise GeminiError(f"Gemini returned invalid JSON: {str(e)}")

        try:
            result = response_schema.model_validate(data)
        except Exception as e:
            raise GeminiError(f"Gemini response did not match expected schema: {str(e)}")

        return result

    @staticmethod
    def _clean_json_response(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.index("\n") if "\n" in text else 3
            text = text[first_newline + 1:]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
        return text.strip()

    def health_check(self) -> Dict[str, Any]:
        start_time = time.time()
        try:
            # Send a fast ping to verify credentials
            self.client.models.generate_content(
                model=self._model_name,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=1)
            )
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "provider": self.provider_name(),
                "status": "healthy",
                "latency_ms": latency_ms,
                "model": self.model_name(),
                "available": True,
            }
        except Exception as e:
            return {
                "provider": self.provider_name(),
                "status": "unhealthy",
                "latency_ms": None,
                "model": self.model_name(),
                "available": False,
                "error": str(e),
            }

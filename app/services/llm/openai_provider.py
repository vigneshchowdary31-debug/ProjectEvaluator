"""
OpenAI Provider implementation.
"""

import json
import logging
import time
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

from app.config import get_settings
from app.services.llm.base_provider import BaseLLMProvider, LLMError

logger = logging.getLogger(__name__)


class OpenAIProviderError(LLMError):
    """Raised when OpenAI API interaction fails."""
    pass


class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise OpenAIProviderError("openai python package is not installed.")

        settings = get_settings()
        self.api_key = settings.OPENAI_API_KEY
        self._model_name = settings.OPENAI_MODEL

        if not self.api_key:
            raise OpenAIProviderError("OPENAI_API_KEY is not configured.")

        self.client = OpenAI(api_key=self.api_key)

    def provider_name(self) -> str:
        return "openai"

    def model_name(self) -> str:
        return self._model_name

    def _generate_content_with_retry(self, **kwargs):
        """Invoke openai with tenacity retry logic for reliability."""
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1.5, min=2, max=12),
            reraise=True
        )
        def _call():
            logger.info(f"[{self.provider_name()}] Attempting API call...")
            return self.client.chat.completions.create(**kwargs)

        return _call()

    def generate_content(self, prompt: str, system_instruction: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.7)
        try:
            response = self._generate_content_with_retry(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if not content:
                raise OpenAIProviderError("OpenAI returned an empty response.")
            return content
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise OpenAIProviderError(f"OpenAI API call failed: {str(e)}")

    def generate_structured_output(
        self, prompt: str, system_instruction: str, response_schema: Type[BaseModel], **kwargs
    ) -> BaseModel:
        temperature = kwargs.get("temperature", 0.1)
        try:
            response = self._generate_content_with_retry(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_schema.__name__,
                        "schema": response_schema.model_json_schema()
                    }
                }
            )
            content = response.choices[0].message.content
            if not content:
                raise OpenAIProviderError("OpenAI returned an empty response.")
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise OpenAIProviderError(f"OpenAI API call failed: {str(e)}")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise OpenAIProviderError(f"OpenAI returned invalid JSON: {str(e)}")

        try:
            result = response_schema.model_validate(data)
        except Exception as e:
            raise OpenAIProviderError(f"OpenAI response did not match expected schema: {str(e)}")

        return result

    def health_check(self) -> Dict[str, Any]:
        start_time = time.time()
        try:
            # Send a fast ping to verify credentials
            self.client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1
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

"""
Base LLM Provider interface.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel


class LLMError(Exception):
    """Base exception for all LLM errors."""
    pass


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_content(self, prompt: str, system_instruction: str, **kwargs) -> str:
        """Generate text content from prompt."""
        pass

    @abstractmethod
    def generate_structured_output(
        self, prompt: str, system_instruction: str, response_schema: Type[BaseModel], **kwargs
    ) -> BaseModel:
        """Generate structured JSON output matching a Pydantic schema."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Return provider health status and latency."""
        pass

    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g. 'gemini', 'openai')."""
        pass

    @abstractmethod
    def model_name(self) -> str:
        """Return the default model name in use."""
        pass

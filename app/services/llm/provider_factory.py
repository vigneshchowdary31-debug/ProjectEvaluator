"""
LLM Provider Factory.
"""

import logging
from typing import Dict, Type

from app.services.llm.base_provider import BaseLLMProvider, LLMError
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

PROVIDERS: Dict[str, Type[BaseLLMProvider]] = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}

class ProviderFactory:
    @staticmethod
    def get_provider(provider_name: str) -> BaseLLMProvider:
        """Instantiate and return the requested provider."""
        provider_name = provider_name.lower().strip()
        provider_class = PROVIDERS.get(provider_name)
        if not provider_class:
            raise LLMError(f"Provider '{provider_name}' is not supported. Available: {list(PROVIDERS.keys())}")
        
        try:
            return provider_class()
        except Exception as e:
            logger.error(f"Failed to instantiate provider '{provider_name}': {e}")
            raise LLMError(f"Failed to instantiate provider '{provider_name}': {e}")

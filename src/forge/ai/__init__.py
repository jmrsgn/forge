"""Provider-independent AI generation API."""

from forge.ai.contracts import (
    AIProvider,
    GenerationRequest,
    GenerationResponse,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderExecutionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from forge.ai.providers import FakeProvider, resolve_provider
from forge.ai.settings import ProviderName, ProviderSettings

__all__ = [
    "AIProvider",
    "FakeProvider",
    "GenerationRequest",
    "GenerationResponse",
    "ProviderAuthenticationError",
    "ProviderConfigurationError",
    "ProviderError",
    "ProviderExecutionError",
    "ProviderName",
    "ProviderRateLimitError",
    "ProviderSettings",
    "ProviderTimeoutError",
    "resolve_provider",
]

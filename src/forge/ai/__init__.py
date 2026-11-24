"""Provider-independent AI generation API."""

from forge.ai.contracts import (
    AIProvider,
    TextGenerationRequest,
    TextGenerationResponse,
)
from forge.ai.providers import FakeProvider, resolve_provider
from forge.ai.settings import ProviderName, ProviderSettings

__all__ = [
    "AIProvider",
    "FakeProvider",
    "ProviderName",
    "ProviderSettings",
    "TextGenerationRequest",
    "TextGenerationResponse",
    "resolve_provider",
]

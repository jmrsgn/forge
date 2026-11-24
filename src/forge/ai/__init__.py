"""Provider-independent AI generation API."""

from forge.ai.contracts import (
    AIProvider,
    GenerationRequest,
    GenerationResponse,
)
from forge.ai.providers import FakeProvider, resolve_provider
from forge.ai.settings import ProviderName, ProviderSettings

__all__ = [
    "AIProvider",
    "FakeProvider",
    "GenerationRequest",
    "GenerationResponse",
    "ProviderName",
    "ProviderSettings",
    "resolve_provider",
]

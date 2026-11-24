"""Provider-independent text generation contracts."""

from typing import Protocol

from pydantic import BaseModel

from forge.error.provider_errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderExecutionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from forge.utils.text_utils import NonBlankText

__all__ = [
    "AIProvider",
    "GenerationRequest",
    "GenerationResponse",
    "ProviderAuthenticationError",
    "ProviderConfigurationError",
    "ProviderError",
    "ProviderExecutionError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
]


class GenerationRequest(BaseModel):
    """A validated text prompt sent to an AI provider."""

    prompt: NonBlankText


class GenerationResponse(BaseModel):
    """Validated text returned by an AI provider."""

    text: NonBlankText


class AIProvider(Protocol):
    """The provider-independent contract for text generation."""

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate a text response for one request."""
        ...

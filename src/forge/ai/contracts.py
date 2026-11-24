"""Provider-independent text generation contracts."""

from typing import Protocol

from pydantic import BaseModel

from forge.utils.text_utils import NonBlankText


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


class ProviderError(Exception):
    """Base error for provider setup and execution."""


class ProviderConfigurationError(ProviderError):
    """Provider settings or credentials are invalid."""


class ProviderAuthenticationError(ProviderError):
    """The provider rejected authentication."""


class ProviderTimeoutError(ProviderError):
    """The provider request timed out."""


class ProviderRateLimitError(ProviderError):
    """The provider rejected a request due to rate limiting."""


class ProviderExecutionError(ProviderError):
    """The provider request failed or returned unusable output."""

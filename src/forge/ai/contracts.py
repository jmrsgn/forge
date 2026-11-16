"""Provider-independent text generation contracts."""

from typing import Annotated, Protocol

from pydantic import AfterValidator, BaseModel


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("Text must not be blank")
    return value


NonBlankText = Annotated[str, AfterValidator(_nonblank)]


class GenerationRequest(BaseModel):
    prompt: NonBlankText


class GenerationResponse(BaseModel):
    text: NonBlankText


class AIProvider(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResponse: ...


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

"""Provider-independent text generation contracts."""

from typing import Protocol

from pydantic import BaseModel

from forge.utils.text_utils import NonBlankText

__all__ = [
    "AIProvider",
    "GenerationRequest",
    "GenerationResponse",
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

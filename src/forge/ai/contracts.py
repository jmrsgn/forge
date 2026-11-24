"""Provider-independent text generation contracts."""

from typing import Protocol

from pydantic import BaseModel

from forge.utils.text_utils import NonBlankText

__all__ = [
    "AIProvider",
    "TextGenerationRequest",
    "TextGenerationResponse",
]


class TextGenerationRequest(BaseModel):
    """A validated text prompt sent to an AI provider."""

    prompt: NonBlankText


class TextGenerationResponse(BaseModel):
    """Validated text returned by an AI provider."""

    text: NonBlankText


class AIProvider(Protocol):
    """The provider-independent contract for text generation."""

    def generate_text_response(self, request: TextGenerationRequest) -> TextGenerationResponse:
        """Generate a text response for one request."""
        ...

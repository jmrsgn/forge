"""Concrete providers and explicit provider resolution."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from forge.ai.contracts import AIProvider, GenerationRequest, GenerationResponse
from forge.ai.settings import ProviderName, ProviderSettings
from forge.configuration.environment import load_local_environment
from forge.error.provider_errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderExecutionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

_OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class FakeProvider:
    """Deterministic local provider for tests and offline workflows."""

    def __init__(self, response_text: str = "Fake response") -> None:
        """Validate and store the fixed response text."""

        self._response = GenerationResponse(text=response_text)

    def generate_text_response(self, request: GenerationRequest) -> GenerationResponse:
        """Return the fixed response without a network request."""

        return self._response


class OpenAIProvider:
    """Minimal text-only adapter for the OpenAI Responses API."""

    def __init__(self, *, model: str, api_key: str, timeout_seconds: float) -> None:
        """Keep runtime settings for later generation requests."""

        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def generate_text_response(self, request: GenerationRequest) -> GenerationResponse:
        """Send a text request and return the provider's validated output."""

        body = json.dumps({"model": self._model, "input": request.prompt, "store": False}).encode(
            "utf-8"
        )

        http_request = Request(
            _OPENAI_RESPONSES_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(http_request, timeout=self._timeout_seconds) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise ProviderAuthenticationError("OpenAI authentication failed") from None
            if exc.code == 429:
                raise ProviderRateLimitError("OpenAI rate limit reached") from None
            raise ProviderExecutionError(f"OpenAI request failed with HTTP {exc.code}") from None
        except TimeoutError:
            raise ProviderTimeoutError("OpenAI request timed out") from None
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ProviderTimeoutError("OpenAI request timed out") from None
            raise ProviderExecutionError("OpenAI request could not be completed") from None
        except (ValueError, UnicodeError, OSError):
            raise ProviderExecutionError("OpenAI returned an invalid response") from None

        try:
            if payload["status"] != "completed":
                raise ValueError
            # Build response text from all output_text items in all message items, in order
            parts = [
                content["text"]
                for item in payload["output"]
                if item.get("type") == "message"
                for content in item["content"]
                if content.get("type") == "output_text"
            ]

            return GenerationResponse(text="".join(parts))
        except (AttributeError, KeyError, TypeError, ValueError):
            raise ProviderExecutionError("OpenAI returned no usable text") from None


def resolve_provider(settings: ProviderSettings) -> AIProvider:
    """Select a configured provider without reading project.yaml."""

    if settings.provider is ProviderName.FAKE:
        return FakeProvider()
    if (
        settings.provider is not ProviderName.OPENAI
        or not settings.model
        or not settings.model.strip()
    ):
        raise ProviderConfigurationError("Unsupported or incomplete provider configuration")

    api_key = os.environ.get("OPENAI_API_KEY")

    if api_key is None:
        load_local_environment()
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        raise ProviderConfigurationError("OPENAI_API_KEY is required for the OpenAI provider")

    return OpenAIProvider(
        model=settings.model, api_key=api_key, timeout_seconds=settings.timeout_seconds
    )

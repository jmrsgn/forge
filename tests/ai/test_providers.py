"""Deterministic tests for provider contracts, selection, and errors."""

import io
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from pydantic import ValidationError

from forge.ai import (
    FakeProvider,
    ProviderName,
    ProviderSettings,
    TextGenerationRequest,
    TextGenerationResponse,
    providers,
    resolve_provider,
)
from forge.configuration import environment
from forge.error.provider_errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderExecutionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


def test_request_and_response_require_nonblank_text() -> None:
    request = TextGenerationRequest(prompt="  Hello  ")
    response = TextGenerationResponse(text="  World  ")

    assert request.prompt == "  Hello  "
    assert response.text == "  World  "
    with pytest.raises(ValidationError):
        TextGenerationRequest(prompt=" \t ")
    with pytest.raises(ValidationError):
        TextGenerationResponse(text=" ")


def test_fake_provider_needs_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = resolve_provider(ProviderSettings(provider="fake"))

    assert isinstance(provider, FakeProvider)
    assert (
        provider.generate_text_response(TextGenerationRequest(prompt="Hello")).text
        == "Fake response"
    )
    assert (
        FakeProvider("Test answer")
        .generate_text_response(TextGenerationRequest(prompt="Hello"))
        .text
        == "Test answer"
    )


@pytest.mark.parametrize(
    "values",
    [
        {"provider": "unknown"},
        {"provider": "openai"},
        {"provider": "openai", "model": "  "},
        {"provider": "fake", "model": "unused"},
        {"provider": "fake", "timeout_seconds": 0},
        {"provider": "fake", "timeout_seconds": float("inf")},
    ],
)
def test_invalid_settings_are_rejected(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ProviderSettings.model_validate(values)


def test_openai_requires_environment_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(environment, "LOCAL_ENV_PATH", tmp_path / "missing.env")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        resolve_provider(ProviderSettings(provider="openai", model="example-model"))

    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        resolve_provider(ProviderSettings(provider="openai", model="example-model"))


def test_openai_resolver_uses_local_env_when_os_key_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=local-test-key\n", encoding="utf-8")
    monkeypatch.setattr(environment, "LOCAL_ENV_PATH", env_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    provider = resolve_provider(ProviderSettings(provider="openai", model="example-model"))

    assert isinstance(provider, providers.OpenAIProvider)
    assert os.environ["OPENAI_API_KEY"] == "local-test-key"


def test_openai_request_uses_model_key_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> io.BytesIO:
        captured["request"] = request
        captured["timeout"] = timeout
        return io.BytesIO(
            json.dumps(
                {
                    "status": "completed",
                    "output": [
                        {"type": "message", "content": [{"type": "output_text", "text": "Hello!"}]}
                    ],
                }
            ).encode()
        )

    monkeypatch.setattr(providers, "urlopen", fake_urlopen)
    settings = ProviderSettings(provider="openai", model="example-model", timeout_seconds=5)
    provider = resolve_provider(settings)

    assert provider.generate_text_response(TextGenerationRequest(prompt="Hi")).text == "Hello!"
    request = captured["request"]
    assert request.full_url == "https://api.openai.com/v1/responses"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert json.loads(request.data) == {"model": "example-model", "input": "Hi", "store": False}
    assert captured["timeout"] == 5
    assert ProviderSettings(provider=ProviderName.FAKE).timeout_seconds == 30.0


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, ProviderAuthenticationError),
        (429, ProviderRateLimitError),
        (500, ProviderExecutionError),
    ],
)
def test_openai_http_errors_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, status: int, error_type: type[Exception]
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fail_request(request: object, timeout: float) -> None:
        raise HTTPError("https://example.invalid/secret-prompt", status, "secret-key", None, None)

    monkeypatch.setattr(providers, "urlopen", fail_request)
    provider = resolve_provider(ProviderSettings(provider="openai", model="example-model"))

    with pytest.raises(error_type) as caught:
        provider.generate_text_response(TextGenerationRequest(prompt="private prompt"))

    assert "secret" not in str(caught.value)
    assert "private prompt" not in str(caught.value)


def test_openai_timeout_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def timeout_request(request: object, timeout: float) -> None:
        raise TimeoutError("private prompt and secret-key")

    monkeypatch.setattr(providers, "urlopen", timeout_request)
    provider = resolve_provider(ProviderSettings(provider="openai", model="example-model"))

    with pytest.raises(ProviderTimeoutError) as caught:
        provider.generate_text_response(TextGenerationRequest(prompt="private prompt"))

    assert "private prompt" not in str(caught.value)
    assert "secret-key" not in str(caught.value)


def test_wrapped_network_timeout_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def timeout_request(request: object, timeout: float) -> None:
        raise URLError(TimeoutError("private prompt"))

    monkeypatch.setattr(providers, "urlopen", timeout_request)
    provider = resolve_provider(ProviderSettings(provider="openai", model="example-model"))

    with pytest.raises(ProviderTimeoutError, match="timed out"):
        provider.generate_text_response(TextGenerationRequest(prompt="private prompt"))


def test_openai_rejects_unusable_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        providers,
        "urlopen",
        lambda request, timeout: io.BytesIO(b'{"status":"completed","output":[]}'),
    )
    provider = resolve_provider(ProviderSettings(provider="openai", model="example-model"))

    with pytest.raises(ProviderExecutionError, match="no usable text"):
        provider.generate_text_response(TextGenerationRequest(prompt="Hi"))

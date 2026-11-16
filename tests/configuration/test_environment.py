"""Local environment loading preserves operating-system values."""

import os
from pathlib import Path

import pytest

from forge.configuration import environment


def test_local_env_supplies_missing_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=local-test-key\n", encoding="utf-8")
    monkeypatch.setattr(environment, "LOCAL_ENV_PATH", env_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    environment.load_local_environment()

    assert os.environ["OPENAI_API_KEY"] == "local-test-key"


def test_os_value_takes_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=local-test-key\n", encoding="utf-8")
    monkeypatch.setattr(environment, "LOCAL_ENV_PATH", env_path)
    monkeypatch.setenv("OPENAI_API_KEY", "os-test-key")

    environment.load_local_environment()

    assert os.environ["OPENAI_API_KEY"] == "os-test-key"

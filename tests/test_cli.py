"""Tests for the Forge command-line entry point."""

from importlib.metadata import distribution, version
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge.cli import app
from forge.workspace import validate_workspace

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Forge software engineering toolkit." in result.output
    assert "--version" in result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"forge {version('forge')}"


def test_unknown_command_reports_error() -> None:
    result = runner.invoke(app, ["unknown"])

    assert result.exit_code == 2
    assert "No such command 'unknown'" in result.output


def test_init_help() -> None:
    result = runner.invoke(app, ["init", "--help"])

    assert result.exit_code == 0
    assert "--mode" in result.output
    assert "--name" in result.output
    assert "--path" in result.output


def test_init_uses_current_directory_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", "--mode", "greenfield", "--name", "Fitness App"])

    assert result.exit_code == 0
    assert "Initialized greenfield Forge workspace" in result.output
    assert validate_workspace(tmp_path).name == "Fitness App"


def test_init_brownfield_preserves_files(tmp_path: Path) -> None:
    application = tmp_path / "app.py"
    application.write_text("existing", encoding="utf-8")

    result = runner.invoke(
        app,
        ["init", "--mode", "brownfield", "--name", "Existing App", "--path", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert application.read_text(encoding="utf-8") == "existing"
    assert validate_workspace(tmp_path).name == "Existing App"


def test_init_rejects_missing_mode_and_invalid_mode(tmp_path: Path) -> None:
    missing = runner.invoke(app, ["init", "--name", "App", "--path", str(tmp_path)])
    invalid = runner.invoke(
        app, ["init", "--mode", "invalid", "--name", "App", "--path", str(tmp_path)]
    )

    assert missing.exit_code == 2
    assert "--mode" in missing.output
    assert invalid.exit_code == 2
    assert "invalid" in invalid.output
    assert not (tmp_path / ".forge").exists()


def test_init_reports_workflow_error(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["init", "--mode", "greenfield", "--name", "  ", "--path", str(tmp_path)]
    )

    assert result.exit_code == 1
    assert "Project name must be a nonblank string" in result.output
    assert not (tmp_path / ".forge").exists()


def test_console_script_targets_cli_app() -> None:
    entry_point = next(
        entry for entry in distribution("forge").entry_points if entry.name == "forge"
    )

    assert entry_point.value == "forge.cli:app"
    assert entry_point.load() is app

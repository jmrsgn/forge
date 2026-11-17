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


def test_init_rejects_missing_options_and_invalid_mode(tmp_path: Path) -> None:
    missing = runner.invoke(app, ["init", "--name", "App", "--path", str(tmp_path)])
    missing_name = runner.invoke(app, ["init", "--mode", "greenfield", "--path", str(tmp_path)])
    invalid = runner.invoke(
        app, ["init", "--mode", "invalid", "--name", "App", "--path", str(tmp_path)]
    )

    assert missing.exit_code == 2
    assert missing.stdout == ""
    assert "--mode" in missing.stderr
    assert missing_name.exit_code == 2
    assert missing_name.stdout == ""
    assert "--name" in missing_name.stderr
    assert invalid.exit_code == 2
    assert invalid.stdout == ""
    assert "invalid" in invalid.stderr
    assert not (tmp_path / ".forge").exists()


def test_init_reports_workflow_error(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["init", "--mode", "greenfield", "--name", "  ", "--path", str(tmp_path)]
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Project name must be a nonblank string" in result.stderr
    assert not (tmp_path / ".forge").exists()


def test_init_reports_invalid_path_on_stderr(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing"
    result = runner.invoke(
        app,
        ["init", "--mode", "brownfield", "--name", "App", "--path", str(missing_path)],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Project directory does not exist" in result.stderr
    assert not missing_path.exists()


def test_console_script_targets_cli_app() -> None:
    entry_point = next(
        entry for entry in distribution("forge").entry_points if entry.name == "forge"
    )

    assert entry_point.value == "forge.cli:app"
    assert entry_point.load() is app

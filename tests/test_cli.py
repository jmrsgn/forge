"""Tests for the Forge command-line entry point."""

from importlib.metadata import distribution, version

from typer.testing import CliRunner

from forge.cli import app

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
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 2
    assert "No such command 'init'" in result.output


def test_console_script_targets_cli_app() -> None:
    entry_point = next(
        entry for entry in distribution("forge").entry_points if entry.name == "forge"
    )

    assert entry_point.value == "forge.cli:app"
    assert entry_point.load() is app

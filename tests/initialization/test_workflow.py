"""Tests for greenfield and brownfield initialization."""

from pathlib import Path

import pytest

from forge.configuration import load_project_config
from forge.initialization import InitializationError, InitializationMode, initialize_project
from forge.workspace import validate_workspace


def test_greenfield_initializes_empty_existing_directory(tmp_path: Path) -> None:
    result = initialize_project(tmp_path, InitializationMode.GREENFIELD, "Fitness App")

    assert result.mode is InitializationMode.GREENFIELD
    assert result.project_dir == tmp_path
    assert result.workspace_dir == tmp_path / ".forge"
    assert validate_workspace(tmp_path) == result.config
    assert load_project_config(result.workspace_dir / "project.yaml").name == "Fitness App"
    assert sorted(path.name for path in tmp_path.iterdir()) == [".forge"]


def test_brownfield_preserves_existing_application_files(tmp_path: Path) -> None:
    application = tmp_path / "app.py"
    application.write_text("print('existing')\n", encoding="utf-8")
    source_dir = tmp_path / "src"
    source_dir.mkdir()

    result = initialize_project(tmp_path, InitializationMode.BROWNFIELD, "Existing App")

    assert result.mode is InitializationMode.BROWNFIELD
    assert validate_workspace(tmp_path) == result.config
    assert application.read_text(encoding="utf-8") == "print('existing')\n"
    assert source_dir.is_dir()
    assert sorted(path.name for path in tmp_path.iterdir()) == [".forge", "app.py", "src"]


@pytest.mark.parametrize("mode", ["unknown", ""])
def test_invalid_mode_is_rejected(tmp_path: Path, mode: str) -> None:
    with pytest.raises(InitializationError, match="Mode must be"):
        initialize_project(tmp_path, mode, "App")

    assert not (tmp_path / ".forge").exists()


def test_blank_name_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(InitializationError, match="nonblank"):
        initialize_project(tmp_path, InitializationMode.GREENFIELD, " \t ")

    assert not (tmp_path / ".forge").exists()


def test_invalid_project_directory_is_rejected(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(InitializationError, match="Project directory"):
        initialize_project(missing, InitializationMode.GREENFIELD, "App")

    assert not missing.exists()


def test_greenfield_rejects_nonempty_directory_without_changes(tmp_path: Path) -> None:
    existing_file = tmp_path / "app.py"
    existing_file.write_text("keep me", encoding="utf-8")

    with pytest.raises(InitializationError, match="must be empty"):
        initialize_project(tmp_path, InitializationMode.GREENFIELD, "App")

    assert existing_file.read_text(encoding="utf-8") == "keep me"
    assert not (tmp_path / ".forge").exists()


@pytest.mark.parametrize("mode", [InitializationMode.GREENFIELD, InitializationMode.BROWNFIELD])
def test_repeated_initialization_preserves_workspace(
    tmp_path: Path, mode: InitializationMode
) -> None:
    initialize_project(tmp_path, mode, "Original")
    marker = tmp_path / ".forge" / "rules" / "user.txt"
    marker.write_text("keep me", encoding="utf-8")

    with pytest.raises(InitializationError, match="already exists"):
        initialize_project(tmp_path, mode, "Replacement")

    assert marker.read_text(encoding="utf-8") == "keep me"
    assert validate_workspace(tmp_path).name == "Original"

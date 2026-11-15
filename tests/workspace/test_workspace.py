"""Tests for safe Forge workspace creation and validation."""

from pathlib import Path

import pytest

from forge.configuration import ProjectConfig, load_project_config
from forge.workspace import WorkspaceError, create_workspace, validate_workspace

DIRECTORIES = ("agents", "skills", "rules", "knowledge")


def test_create_workspace_writes_valid_configuration_and_empty_directories(tmp_path: Path) -> None:
    config = ProjectConfig(schema_version=1, name="Fitness App")

    workspace = create_workspace(tmp_path, config)

    assert workspace == tmp_path / ".forge"
    assert load_project_config(workspace / "project.yaml") == config
    assert sorted(path.name for path in workspace.iterdir()) == [
        "agents",
        "knowledge",
        "project.yaml",
        "rules",
        "skills",
    ]
    assert all(
        (workspace / name).is_dir() and not list((workspace / name).iterdir())
        for name in DIRECTORIES
    )


def test_create_rejects_existing_workspace_without_changes(tmp_path: Path) -> None:
    workspace = tmp_path / ".forge"
    workspace.mkdir()
    existing_file = workspace / "user.txt"
    existing_file.write_text("keep me", encoding="utf-8")

    with pytest.raises(WorkspaceError, match="already exists"):
        create_workspace(tmp_path, ProjectConfig(schema_version=1, name="Fitness App"))

    assert existing_file.read_text(encoding="utf-8") == "keep me"
    assert sorted(path.name for path in workspace.iterdir()) == ["user.txt"]


def test_create_requires_existing_project_directory(tmp_path: Path) -> None:
    target = tmp_path / "missing"

    with pytest.raises(WorkspaceError, match="Project directory"):
        create_workspace(target, ProjectConfig(schema_version=1, name="Fitness App"))

    assert not target.exists()


def test_validate_created_workspace(tmp_path: Path) -> None:
    config = ProjectConfig(schema_version=1, name="Fitness App")
    create_workspace(tmp_path, config)

    assert validate_workspace(tmp_path) == config


def test_validate_rejects_missing_workspace(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="workspace is missing"):
        validate_workspace(tmp_path)


def test_validate_rejects_missing_directory(tmp_path: Path) -> None:
    workspace = create_workspace(tmp_path, ProjectConfig(schema_version=1, name="Fitness App"))
    (workspace / "agents").rmdir()

    with pytest.raises(WorkspaceError, match="agents"):
        validate_workspace(tmp_path)


def test_validate_rejects_invalid_configuration(tmp_path: Path) -> None:
    workspace = create_workspace(tmp_path, ProjectConfig(schema_version=1, name="Fitness App"))
    (workspace / "project.yaml").write_text(
        "schema_version: 2\nname: Fitness App\n", encoding="utf-8"
    )

    with pytest.raises(WorkspaceError, match="Unsupported schema version"):
        validate_workspace(tmp_path)


@pytest.mark.parametrize("wrong_path", [".forge", "project.yaml", "agents"])
def test_validate_rejects_wrong_file_types(tmp_path: Path, wrong_path: str) -> None:
    if wrong_path == ".forge":
        (tmp_path / ".forge").write_text("not a directory", encoding="utf-8")
    else:
        workspace = create_workspace(tmp_path, ProjectConfig(schema_version=1, name="Fitness App"))
        path = workspace / wrong_path
        if wrong_path == "project.yaml":
            path.unlink()
            path.mkdir()
        else:
            path.rmdir()
            path.write_text("not a directory", encoding="utf-8")

    with pytest.raises(WorkspaceError, match=wrong_path):
        validate_workspace(tmp_path)

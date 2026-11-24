"""Filesystem operations for the initial .forge workspace."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from forge.configuration import ConfigurationError, ProjectConfig, load_project_config
from forge.error.workspace_errors import WorkspaceError

REQUIRED_DIRECTORIES = ("agents", "skills", "rules", "knowledge")


def create_workspace(project_dir: str | Path, config: ProjectConfig) -> Path:
    """Create a new .forge workspace in an existing project directory."""
    target = Path(project_dir)
    if not target.is_dir():
        raise WorkspaceError(f"Project directory does not exist or is not a directory: {target}")

    try:
        validated_config = ProjectConfig.model_validate(config.model_dump())
    except ValidationError as exc:
        raise WorkspaceError("Project configuration is invalid") from exc

    workspace = target / ".forge"
    try:
        workspace.mkdir()
    except FileExistsError as exc:
        raise WorkspaceError(f"Forge workspace already exists: {workspace}") from exc
    except OSError as exc:
        raise WorkspaceError(f"Cannot create Forge workspace {workspace}: {exc}") from exc

    try:
        for name in REQUIRED_DIRECTORIES:
            (workspace / name).mkdir()
        with (workspace / "project.yaml").open("x", encoding="utf-8") as file:
            yaml.safe_dump(validated_config.model_dump(), file, sort_keys=False, allow_unicode=True)
    except OSError as exc:
        raise WorkspaceError(f"Cannot complete Forge workspace {workspace}: {exc}") from exc

    return workspace


def validate_workspace(project_dir: str | Path) -> ProjectConfig:
    """Check the required workspace structure and return its validated configuration."""
    workspace = Path(project_dir) / ".forge"
    if workspace.is_symlink() or not workspace.is_dir():
        raise WorkspaceError(f"Forge workspace is missing or not a directory: {workspace}")

    config_path = workspace / "project.yaml"
    if config_path.is_symlink() or not config_path.is_file():
        raise WorkspaceError(f"Forge configuration is missing or not a file: {config_path}")

    for name in REQUIRED_DIRECTORIES:
        directory = workspace / name
        if directory.is_symlink() or not directory.is_dir():
            raise WorkspaceError(f"Required workspace directory is missing or invalid: {directory}")

    try:
        return load_project_config(config_path)
    except ConfigurationError as exc:
        raise WorkspaceError(f"Invalid Forge workspace configuration: {exc}") from exc

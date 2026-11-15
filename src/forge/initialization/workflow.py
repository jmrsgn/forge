"""Initialize Forge in a new or existing project directory."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from forge.configuration.models import CURRENT_SCHEMA_VERSION, ProjectConfig
from forge.workspace import WorkspaceError, create_workspace


class InitializationMode(str, Enum):
    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"


class InitializationError(ValueError):
    """The project cannot be initialized with the supplied inputs."""


@dataclass(frozen=True, slots=True)
class InitializationResult:
    mode: InitializationMode
    project_dir: Path
    workspace_dir: Path
    config: ProjectConfig


def initialize_project(
    project_dir: str | Path, mode: InitializationMode | str, name: str
) -> InitializationResult:
    """Create a Forge workspace after checking the selected initialization mode."""
    try:
        selected_mode = InitializationMode(mode)
    except ValueError as exc:
        raise InitializationError("Mode must be 'greenfield' or 'brownfield'") from exc

    if not isinstance(name, str) or not name.strip():
        raise InitializationError("Project name must be a nonblank string")

    target = Path(project_dir)
    if not target.is_dir():
        raise InitializationError(
            f"Project directory does not exist or is not a directory: {target}"
        )

    workspace_path = target / ".forge"
    if workspace_path.exists() or workspace_path.is_symlink():
        raise InitializationError(f"Forge workspace already exists: {workspace_path}")

    if selected_mode is InitializationMode.GREENFIELD:
        try:
            if any(target.iterdir()):
                raise InitializationError(f"Greenfield project directory must be empty: {target}")
        except OSError as exc:
            raise InitializationError(f"Cannot inspect project directory {target}: {exc}") from exc

    config = ProjectConfig(schema_version=CURRENT_SCHEMA_VERSION, name=name)
    try:
        workspace_dir = create_workspace(target, config)
    except WorkspaceError as exc:
        raise InitializationError(str(exc)) from exc

    return InitializationResult(
        mode=selected_mode, project_dir=target, workspace_dir=workspace_dir, config=config
    )

"""Atomic local persistence for one discovery session per Forge workspace.

The Forge-owned ``.forge/discovery.json`` file contains the canonical discovery,
its derived revision checksum, and ordered review decisions. The specification
and Markdown are regenerated; neither is stored as another editable copy.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from forge.discovery.models import ProjectDiscovery
from forge.discovery.state import PERSISTENCE_SCHEMA_VERSION, DiscoveryState, new_discovery_state
from forge.error.persistence_errors import DiscoveryPersistenceError
from forge.workspace import WorkspaceError, validate_workspace

DISCOVERY_FILE = "discovery.json"


def _state_path(project_dir: str | Path) -> Path:
    """Keep discovery storage inside an existing validated Forge workspace."""
    project = Path(project_dir)
    try:
        validate_workspace(project)
    except WorkspaceError as exc:
        raise DiscoveryPersistenceError(f"Invalid Forge workspace: {exc}") from exc
    return project / ".forge" / DISCOVERY_FILE


def _validated_state(state: DiscoveryState) -> DiscoveryState:
    """Revalidate even when a caller has mutated nested Pydantic data."""
    if not isinstance(state, DiscoveryState):
        raise DiscoveryPersistenceError("Discovery state must be a DiscoveryState")
    try:
        return DiscoveryState.model_validate(state.model_dump())
    except (ValidationError, ValueError) as exc:
        raise DiscoveryPersistenceError("Discovery state is invalid") from exc


def _write_state(path: Path, state: DiscoveryState, *, create: bool) -> None:
    """Publish a fully written file by exclusive link or atomic replacement."""
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=".discovery-", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(state.model_dump_json(indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if create:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    except FileExistsError as exc:
        raise DiscoveryPersistenceError(f"Discovery state already exists: {path}") from exc
    except OSError as exc:
        raise DiscoveryPersistenceError(f"Cannot write discovery state: {exc.strerror}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys rather than accepting the last value."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def create_discovery(project_dir: str | Path, discovery: ProjectDiscovery) -> DiscoveryState:
    """Create a new persisted discovery without replacing any existing state."""
    try:
        state = new_discovery_state(discovery)
    except (ValidationError, ValueError, TypeError) as exc:
        raise DiscoveryPersistenceError("Discovery data is invalid") from exc
    path = _state_path(project_dir)
    _write_state(path, state, create=True)
    return state


def load_discovery(project_dir: str | Path) -> DiscoveryState:
    """Reload a session for resumption without invoking analysis or clarification."""
    path = _state_path(project_dir)
    if path.is_symlink():
        raise DiscoveryPersistenceError("Discovery state cannot be a symbolic link")
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise DiscoveryPersistenceError(f"Discovery state does not exist: {path}") from exc
    except UnicodeError as exc:
        raise DiscoveryPersistenceError("Malformed discovery JSON encoding") from exc
    except OSError as exc:
        raise DiscoveryPersistenceError(f"Cannot read discovery state: {exc.strerror}") from exc
    try:
        raw = json.loads(raw_text, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError) as exc:
        raise DiscoveryPersistenceError("Malformed discovery JSON") from exc
    if not isinstance(raw, dict):
        raise DiscoveryPersistenceError("Discovery JSON must contain an object")
    version = raw.get("schema_version")
    if type(version) is not int:
        raise DiscoveryPersistenceError(
            "Discovery persistence schema version is missing or invalid"
        )
    if version != PERSISTENCE_SCHEMA_VERSION:
        raise DiscoveryPersistenceError(
            f"Unsupported discovery persistence schema version: {version}"
        )
    try:
        return DiscoveryState.model_validate_json(raw_text)
    except (ValidationError, ValueError) as exc:
        raise DiscoveryPersistenceError("Invalid discovery state or approval metadata") from exc


def save_discovery(project_dir: str | Path, state: DiscoveryState) -> DiscoveryState:
    """Replace an existing state atomically, rejecting stale or lost decisions.

    The returned state has an incremented generation and should be used for the
    next save. This detects sequential stale writes; no cross-process lock is used.
    """
    validated = _validated_state(state)
    current = load_discovery(project_dir)
    if validated.generation != current.generation:
        raise DiscoveryPersistenceError("Discovery state changed since it was loaded")
    if validated.discovery.original_idea != current.discovery.original_idea:
        raise DiscoveryPersistenceError("The original project idea cannot be changed")
    if validated.review_history[: len(current.review_history)] != current.review_history:
        raise DiscoveryPersistenceError("Discovery update would discard recorded review decisions")
    updated = DiscoveryState.model_validate(
        {**validated.model_dump(), "generation": current.generation + 1}
    )
    _write_state(_state_path(project_dir), updated, create=False)
    return updated

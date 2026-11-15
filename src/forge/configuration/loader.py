"""Load Forge project configuration from YAML."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from forge.configuration.models import ProjectConfig


class ConfigurationError(ValueError):
    """The project configuration could not be read or validated."""


def load_project_config(path: str | Path) -> ProjectConfig:
    """Read and validate a project configuration YAML file."""
    config_path = Path(path)
    try:
        contents = config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError(f"Cannot read configuration {config_path}: {exc}") from exc

    try:
        data = yaml.safe_load(contents)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ConfigurationError(f"Malformed YAML in {config_path}{location}") from exc

    try:
        return ProjectConfig.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(map(str, error['loc'])) or 'configuration'}: {error['msg']}"
            for error in exc.errors(include_input=False, include_context=False)
        )
        raise ConfigurationError(f"Invalid configuration in {config_path}: {details}") from exc

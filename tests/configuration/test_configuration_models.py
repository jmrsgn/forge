"""Tests for the project configuration schema."""

import pytest
from pydantic import ValidationError

from forge.configuration.models import ProjectConfig


def test_valid_project_configuration() -> None:
    config = ProjectConfig.model_validate({"schema_version": 1, "name": "  Fitness App  "})

    assert config.schema_version == 1
    assert config.name == "  Fitness App  "


@pytest.mark.parametrize(
    "values",
    [
        {"name": "Forge"},
        {"schema_version": 1},
        {"schema_version": "1", "name": "Forge"},
        {"schema_version": 1, "name": 123},
        {"schema_version": 1, "name": " \t "},
        {"schema_version": 1, "name": "Forge", "api_key": "unexpected"},
    ],
)
def test_missing_or_invalid_fields_are_rejected(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate(values)


def test_unsupported_schema_version_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Unsupported schema version"):
        ProjectConfig.model_validate({"schema_version": 2, "name": "Forge"})

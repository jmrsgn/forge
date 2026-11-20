"""Validated project configuration independent of its storage format."""

from typing import Final

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, field_validator

CURRENT_SCHEMA_VERSION: Final = 1


class ProjectConfig(BaseModel):
    """Minimal configuration for a Forge project."""

    model_config = ConfigDict(extra="forbid")

    schema_version: StrictInt
    name: StrictStr

    @field_validator("schema_version")
    @classmethod
    def supported_schema_version(cls, value: int) -> int:
        """Reject configuration versions this Forge release cannot read."""
        if value != CURRENT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema version; expected {CURRENT_SCHEMA_VERSION}")
        return value

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        """Require a project name without changing its whitespace."""
        if not value.strip():
            raise ValueError("Project name must not be blank")
        return value

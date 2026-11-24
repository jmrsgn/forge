"""Shared text validation utilities for Forge models."""

from typing import Annotated

from pydantic import AfterValidator


def _nonblank(value: str) -> str:
    """Reject blank text without changing the supplied wording."""
    if not value.strip():
        raise ValueError("Text must not be blank")
    return value


NonBlankText = Annotated[str, AfterValidator(_nonblank)]

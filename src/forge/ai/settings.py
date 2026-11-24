"""Runtime settings for explicit AI provider selection."""

from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator


class ProviderName(str, Enum):
    """Provider implementations available for explicit selection."""

    FAKE = "fake"
    OPENAI = "openai"


class ProviderSettings(BaseModel):
    """Runtime provider settings, separate from project.yaml and credentials."""

    model_config = ConfigDict(extra="forbid")

    provider: ProviderName
    model: StrictStr | None = None
    timeout_seconds: float = Field(default=30.0, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_provider(self) -> Self:
        """Require a model for OpenAI and reject one for the fake provider."""
        if self.provider is ProviderName.OPENAI and (self.model is None or not self.model.strip()):
            raise ValueError("OpenAI provider requires a nonblank model")
        if self.provider is ProviderName.FAKE and self.model is not None:
            raise ValueError("Fake provider does not use a model")

        return self

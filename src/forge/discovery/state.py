"""Validated, versioned discovery state without filesystem concerns."""

import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from forge.discovery.models import NonBlankText, ProjectDiscovery
from forge.discovery.review import (
    ReviewDecision,
    ReviewDecisionRecord,
    can_handoff,
    specification_revision,
)
from forge.discovery.specification import DiscoverySpecification, build_specification

PERSISTENCE_SCHEMA_VERSION = 1


class SequencedReviewDecision(BaseModel):
    """One review decision in deterministic, one-based recording order."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    sequence: StrictInt = Field(ge=1)
    record: ReviewDecisionRecord

    @model_validator(mode="after")
    def validate_revision_format(self) -> Self:
        """Reject decision references that cannot be Forge revision IDs."""
        if re.fullmatch(r"rev-[0-9a-f]{64}", self.record.revision_id) is None:
            raise ValueError("Review decision has an invalid specification revision")
        return self


class DiscoveryState(BaseModel):
    """The canonical discovery and ordered decisions stored in one JSON file.

    The specification is derived from discovery. Its revision is stored only as
    integrity metadata and checked whenever the state is validated.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    generation: StrictInt = Field(ge=1)
    specification_revision: NonBlankText
    discovery: ProjectDiscovery
    review_history: list[SequencedReviewDecision]

    @model_validator(mode="after")
    def validate_integrity(self) -> Self:
        """Check the derived revision and contiguous decision ordering."""
        if self.specification_revision != specification_revision(
            build_specification(self.discovery)
        ):
            raise ValueError("Stored specification revision does not match discovery")
        sequences = [entry.sequence for entry in self.review_history]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("Review decision sequences must be contiguous and ordered")
        return self

    @property
    def specification(self) -> DiscoverySpecification:
        """Regenerate the current specification from the canonical discovery."""
        self.validate_integrity()
        return build_specification(self.discovery)

    @property
    def current_decision(self) -> ReviewDecisionRecord | None:
        """Return the latest decision for this exact revision, if one exists."""
        self.validate_integrity()
        for entry in reversed(self.review_history):
            if entry.record.revision_id == self.specification_revision:
                return entry.record
        return None

    def with_discovery(self, discovery: ProjectDiscovery) -> Self:
        """Return updated discovery while retaining prior review decisions."""
        if not isinstance(discovery, ProjectDiscovery):
            raise TypeError("Updated discovery must be a ProjectDiscovery")
        validated = ProjectDiscovery.model_validate(discovery.model_dump())
        if validated.original_idea != self.discovery.original_idea:
            raise ValueError("The original project idea cannot be changed")
        return type(self)(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            generation=self.generation,
            specification_revision=specification_revision(build_specification(validated)),
            discovery=validated,
            review_history=[entry.model_dump() for entry in self.review_history],
        )

    def with_decision(self, record: ReviewDecisionRecord) -> Self:
        """Append an explicit current-revision decision without changing discovery."""
        self.validate_integrity()
        if not isinstance(record, ReviewDecisionRecord):
            raise TypeError("Review decision must be a ReviewDecisionRecord")
        validated_record = ReviewDecisionRecord.model_validate(record.model_dump())
        if validated_record.revision_id != self.specification_revision:
            raise ValueError("Review decision does not match the current specification")
        if validated_record.decision is ReviewDecision.APPROVE and not can_handoff(
            self.specification, validated_record
        ):
            raise ValueError("Approval is blocked by unresolved specification issues")
        return type(self)(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            generation=self.generation,
            specification_revision=self.specification_revision,
            discovery=self.discovery.model_dump(),
            review_history=[
                *(entry.model_dump() for entry in self.review_history),
                SequencedReviewDecision(
                    sequence=len(self.review_history) + 1, record=validated_record
                ).model_dump(),
            ],
        )


def new_discovery_state(discovery: ProjectDiscovery) -> DiscoveryState:
    """Create an unsaved state for a new discovery session."""
    if not isinstance(discovery, ProjectDiscovery):
        raise TypeError("Discovery must be a ProjectDiscovery")
    validated = ProjectDiscovery.model_validate(discovery.model_dump())
    return DiscoveryState(
        schema_version=PERSISTENCE_SCHEMA_VERSION,
        generation=1,
        specification_revision=specification_revision(build_specification(validated)),
        discovery=validated,
        review_history=[],
    )

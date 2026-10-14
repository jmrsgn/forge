"""Validated data structures for an unfinished new project discovery."""

from enum import Enum
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, Field, model_validator


def _nonblank(value: str) -> str:
    """Validate that a string contains at least one non-whitespace character."""
    if value.strip():
        return value

    raise ValueError("Text must not be blank")


# Define a type for non-blank text using Pydantic's Annotated type with a custom validator.
NonBlankText = Annotated[str, AfterValidator(_nonblank)]


# Define an enumeration for the source of information in the discovery process.
class InformationSource(str, Enum):
    """
    Identifies the origin of information collected during project discovery.

    USER: Information explicitly provided in the initial user input.
    CLARIFIED: Information confirmed or provided during clarification.
    INFERRED: Information inferred by AI that has not been confirmed by the user.
    """

    USER = "user"
    CLARIFIED = "clarified"
    INFERRED = "inferred"


class DiscoveryItem(BaseModel):
    """
    Represents a piece of information collected during project discovery.

    Tracks the information's statement, source, and supporting interaction reference.
    A valid reference does not establish that the interaction supports the statement.
    """

    statement: NonBlankText
    source: InformationSource
    evidence_ref: NonBlankText | None = None

    @model_validator(mode="after")
    def validate_evidence_ref(self) -> Self:
        if self.source is InformationSource.USER and self.evidence_ref != "original_idea":
            raise ValueError("USER information requires original_idea evidence")
        if self.source is InformationSource.CLARIFIED and (
            self.evidence_ref is None
            or not self.evidence_ref.startswith("clarification:")
            or not self.evidence_ref.removeprefix("clarification:").strip()
        ):
            raise ValueError("CLARIFIED information requires a clarification:<id> reference")
        if self.source is InformationSource.INFERRED and self.evidence_ref is not None:
            raise ValueError("INFERRED information cannot have confirming evidence")
        return self


class Requirement(DiscoveryItem):
    """
    Represents a functional or quality requirement identified during discovery.

    Inherits the statement and information source from DiscoveryItem,
    allowing Forge to track each requirement's origin.
    """


class ProjectIdentity(BaseModel):
    """
    Represents the basic identity of the project being discovered.

    Stores the project's name and summary, both of which are optional
    because they may not be known during the initial discovery stage.
    """

    name: DiscoveryItem | None = None
    summary: DiscoveryItem | None = None


class ProjectProblem(BaseModel):
    """
    Describes the problem the proposed project aims to solve.

    Contains an optional problem statement and a collection of goals
    that capture the intended outcomes of the project.
    """

    statement: DiscoveryItem | None = None
    goals: list[DiscoveryItem] = Field(default_factory=list)


class ProjectTargetUser(BaseModel):
    """
    Represents an intended user or user group of the proposed project.

    Captures the target user's role, an optional description, and the
    goals they want to accomplish through the proposed system.
    """

    name: DiscoveryItem
    description: DiscoveryItem | None = None
    goals: list[DiscoveryItem] = Field(default_factory=list)


class UseCase(BaseModel):
    """
    Represents an interaction between a user and the proposed system.

    Defines the actor performing the interaction, the objective they
    want to achieve, and the expected outcome of that interaction.
    """

    actor: DiscoveryItem
    objective: DiscoveryItem
    expected_outcome: DiscoveryItem


class OpenQuestion(BaseModel):
    """
    Represents an unresolved question identified during discovery.

    The blocking flag indicates whether the question must be resolved
    before Forge can consider the discovery ready for approval.
    """

    question: NonBlankText
    blocking: bool = False


class ProjectDiscovery(BaseModel):
    """
    Represents the evolving discovery state of a new software project.

    Preserves the user's original idea while organizing the project's
    identity, problem, users, use cases, requirements, constraints,
    assumptions, scope boundaries, and unresolved questions.

    Supports incomplete discovery sessions so information can be
    progressively collected and refined through clarification.
    """

    original_idea: NonBlankText = Field(frozen=True)
    identity: ProjectIdentity = Field(default_factory=ProjectIdentity)
    problem: ProjectProblem | None = None
    target_users: list[ProjectTargetUser] = Field(default_factory=list)
    use_cases: list[UseCase] = Field(default_factory=list)
    functional_requirements: list[Requirement] = Field(default_factory=list)
    quality_requirements: list[Requirement] = Field(default_factory=list)
    constraints: list[DiscoveryItem] = Field(default_factory=list)
    assumptions: list[DiscoveryItem] = Field(default_factory=list)
    out_of_scope: list[DiscoveryItem] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)

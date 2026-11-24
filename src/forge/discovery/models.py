"""Validated data structures for an unfinished new project discovery."""

from enum import Enum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

from forge.utils.text_utils import NonBlankText


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
    Corrected claims must be represented by a new validated item.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    statement: NonBlankText
    source: InformationSource
    evidence_ref: NonBlankText | None = None

    @model_validator(mode="after")
    def validate_evidence_ref(self) -> Self:
        """Enforce the evidence-reference rule for this item's source."""
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

    model_config = ConfigDict(extra="forbid")

    name: DiscoveryItem | None = None
    summary: DiscoveryItem | None = None


class ProjectProblem(BaseModel):
    """
    Describes the problem the proposed project aims to solve.

    Contains an optional problem statement and a collection of goals
    that capture the intended outcomes of the project.
    """

    model_config = ConfigDict(extra="forbid")

    statement: DiscoveryItem | None = None
    goals: list[DiscoveryItem] = Field(default_factory=list)


class ProjectTargetUser(BaseModel):
    """
    Represents an intended user or user group of the proposed project.

    Captures the target user's role, an optional description, and the
    goals they want to accomplish through the proposed system.
    """

    model_config = ConfigDict(extra="forbid")

    name: DiscoveryItem
    description: DiscoveryItem | None = None
    goals: list[DiscoveryItem] = Field(default_factory=list)


class UseCase(BaseModel):
    """
    Represents an interaction between a user and the proposed system.

    Defines the actor performing the interaction, the objective they
    want to achieve, and the expected outcome of that interaction.
    """

    model_config = ConfigDict(extra="forbid")

    actor: DiscoveryItem
    objective: DiscoveryItem
    expected_outcome: DiscoveryItem


class QuestionStatus(str, Enum):
    """The resolution state of a discovery clarification question."""

    UNRESOLVED = "unresolved"
    DEFERRED = "deferred"
    RESOLVED = "resolved"


class OpenQuestion(BaseModel):
    """
    Represents a question identified during discovery.

    The blocking flag indicates whether the question must be resolved
    before Forge can consider the discovery ready for approval. Once asked,
    its id links any verbatim answer to the clarification interaction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question: NonBlankText
    blocking: StrictBool = False
    id: NonBlankText | None = None
    status: QuestionStatus = QuestionStatus.UNRESOLVED
    answer: DiscoveryItem | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        """Require a matching clarified answer for resolved questions."""
        if self.status is QuestionStatus.RESOLVED:
            if self.id is None or self.answer is None:
                raise ValueError("Resolved questions require an id and answer")
            if (
                self.answer.source is not InformationSource.CLARIFIED
                or self.answer.evidence_ref != f"clarification:{self.id}"
            ):
                raise ValueError("Question answers require matching CLARIFIED evidence")
        elif self.status is QuestionStatus.DEFERRED and self.id is None:
            raise ValueError("Deferred questions require an id")
        elif self.answer is not None:
            raise ValueError("Only resolved questions may contain an answer")
        
        return self


class ClarificationRoundRecord(BaseModel):
    """Question IDs selected during one numbered clarification round."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    round_number: StrictInt = Field(ge=1)
    question_ids: list[NonBlankText] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_question_ids(self) -> Self:
        """Keep a round's selected questions unambiguous."""
        if len(self.question_ids) != len(set(self.question_ids)):
            raise ValueError("Clarification round question ids must be unique")
        
        return self


class ProjectDiscovery(BaseModel):
    """
    Represents the evolving discovery state of a new software project.

    Preserves the user's original idea while organizing the project's
    identity, problem, users, use cases, requirements, constraints,
    assumptions, scope boundaries, and unresolved questions.

    Supports incomplete discovery sessions so information can be
    progressively collected and refined through clarification.
    """

    model_config = ConfigDict(extra="forbid")

    original_idea: NonBlankText = Field(frozen=True, strict=True)
    identity: ProjectIdentity = Field(default_factory=ProjectIdentity)
    problem: ProjectProblem | None = None
    target_users: list[ProjectTargetUser] = Field(default_factory=list)
    use_cases: list[UseCase] = Field(default_factory=list)
    functional_requirements: list[Requirement] = Field(default_factory=list)
    quality_requirements: list[Requirement] = Field(default_factory=list)
    constraints: list[DiscoveryItem] = Field(default_factory=list)
    assumptions: list[DiscoveryItem] = Field(default_factory=list)
    in_scope: list[DiscoveryItem] = Field(default_factory=list)
    out_of_scope: list[DiscoveryItem] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    clarification_rounds: StrictInt = Field(default=0, ge=0)
    clarification_history: list[ClarificationRoundRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_question_ids(self) -> Self:
        """Reject ambiguous question IDs and out-of-order round records."""
        ids = [question.id for question in self.open_questions if question.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("Question ids must be unique")
        
        rounds = [round_record.round_number for round_record in self.clarification_history]
        if rounds != sorted(set(rounds)) or any(
            number > self.clarification_rounds for number in rounds
        ):
            raise ValueError("Clarification history must have unique, ordered round numbers")
        
        return self

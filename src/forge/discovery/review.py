"""Explicit, revision-bound human review of discovery specifications."""

import json
from enum import Enum
from hashlib import sha256
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from forge.discovery.models import (
    DiscoveryItem,
    InformationSource,
    NonBlankText,
    OpenQuestion,
    QuestionStatus,
    Requirement,
)
from forge.discovery.specification import (
    DiscoverySpecification,
    SpecificationIssue,
    render_specification_markdown,
)
from forge.error.review_errors import ReviewError


class ReviewDecision(str, Enum):
    """The three decisions a developer may explicitly make about a review."""

    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


def specification_revision(specification: DiscoverySpecification) -> str:
    """Fingerprint all validated structured content, including provenance and issues."""
    validated = DiscoverySpecification.model_validate(specification.model_dump())
    canonical = json.dumps(
        validated.model_dump(
            mode="json",
            exclude={"discovery": {"clarification_rounds", "clarification_history"}},
        ),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return f"rev-{sha256(canonical.encode('utf-8')).hexdigest()}"


def _blocking_issues(specification: DiscoverySpecification) -> tuple[SpecificationIssue, ...]:
    """Block gaps, scope conflicts, and unanswered questions marked blocking.

    Optional questions and assumptions remain informational. Inferred requirements
    stay visible as proposals; explicit approval accepts the reviewed draft without
    rewriting their original provenance.
    """
    blocking_question_ids = {
        specification.item_ids[f"open_questions.{index}"]
        for index, question in enumerate(specification.discovery.open_questions)
        if question.blocking and question.status is not QuestionStatus.RESOLVED
    }
    return tuple(
        issue
        for issue in specification.issues
        if issue.kind in ("gap", "contradiction")
        or (
            issue.kind == "unresolved_question"
            and bool(blocking_question_ids.intersection(issue.related_ids))
        )
    )


class SpecificationReview(BaseModel):
    """A reviewable snapshot and the identifier of the exact content shown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    specification: DiscoverySpecification
    revision_id: NonBlankText

    @model_validator(mode="after")
    def validate_revision(self) -> Self:
        """Reject a review whose revision does not match its specification."""
        if self.revision_id != specification_revision(self.specification):
            raise ValueError("Review revision does not match the specification")
        return self

    @property
    def markdown(self) -> str:
        """Render the same structured content that the revision identifies."""
        self.validate_revision()
        return render_specification_markdown(self.specification)

    @property
    def blocking_issues(self) -> tuple[SpecificationIssue, ...]:
        """Return gaps, scope conflicts, and unanswered blocking questions."""
        self.validate_revision()
        return _blocking_issues(self.specification)

    @property
    def informational_issues(self) -> tuple[SpecificationIssue, ...]:
        """Return issues visible to reviewers that do not prevent approval."""
        blockers = {issue.id for issue in self.blocking_issues}
        return tuple(issue for issue in self.specification.issues if issue.id not in blockers)

    @property
    def unresolved_questions(self) -> tuple[OpenQuestion, ...]:
        """Expose unanswered and deferred questions, including optional ones."""
        self.validate_revision()
        return tuple(
            question
            for question in self.specification.discovery.open_questions
            if question.status is not QuestionStatus.RESOLVED
        )

    @property
    def assumptions(self) -> tuple[DiscoveryItem, ...]:
        """Expose assumptions without treating their presence as a blocker."""
        self.validate_revision()
        return tuple(self.specification.discovery.assumptions)

    @property
    def proposed_requirements(self) -> tuple[Requirement, ...]:
        """Expose AI-inferred functional and quality requirements for review."""
        self.validate_revision()
        discovery = self.specification.discovery
        return tuple(
            requirement
            for requirement in (*discovery.functional_requirements, *discovery.quality_requirements)
            if requirement.source is InformationSource.INFERRED
        )


class ReviewDecisionRecord(BaseModel):
    """One explicit decision; callers must hand the latest record to the gate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    revision_id: NonBlankText
    decision: ReviewDecision
    feedback: NonBlankText | None = None


def prepare_specification_review(specification: DiscoverySpecification) -> SpecificationReview:
    """Validate and snapshot a specification for developer review."""
    validated = DiscoverySpecification.model_validate(specification.model_dump())
    return SpecificationReview(
        specification=validated.model_dump(),
        revision_id=specification_revision(validated),
    )


def record_review_decision(
    review: SpecificationReview,
    current_specification: DiscoverySpecification,
    *,
    decision: ReviewDecision,
    feedback: str | None = None,
) -> ReviewDecisionRecord:
    """Record a trusted caller's explicit decision about the current revision.

    The caller must obtain the decision from the developer. This module cannot
    authenticate a caller or establish that a human actually saw the review.
    """
    if not isinstance(decision, ReviewDecision):
        raise ReviewError("Decision must be a ReviewDecision value")
    if not isinstance(review, SpecificationReview) or not isinstance(
        current_specification, DiscoverySpecification
    ):
        raise ReviewError("A valid review and current specification are required")
    validated_review = SpecificationReview.model_validate(review.model_dump())
    current_revision = specification_revision(current_specification)
    if validated_review.revision_id != current_revision:
        raise ReviewError("The reviewed specification is no longer current")
    if decision is ReviewDecision.APPROVE and validated_review.blocking_issues:
        raise ReviewError("Approval is blocked by unresolved specification issues")
    return ReviewDecisionRecord(
        revision_id=validated_review.revision_id,
        decision=decision,
        feedback=feedback,
    )


def can_handoff(
    specification: DiscoverySpecification, decision_record: ReviewDecisionRecord | None
) -> bool:
    """Allow handoff only for an eligible revision and its latest approval record."""
    if not isinstance(specification, DiscoverySpecification) or not isinstance(
        decision_record, ReviewDecisionRecord
    ):
        return False
    if decision_record.decision is not ReviewDecision.APPROVE:
        return False
    try:
        validated = DiscoverySpecification.model_validate(specification.model_dump())
        record = ReviewDecisionRecord.model_validate(decision_record.model_dump())
        return not _blocking_issues(validated) and record.revision_id == specification_revision(
            validated
        )
    except (ValidationError, ValueError):
        return False

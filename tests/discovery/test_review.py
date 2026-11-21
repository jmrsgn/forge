"""Focused tests for explicit, revision-bound specification review."""

import pytest
from pydantic import ValidationError

from forge.discovery.models import (
    DiscoveryItem,
    InformationSource,
    OpenQuestion,
    ProjectDiscovery,
    ProjectIdentity,
    ProjectProblem,
    ProjectTargetUser,
    QuestionStatus,
    Requirement,
    UseCase,
)
from forge.discovery.review import (
    ReviewDecision,
    ReviewDecisionRecord,
    ReviewError,
    SpecificationReview,
    can_handoff,
    prepare_specification_review,
    record_review_decision,
    specification_revision,
)
from forge.discovery.specification import build_specification


def _user(statement: str) -> DiscoveryItem:
    """Create a claim supported by the preserved original idea."""
    return DiscoveryItem(
        statement=statement, source=InformationSource.USER, evidence_ref="original_idea"
    )


def _discovery() -> ProjectDiscovery:
    """Create a complete draft with optional questions and visible proposals."""
    return ProjectDiscovery(
        original_idea="Fitness coaches manage clients and create workout programs.",
        identity=ProjectIdentity(
            name=DiscoveryItem(statement="Fitness coaching app", source=InformationSource.INFERRED),
            summary=DiscoveryItem(statement="Coaching app", source=InformationSource.INFERRED),
        ),
        problem=ProjectProblem(
            statement=DiscoveryItem(
                statement="Fitness coaches need to manage clients",
                source=InformationSource.INFERRED,
            ),
            goals=[_user("Manage clients")],
        ),
        target_users=[ProjectTargetUser(name=_user("Fitness coaches"))],
        in_scope=[_user("Create workout programs")],
        use_cases=[
            UseCase(
                actor=_user("Fitness coaches"),
                objective=_user("Create workout programs"),
                expected_outcome=DiscoveryItem(
                    statement="A program is saved", source=InformationSource.INFERRED
                ),
            )
        ],
        functional_requirements=[
            Requirement(
                statement="Create workout programs",
                source=InformationSource.USER,
                evidence_ref="original_idea",
            ),
            Requirement(statement="Send reminders", source=InformationSource.INFERRED),
        ],
        assumptions=[
            DiscoveryItem(statement="Clients use email", source=InformationSource.INFERRED)
        ],
        open_questions=[
            OpenQuestion(
                question="Should clients have accounts?",
                id="q-accounts",
                status=QuestionStatus.DEFERRED,
            )
        ],
    )


def test_explicit_approval_of_eligible_review_allows_handoff() -> None:
    specification = build_specification(_discovery())
    review = prepare_specification_review(specification)

    assert review.revision_id == specification_revision(specification)
    assert review.blocking_issues == ()
    assert len(review.informational_issues) == 1
    assert review.unresolved_questions[0].status is QuestionStatus.DEFERRED
    assert review.assumptions[0].source is InformationSource.INFERRED
    assert [item.statement for item in review.proposed_requirements] == ["Send reminders"]
    assert "Send reminders — PROPOSED" in review.markdown
    assert "Should clients have accounts?" in review.markdown

    record = record_review_decision(
        review,
        specification,
        decision=ReviewDecision.APPROVE,
        feedback="  Approved for planning.  ",
    )
    assert record.revision_id == review.revision_id
    assert record.feedback == "  Approved for planning.  "
    assert can_handoff(specification, record)
    assert ReviewDecisionRecord.model_validate_json(record.model_dump_json()) == record
    assert specification.discovery.functional_requirements[1].source is InformationSource.INFERRED


@pytest.mark.parametrize("blocker", ["gap", "question", "deferred_question", "contradiction"])
def test_approval_rejected_when_blocking_issue_exists(blocker: str) -> None:
    discovery = _discovery()
    if blocker == "gap":
        discovery.identity.name = None
    elif blocker == "question":
        discovery.open_questions.append(OpenQuestion(question="Which platform?", blocking=True))
    elif blocker == "deferred_question":
        discovery.open_questions.append(
            OpenQuestion(
                question="Which platform?",
                id="q-platform",
                blocking=True,
                status=QuestionStatus.DEFERRED,
            )
        )
    else:
        discovery.out_of_scope.append(_user("Create workout programs"))
    specification = build_specification(discovery)
    review = prepare_specification_review(specification)

    assert review.blocking_issues
    expected_kind = "unresolved_question" if "question" in blocker else blocker
    assert expected_kind in {issue.kind for issue in review.blocking_issues}
    with pytest.raises(ReviewError, match="blocked"):
        record_review_decision(review, specification, decision=ReviewDecision.APPROVE)


@pytest.mark.parametrize("decision", [ReviewDecision.REQUEST_CHANGES, ReviewDecision.REJECT])
def test_changes_and_rejection_do_not_authorize_handoff(decision: ReviewDecision) -> None:
    specification = build_specification(_discovery())
    review = prepare_specification_review(specification)
    record = record_review_decision(
        review, specification, decision=decision, feedback="Revise scope"
    )

    assert record.feedback == "Revise scope"
    assert not can_handoff(specification, record)


def test_stale_review_and_approval_cannot_authorize_changed_specification() -> None:
    discovery = _discovery()
    specification = build_specification(discovery)
    review = prepare_specification_review(specification)
    approval = record_review_decision(review, specification, decision=ReviewDecision.APPROVE)

    discovery.assumptions.append(
        DiscoveryItem(statement="Clients use mobile devices", source=InformationSource.INFERRED)
    )
    changed = build_specification(discovery)
    assert specification_revision(changed) != review.revision_id
    assert not can_handoff(changed, approval)
    with pytest.raises(ReviewError, match="no longer current"):
        record_review_decision(review, changed, decision=ReviewDecision.APPROVE)


def test_missing_or_malformed_decisions_and_reviews_are_rejected() -> None:
    specification = build_specification(_discovery())
    review = prepare_specification_review(specification)

    assert not can_handoff(specification, None)
    assert not can_handoff(specification, {"decision": "approve"})
    with pytest.raises(ReviewError, match="ReviewDecision"):
        record_review_decision(review, specification, decision="approve")
    with pytest.raises(ReviewError, match="valid review"):
        record_review_decision(None, specification, decision=ReviewDecision.APPROVE)
    with pytest.raises(ValidationError):
        record_review_decision(
            review, specification, decision=ReviewDecision.REQUEST_CHANGES, feedback="  "
        )
    with pytest.raises(ValidationError, match="revision"):
        SpecificationReview(specification=specification, revision_id="rev-invalid")
    with pytest.raises(ValidationError):
        ReviewDecisionRecord(revision_id=review.revision_id, decision="invalid")

    approval = record_review_decision(review, specification, decision=ReviewDecision.APPROVE)
    specification.item_ids.clear()
    assert not can_handoff(specification, approval)


def test_revision_is_deterministic_and_includes_provenance_and_issues() -> None:
    discovery = _discovery()
    first = build_specification(discovery)
    assert specification_revision(first) == specification_revision(build_specification(discovery))

    discovery.clarification_rounds += 1
    assert specification_revision(build_specification(discovery)) == specification_revision(first)

    discovery.functional_requirements[0] = Requirement(
        statement="Create workout programs", source=InformationSource.INFERRED
    )
    changed_provenance_revision = specification_revision(build_specification(discovery))
    assert changed_provenance_revision != specification_revision(first)

    discovery.open_questions[0] = OpenQuestion(
        question="Should clients have accounts?", id="q-accounts", blocking=True
    )
    assert specification_revision(build_specification(discovery)) != changed_provenance_revision

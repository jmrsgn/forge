"""Focused tests for structured discovery specifications."""

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
from forge.discovery.specification import (
    DiscoverySpecification,
    build_specification,
    render_specification_markdown,
)


def _item(statement: str, source: InformationSource = InformationSource.INFERRED) -> DiscoveryItem:
    """Build a claim with evidence appropriate for its source."""
    evidence = "original_idea" if source is InformationSource.USER else None
    if source is InformationSource.CLARIFIED:
        evidence = "clarification:q-1"
    return DiscoveryItem(statement=statement, source=source, evidence_ref=evidence)


def _discovery() -> ProjectDiscovery:
    """Create a small discovery with confirmed and proposed information."""
    return ProjectDiscovery(
        original_idea="I want an app where fitness coaches manage clients and create workout programs.",
        identity=ProjectIdentity(name=_item("Coach App", InformationSource.CLARIFIED)),
        problem=ProjectProblem(
            statement=_item(
                "Coaches need one place to organize clients.", InformationSource.INFERRED
            ),
            goals=[_item("Manage clients", InformationSource.USER)],
        ),
        target_users=[
            ProjectTargetUser(
                name=_item("Fitness coaches", InformationSource.USER),
                goals=[_item("Track client progress")],
            )
        ],
        in_scope=[_item("Create workout programs", InformationSource.USER)],
        out_of_scope=[_item("Process payments")],
        use_cases=[
            UseCase(
                actor=_item("Fitness coaches", InformationSource.USER),
                objective=_item("create workout programs", InformationSource.USER),
                expected_outcome=_item("Client receives a plan"),
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
        assumptions=[_item("Clients have email addresses")],
        open_questions=[
            OpenQuestion(question="Do clients need accounts?", id="q-accounts", blocking=True),
            OpenQuestion(
                question="Which payment provider?",
                id="q-payments",
                status=QuestionStatus.DEFERRED,
            ),
            OpenQuestion(
                question="What is the product name?",
                id="q-1",
                status=QuestionStatus.RESOLVED,
                answer=_item("Coach App", InformationSource.CLARIFIED),
            ),
        ],
    )


def test_build_preserves_claims_provenance_and_stable_ids() -> None:
    discovery = _discovery()
    specification = build_specification(discovery)

    assert specification.schema_version == 1
    assert specification.discovery is not discovery
    assert specification.discovery.original_idea == discovery.original_idea
    assert specification.discovery.target_users[0].name.source is InformationSource.USER
    assert specification.discovery.identity.name.evidence_ref == "clarification:q-1"
    assert specification.discovery.functional_requirements[1].source is InformationSource.INFERRED
    assert specification.item_ids["open_questions.0"] == "q-accounts"
    assert specification.item_ids == build_specification(discovery).item_ids
    assert (
        specification.item_ids["functional_requirements.0"] != specification.item_ids["in_scope.0"]
    )

    discovery.functional_requirements.append(
        Requirement(statement="Export plans", source=InformationSource.INFERRED)
    )
    assert len(specification.discovery.functional_requirements) == 2
    assert (
        build_specification(discovery).item_ids["functional_requirements.0"]
        == specification.item_ids["functional_requirements.0"]
    )
    discovery.functional_requirements.reverse()
    assert (
        build_specification(discovery).item_ids["functional_requirements.2"]
        == specification.item_ids["functional_requirements.0"]
    )
    assert (
        DiscoverySpecification.model_validate_json(specification.model_dump_json()) == specification
    )


def test_incomplete_discovery_and_known_conflict_are_reviewable() -> None:
    discovery = ProjectDiscovery(original_idea="A project idea")
    specification = build_specification(discovery)
    assert any(issue.kind == "gap" for issue in specification.issues)
    assert not discovery.in_scope

    discovery = _discovery()
    discovery.out_of_scope.append(_item("Create workout programs"))
    specification = build_specification(discovery)
    kinds = {issue.kind for issue in specification.issues}
    assert kinds == {"gap", "unresolved_question", "contradiction"}
    assert any("deferred" in issue.statement for issue in specification.issues)
    assert any("unanswered" in issue.statement for issue in specification.issues)
    conflict = next(issue for issue in specification.issues if issue.kind == "contradiction")
    assert len(conflict.related_ids) == 2
    assert set(conflict.related_ids) <= set(specification.item_ids.values())


def test_markdown_is_deterministic_and_marks_proposed_and_unresolved_items() -> None:
    specification = build_specification(_discovery())
    markdown = render_specification_markdown(specification)

    assert markdown == render_specification_markdown(specification)
    assert "# Discovery Specification (Review Draft)" in markdown
    assert "## Functional Requirements" in markdown
    assert "Send reminders — PROPOSED" in markdown
    assert "Coach App — CLARIFIED; evidence: clarification:q-1" in markdown
    assert "q-accounts" in markdown
    assert "## Gaps and Unresolved Issues" in markdown
    assert specification.item_ids["functional_requirements.1"] in markdown

    discovery = ProjectDiscovery(original_idea="A ``` idea", in_scope=[_item("# external heading")])
    rendered = render_specification_markdown(build_specification(discovery))
    assert "\\# external heading" in rendered
    assert "````\nA ``` idea\n````" in rendered


def test_rejects_malformed_or_inconsistent_specification() -> None:
    specification = build_specification(_discovery())
    data = specification.model_dump()
    with pytest.raises(ValidationError):
        DiscoverySpecification.model_validate({**data, "schema_version": 2})
    with pytest.raises(ValidationError):
        DiscoverySpecification.model_validate({**data, "item_ids": {}})
    with pytest.raises(ValidationError):
        DiscoverySpecification.model_validate({**data, "issues": []})
    with pytest.raises(ValidationError):
        DiscoverySpecification.model_validate({**data, "unexpected": True})

    data["discovery"]["functional_requirements"][0]["evidence_ref"] = None
    with pytest.raises(ValidationError):
        DiscoverySpecification.model_validate(data)

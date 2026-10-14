import pytest
from pydantic import ValidationError

from forge.discovery import (
    DiscoveryItem,
    InformationSource,
    OpenQuestion,
    ProjectDiscovery,
    ProjectIdentity,
    ProjectProblem,
    ProjectTargetUser,
    Requirement,
    UseCase,
)


def test_partial_discovery_preserves_original_idea() -> None:
    idea = "  Build an app for local gardeners.  "
    discovery = ProjectDiscovery(original_idea=idea)

    assert discovery.original_idea == idea
    assert discovery.identity == ProjectIdentity()
    assert discovery.problem is None
    assert discovery.target_users == []
    assert discovery.use_cases == []
    assert discovery.functional_requirements == []
    assert discovery.quality_requirements == []
    assert discovery.constraints == []
    assert discovery.assumptions == []
    assert discovery.out_of_scope == []
    assert discovery.open_questions == []


def test_collections_are_independent_between_discoveries() -> None:
    first = ProjectDiscovery(original_idea="First")
    second = ProjectDiscovery(original_idea="Second")

    first.constraints.append(
        DiscoveryItem(
            statement="Offline access",
            source=InformationSource.USER,
            evidence_ref="original_idea",
        )
    )

    assert second.constraints == []


def test_original_idea_cannot_be_reassigned() -> None:
    discovery = ProjectDiscovery(original_idea="First idea")

    with pytest.raises(ValidationError):
        discovery.original_idea = "Revised idea"

    assert discovery.original_idea == "First idea"


def test_original_idea_is_required() -> None:
    with pytest.raises(ValidationError, match="original_idea"):
        ProjectDiscovery()


def test_populated_discovery_tracks_provenance_and_blocking_questions() -> None:
    discovery = ProjectDiscovery(
        original_idea="A gardening app",
        identity=ProjectIdentity(
            name=DiscoveryItem(statement="Garden", source=InformationSource.INFERRED),
            summary=DiscoveryItem(statement="Garden planning", source=InformationSource.INFERRED),
        ),
        problem=ProjectProblem(
            statement=DiscoveryItem(
                statement="Gardeners lose track of planting dates",
                source=InformationSource.INFERRED,
            ),
            goals=[
                DiscoveryItem(
                    statement="Plan planting",
                    source=InformationSource.CLARIFIED,
                    evidence_ref="clarification:goal-1",
                )
            ],
        ),
        target_users=[
            ProjectTargetUser(
                name=DiscoveryItem(
                    statement="Gardener",
                    source=InformationSource.USER,
                    evidence_ref="original_idea",
                ),
                description=DiscoveryItem(
                    statement="Plans a home garden", source=InformationSource.INFERRED
                ),
                goals=[
                    DiscoveryItem(
                        statement="Track seeds",
                        source=InformationSource.CLARIFIED,
                        evidence_ref="clarification:goal-2",
                    )
                ],
            )
        ],
        use_cases=[
            UseCase(
                actor=DiscoveryItem(
                    statement="Gardener",
                    source=InformationSource.USER,
                    evidence_ref="original_idea",
                ),
                objective=DiscoveryItem(
                    statement="Record planting date", source=InformationSource.INFERRED
                ),
                expected_outcome=DiscoveryItem(
                    statement="A saved planting record",
                    source=InformationSource.CLARIFIED,
                    evidence_ref="clarification:outcome-1",
                ),
            )
        ],
        functional_requirements=[
            Requirement(
                statement="Save planting dates",
                source=InformationSource.USER,
                evidence_ref="original_idea",
            )
        ],
        quality_requirements=[
            Requirement(statement="Work offline", source=InformationSource.INFERRED)
        ],
        constraints=[
            DiscoveryItem(
                statement="Mobile first",
                source=InformationSource.CLARIFIED,
                evidence_ref="clarification:constraint-1",
            )
        ],
        assumptions=[DiscoveryItem(statement="One user per garden", source=InformationSource.INFERRED)],
        out_of_scope=[
            DiscoveryItem(
                statement="Seed ordering",
                source=InformationSource.USER,
                evidence_ref="original_idea",
            )
        ],
        open_questions=[OpenQuestion(question="Is sharing needed?", blocking=True)],
    )

    assert discovery.functional_requirements[0].source is InformationSource.USER
    assert discovery.functional_requirements[0].evidence_ref == "original_idea"
    assert discovery.quality_requirements[0].source is InformationSource.INFERRED
    assert discovery.identity.name.source is InformationSource.INFERRED
    assert discovery.problem.statement.source is InformationSource.INFERRED
    assert discovery.target_users[0].name.source is InformationSource.USER
    assert discovery.target_users[0].description.source is InformationSource.INFERRED
    assert discovery.target_users[0].goals[0].source is InformationSource.CLARIFIED
    assert discovery.use_cases[0].expected_outcome.evidence_ref == "clarification:outcome-1"
    assert discovery.open_questions[0].blocking is True
    assert OpenQuestion(question="Which platform?").blocking is False
    assert isinstance(discovery.functional_requirements[0], DiscoveryItem)

    restored = ProjectDiscovery.model_validate_json(discovery.model_dump_json())
    assert restored == discovery


@pytest.mark.parametrize(
    ("model", "values"),
    [
        (ProjectDiscovery, {"original_idea": " \t "}),
        (
            DiscoveryItem,
            {"statement": "  ", "source": InformationSource.USER, "evidence_ref": "original_idea"},
        ),
        (
            Requirement,
            {"statement": "\n", "source": InformationSource.USER, "evidence_ref": "original_idea"},
        ),
        (ProjectProblem, {"statement": {"statement": "  ", "source": "inferred"}}),
        (OpenQuestion, {"question": "  "}),
        (
            UseCase,
            {
                "actor": {"statement": " ", "source": "inferred"},
                "objective": {"statement": "Plan", "source": "inferred"},
                "expected_outcome": {"statement": "Saved", "source": "inferred"},
            },
        ),
    ],
)
def test_blank_text_is_rejected(model: type, values: dict) -> None:
    with pytest.raises(ValidationError):
        model(**values)


def test_invalid_information_source_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DiscoveryItem(statement="Save planting dates", source="unknown")


@pytest.mark.parametrize(
    ("source", "evidence_ref"),
    [
        (InformationSource.USER, "original_idea"),
        (InformationSource.CLARIFIED, "clarification:answer-1"),
        (InformationSource.INFERRED, None),
    ],
)
def test_valid_evidence_references(source: InformationSource, evidence_ref: str | None) -> None:
    statement = "  Save planting dates  "

    item = DiscoveryItem(statement=statement, source=source, evidence_ref=evidence_ref)

    assert item.statement == statement
    assert item.source is source
    assert item.evidence_ref == evidence_ref


@pytest.mark.parametrize(
    ("source", "evidence_ref"),
    [
        (InformationSource.USER, None),
        (InformationSource.USER, "clarification:answer-1"),
        (InformationSource.USER, "original_idea:0-10"),
        (InformationSource.USER, " "),
        (InformationSource.CLARIFIED, None),
        (InformationSource.CLARIFIED, "original_idea"),
        (InformationSource.CLARIFIED, "clarification:"),
        (InformationSource.CLARIFIED, "clarification:   "),
        (InformationSource.CLARIFIED, " "),
        (InformationSource.INFERRED, "original_idea"),
        (InformationSource.INFERRED, "clarification:answer-1"),
        (InformationSource.INFERRED, " "),
    ],
)
def test_invalid_evidence_references_are_rejected(
    source: InformationSource, evidence_ref: str | None
) -> None:
    with pytest.raises(ValidationError):
        DiscoveryItem(statement="Save planting dates", source=source, evidence_ref=evidence_ref)


def test_nested_claims_require_discovery_items() -> None:
    with pytest.raises(ValidationError):
        ProjectIdentity(name="Garden")

    with pytest.raises(ValidationError):
        ProjectProblem(statement="Gardeners need a plan")

    with pytest.raises(ValidationError):
        ProjectTargetUser(name="Gardener")

    with pytest.raises(ValidationError):
        UseCase(actor="Gardener", objective="Plan", expected_outcome="Saved")

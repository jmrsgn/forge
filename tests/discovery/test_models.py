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

    first.constraints.append(DiscoveryItem(statement="Offline access", source=InformationSource.USER))

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
        identity=ProjectIdentity(name="Garden", summary="Garden planning"),
        problem=ProjectProblem(
            statement="Gardeners lose track of planting dates",
            goals=[DiscoveryItem(statement="Plan planting", source=InformationSource.CLARIFIED)],
        ),
        users=[
            ProjectTargetUser(
                name="Gardener",
                description="Plans a home garden",
                goals=[DiscoveryItem(statement="Track seeds", source=InformationSource.USER)],
            )
        ],
        use_cases=[
            UseCase(
                actor="Gardener",
                objective="Record planting date",
                expected_outcome="A saved planting record",
            )
        ],
        functional_requirements=[
            Requirement(statement="Save planting dates", source=InformationSource.USER)
        ],
        quality_requirements=[
            Requirement(statement="Work offline", source=InformationSource.INFERRED)
        ],
        constraints=[DiscoveryItem(statement="Mobile first", source=InformationSource.CLARIFIED)],
        assumptions=[DiscoveryItem(statement="One user per garden", source=InformationSource.INFERRED)],
        out_of_scope=[DiscoveryItem(statement="Seed ordering", source=InformationSource.USER)],
        open_questions=[OpenQuestion(question="Is sharing needed?", blocking=True)],
    )

    assert discovery.functional_requirements[0].source is InformationSource.USER
    assert discovery.quality_requirements[0].source is InformationSource.INFERRED
    assert discovery.open_questions[0].blocking is True
    assert OpenQuestion(question="Which platform?").blocking is False
    assert isinstance(discovery.functional_requirements[0], DiscoveryItem)

    restored = ProjectDiscovery.model_validate_json(discovery.model_dump_json())
    assert restored == discovery


@pytest.mark.parametrize(
    ("model", "values"),
    [
        (ProjectDiscovery, {"original_idea": " \t "}),
        (DiscoveryItem, {"statement": "  ", "source": InformationSource.USER}),
        (Requirement, {"statement": "\n", "source": InformationSource.USER}),
        (ProjectProblem, {"statement": "  "}),
        (OpenQuestion, {"question": "  "}),
        (UseCase, {"actor": " ", "objective": "Plan", "expected_outcome": "Saved"}),
    ],
)
def test_blank_text_is_rejected(model: type, values: dict) -> None:
    with pytest.raises(ValidationError):
        model(**values)


def test_invalid_information_source_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DiscoveryItem(statement="Save planting dates", source="unknown")

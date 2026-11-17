import pytest
from pydantic import ValidationError

from forge.discovery.intake import intake_idea
from forge.discovery.models import OpenQuestion, ProjectDiscovery, ProjectIdentity


def test_intake_preserves_original_idea_and_discovery_defaults() -> None:
    idea = (
        "I want to build a fitness application where coaches "
        "can manage clients and track their progress."
    )

    discovery = intake_idea(idea)

    assert isinstance(discovery, ProjectDiscovery)
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


def test_intake_preserves_multiline_unicode_and_whitespace() -> None:
    idea = "  Build a Café app!\nCoaches track 💪 progress—daily.\n\t"

    assert intake_idea(idea).original_idea == idea


@pytest.mark.parametrize("idea", ["", " \t\n "])
def test_intake_rejects_blank_idea(idea: str) -> None:
    with pytest.raises(ValidationError, match="original_idea"):
        intake_idea(idea)


@pytest.mark.parametrize("idea", [None, 42, b"Build an app", ["Build an app"]])
def test_intake_rejects_non_text_input(idea: object) -> None:
    with pytest.raises(ValidationError, match="original_idea"):
        intake_idea(idea)


def test_intake_records_are_independent() -> None:
    first = intake_idea("First idea")
    second = intake_idea("Second idea")

    first.open_questions.append(OpenQuestion(question="Which platform?"))

    assert second.original_idea == "Second idea"
    assert second.open_questions == []
    assert first.identity is not second.identity

import pytest
from pydantic import ValidationError

from forge.discovery.intake import intake_idea
from forge.discovery.models import ProjectDiscovery, ProjectIdentity


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


def test_intake_preserves_surrounding_whitespace() -> None:
    idea = "  Build a fitness application.\n"

    assert intake_idea(idea).original_idea == idea


@pytest.mark.parametrize("idea", ["", " \t\n "])
def test_intake_rejects_blank_idea(idea: str) -> None:
    with pytest.raises(ValidationError, match="original_idea"):
        intake_idea(idea)

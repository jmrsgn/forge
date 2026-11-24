"""Tests for validated, unconfirmed requirements extraction."""

import json

import pytest

from forge.ai import FakeProvider, GenerationRequest
from forge.discovery.analysis import RequirementsAnalysisError, analyze_project_requirements
from forge.discovery.intake import intake_idea
from forge.discovery.models import DiscoveryItem, InformationSource, Requirement
from forge.error.provider_errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderExecutionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


def _response(**changes: object) -> str:
    data: dict[str, object] = {
        "project_name": None,
        "project_summary": None,
        "problem_statement": None,
        "goals": [],
        "target_users": [],
        "use_cases": [],
        "functional_requirements": [],
        "quality_requirements": [],
        "constraints": [],
        "assumptions": [],
        "out_of_scope": [],
        "open_questions": ["Which platform should be supported?"],
    }
    data.update(changes)
    return json.dumps(data)


class RecordingProvider(FakeProvider):
    def generate_text_response(self, request: GenerationRequest):
        self.request = request
        return super().generate_text_response(request)


def test_analysis_maps_candidates_and_preserves_existing_claims() -> None:
    idea = (
        "I want an application where fitness coaches can manage clients and create workout "
        "programs. It must work offline."
    )
    original = intake_idea(idea)
    original.functional_requirements.append(
        Requirement(
            statement="Create workout programs",
            source=InformationSource.USER,
            evidence_ref="original_idea",
        )
    )
    original.constraints.append(
        DiscoveryItem(
            statement="No subscription",
            source=InformationSource.CLARIFIED,
            evidence_ref="clarification:pricing-1",
        )
    )
    before = original.model_dump()
    provider = RecordingProvider(
        _response(
            project_name="Coach Workspace",
            project_summary="A workspace for fitness coaches",
            problem_statement="Coaches need a way to organize client training",
            goals=["Organize client training"],
            target_users=[
                {
                    "name": "fitness coaches",
                    "description": "Coaches who manage clients",
                    "goals": ["Plan client workouts"],
                }
            ],
            use_cases=[
                {
                    "actor": "fitness coach",
                    "objective": "Create a workout program",
                    "expected_outcome": "A saved program for a client",
                }
            ],
            functional_requirements=["Manage clients"],
            quality_requirements=["Offline access"],
            constraints=["Work offline"],
            assumptions=["Clients may need accounts"],
            out_of_scope=["Payments"],
            open_questions=["Should clients have their own accounts?"],
        )
    )

    result = analyze_project_requirements(original, provider)

    assert provider.request.prompt.endswith(idea)
    assert result is not original
    assert original.model_dump() == before
    assert result.original_idea == idea
    assert result.identity.name.statement == "Coach Workspace"
    assert result.identity.summary.statement == "A workspace for fitness coaches"
    assert result.problem.statement.statement == "Coaches need a way to organize client training"
    assert result.problem.goals[0].statement == "Organize client training"
    assert result.target_users[0].name.statement == "fitness coaches"
    assert result.target_users[0].description.statement == "Coaches who manage clients"
    assert result.target_users[0].goals[0].statement == "Plan client workouts"
    assert result.use_cases[0].objective.statement == "Create a workout program"
    assert result.use_cases[0].expected_outcome.statement == "A saved program for a client"
    assert result.functional_requirements[0].source is InformationSource.USER
    assert result.functional_requirements[1].statement == "Manage clients"
    assert result.quality_requirements[0].statement == "Offline access"
    assert result.constraints[0].source is InformationSource.CLARIFIED
    assert result.constraints[0].evidence_ref == "clarification:pricing-1"
    assert result.constraints[1].statement == "Work offline"
    assert result.assumptions[0].statement == "Clients may need accounts"
    assert result.out_of_scope[0].statement == "Payments"
    assert result.open_questions[0].question == "Should clients have their own accounts?"
    assert result.open_questions[0].blocking is False
    assert all(
        item.source is InformationSource.INFERRED and item.evidence_ref is None
        for item in (
            result.identity.name,
            result.identity.summary,
            result.problem.statement,
            *result.problem.goals,
            result.target_users[0].name,
            result.target_users[0].description,
            *result.target_users[0].goals,
            result.use_cases[0].actor,
            result.use_cases[0].objective,
            result.use_cases[0].expected_outcome,
            *result.functional_requirements[1:],
            *result.quality_requirements,
            *result.constraints[1:],
            *result.assumptions,
            *result.out_of_scope,
        )
    )


def test_existing_identity_is_not_overwritten() -> None:
    original = intake_idea("Build a coaching app.")
    original.identity.name = DiscoveryItem(
        statement="Coach App", source=InformationSource.USER, evidence_ref="original_idea"
    )

    result = analyze_project_requirements(original, FakeProvider(_response(project_name="AI Name")))

    assert result.identity.name == original.identity.name
    assert result.identity.name.source is InformationSource.USER
    assert result.open_questions[0].question == "Which platform should be supported?"
    assert original.open_questions == []


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        _response(functional_requirements=[{"statement": "Manage clients", "source": "user"}]),
        _response(target_users=[{"name": "Coaches", "source": "clarified"}]),
        _response(functional_requirements=[42]),
        _response(unexpected="sensitive-provider-output"),
    ],
)
def test_invalid_analysis_is_rejected_without_mutation(response: str) -> None:
    original = intake_idea("Build a coaching app.")
    before = original.model_dump()

    with pytest.raises(RequirementsAnalysisError) as caught:
        analyze_project_requirements(original, FakeProvider(response))

    assert "Build a coaching app." not in str(caught.value)
    assert "sensitive-provider-output" not in str(caught.value)
    assert original.model_dump() == before


def test_missing_section_is_named_without_leaking_response() -> None:
    data = json.loads(_response())
    del data["goals"]
    data["unexpected"] = "sensitive-provider-output"

    with pytest.raises(RequirementsAnalysisError, match="goals") as caught:
        analyze_project_requirements(
            intake_idea("Build a coaching app."), FakeProvider(json.dumps(data))
        )

    assert "sensitive-provider-output" not in str(caught.value)


def test_empty_analysis_is_rejected() -> None:
    with pytest.raises(RequirementsAnalysisError, match="no findings or questions"):
        analyze_project_requirements(
            intake_idea("Build a coaching app."), FakeProvider(_response(open_questions=[]))
        )


@pytest.mark.parametrize(
    "error",
    [
        ProviderConfigurationError("secret-key in configuration"),
        ProviderAuthenticationError("secret-key in authentication"),
        ProviderTimeoutError("private project idea in timeout"),
        ProviderRateLimitError("private project idea in rate limit"),
        ProviderExecutionError("secret-key in provider failure"),
    ],
)
def test_provider_error_types_are_preserved_without_sensitive_messages(error: Exception) -> None:
    class FailingProvider:
        def generate_text_response(self, request: GenerationRequest):
            raise error

    with pytest.raises(type(error)) as caught:
        analyze_project_requirements(intake_idea("Build a coaching app."), FailingProvider())

    assert "secret-key" not in str(caught.value)
    assert "private project idea" not in str(caught.value)


def test_unexpected_provider_error_is_sanitized() -> None:
    class FailingProvider:
        def generate_text_response(self, request: GenerationRequest):
            raise RuntimeError("private project idea and secret-key")

    with pytest.raises(ProviderExecutionError) as caught:
        analyze_project_requirements(intake_idea("Build a coaching app."), FailingProvider())

    assert "private project idea" not in str(caught.value)
    assert "secret-key" not in str(caught.value)

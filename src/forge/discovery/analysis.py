"""AI-assisted extraction of unconfirmed requirements from an original idea."""

import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from forge.ai.contracts import AIProvider, TextGenerationRequest, TextGenerationResponse
from forge.discovery.models import (
    DiscoveryItem,
    InformationSource,
    NonBlankText,
    OpenQuestion,
    ProjectDiscovery,
    ProjectProblem,
    ProjectTargetUser,
    UseCase,
)
from forge.error.analysis_errors import RequirementsAnalysisError
from forge.error.provider_errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderExecutionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


class _TargetUserCandidate(BaseModel):
    """Untrusted target-user fields before provenance is assigned."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: NonBlankText
    description: NonBlankText | None = None
    goals: list[NonBlankText] = Field(default_factory=list)


class _UseCaseCandidate(BaseModel):
    """Untrusted use-case fields before provenance is assigned."""

    model_config = ConfigDict(extra="forbid", strict=True)

    actor: NonBlankText
    objective: NonBlankText
    expected_outcome: NonBlankText


class _AnalysisResponse(BaseModel):
    """Untrusted provider text, without provenance or approval fields."""

    model_config = ConfigDict(extra="forbid", strict=True)

    project_name: NonBlankText | None = None
    project_summary: NonBlankText | None = None
    problem_statement: NonBlankText | None = None
    goals: list[NonBlankText]
    target_users: list[_TargetUserCandidate]
    use_cases: list[_UseCaseCandidate]
    functional_requirements: list[NonBlankText]
    quality_requirements: list[NonBlankText]
    constraints: list[NonBlankText]
    assumptions: list[NonBlankText]
    out_of_scope: list[NonBlankText]
    open_questions: list[NonBlankText]


def _generate_prompt(original_idea: str) -> str:
    """Ask for the required JSON sections using the untouched original idea.

    Example response for a fitness coaching idea::

        {
          "project_name": null,
          "project_summary": null,
          "problem_statement": null,
          "goals": [],
          "target_users": [{"name": "fitness coaches", "description": null, "goals": []}],
          "use_cases": [],
          "functional_requirements": ["Manage clients", "Create workout programs"],
          "quality_requirements": [],
          "constraints": [],
          "assumptions": [],
          "out_of_scope": [],
          "open_questions": ["Should clients have accounts?"]
        }

    The response contains candidate information; Forge assigns provenance after validation.
    """

    return (
        "Analyze the developer's new project idea. Extract only information supported by the "
        "idea. Treat interpretations as candidates and put uncertain claims in assumptions or "
        "open_questions. Do not invent technologies, architecture, or detailed business rules. "
        "Return only a JSON object, without Markdown, with these fields:\n"
        '{"project_name": null, "project_summary": null, "problem_statement": null, '
        '"goals": [], "target_users": [{"name": "...", "description": null, "goals": []}], '
        '"use_cases": [{"actor": "...", "objective": "...", "expected_outcome": "..."}], '
        '"functional_requirements": [], "quality_requirements": [], "constraints": [], '
        '"assumptions": [], "out_of_scope": [], "open_questions": []}\n'
        "Every list field is required; use [] when unknown. Use null for unknown scalar fields. "
        "Do not include source, evidence_ref, or approval fields. Only include use cases when "
        "actor, objective, and expected outcome are known; otherwise ask a question.\n"
        f"Original idea (verbatim):\n{original_idea}"
    )


def _parse_response(response: TextGenerationResponse) -> _AnalysisResponse:
    """Validate provider JSON without exposing its contents in errors."""

    try:
        data = json.loads(response.text)
    except (TypeError, ValueError):
        raise RequirementsAnalysisError("Provider returned malformed analysis JSON") from None

    try:
        analysis = _AnalysisResponse.model_validate(data)
    except ValidationError as exc:
        missing = sorted(
            str(error["loc"][0])
            for error in exc.errors(include_input=False, include_context=False)
            if error["type"] == "missing" and len(error["loc"]) == 1
        )

        if missing:
            raise RequirementsAnalysisError(
                f"Provider analysis omitted required sections: {', '.join(missing)}"
            ) from None
        raise RequirementsAnalysisError("Provider returned an invalid analysis structure") from None
    if not any(analysis.model_dump().values()):
        raise RequirementsAnalysisError("Provider analysis contained no findings or questions")

    return analysis


def _create_inferred_item(statement: str) -> DiscoveryItem:
    """Wrap one AI-produced statement as an unconfirmed discovery item."""

    return DiscoveryItem(statement=statement, source=InformationSource.INFERRED)


def analyze_project_requirements(
    discovery: ProjectDiscovery, provider: AIProvider
) -> ProjectDiscovery:
    """Return a separate discovery with validated, unconfirmed AI candidates."""

    request = TextGenerationRequest(prompt=_generate_prompt(discovery.original_idea))

    try:
        response = provider.generate_text_response(request)
    except ProviderError as exc:
        error_type = type(exc)
        if error_type not in (
            ProviderAuthenticationError,
            ProviderConfigurationError,
            ProviderTimeoutError,
            ProviderRateLimitError,
            ProviderExecutionError,
        ):
            error_type = ProviderExecutionError
        raise error_type("AI provider failed during requirements analysis") from None
    except Exception:  # noqa: BLE001 - injected providers can raise sensitive errors
        raise ProviderExecutionError("AI provider failed during requirements analysis") from None

    if not isinstance(response, TextGenerationResponse):
        raise RequirementsAnalysisError("Provider returned an invalid generation response")

    analysis = _parse_response(response)
    updated_discovery = discovery.model_copy(deep=True)

    # Check identity name
    if updated_discovery.identity.name is None and analysis.project_name is not None:
        updated_discovery.identity.name = _create_inferred_item(analysis.project_name)

    # Check identity summary
    if updated_discovery.identity.summary is None and analysis.project_summary is not None:
        updated_discovery.identity.summary = _create_inferred_item(analysis.project_summary)

    # Check problem statement and goals
    if analysis.problem_statement is not None or analysis.goals:
        if updated_discovery.problem is None:
            updated_discovery.problem = ProjectProblem()

        if updated_discovery.problem.statement is None and analysis.problem_statement is not None:
            updated_discovery.problem.statement = _create_inferred_item(analysis.problem_statement)

        updated_discovery.problem.goals.extend(
            _create_inferred_item(goal) for goal in analysis.goals
        )

    # Extend target users from analysis
    updated_discovery.target_users.extend(
        ProjectTargetUser(
            name=_create_inferred_item(user.name),
            description=(
                _create_inferred_item(user.description) if user.description is not None else None
            ),
            goals=[_create_inferred_item(goal) for goal in user.goals],
        )
        for user in analysis.target_users
    )

    # Extend use cases from analysis
    updated_discovery.use_cases.extend(
        UseCase(
            actor=_create_inferred_item(use_case.actor),
            objective=_create_inferred_item(use_case.objective),
            expected_outcome=_create_inferred_item(use_case.expected_outcome),
        )
        for use_case in analysis.use_cases
    )

    # Extend functional requirements from analysis
    updated_discovery.functional_requirements.extend(
        _create_inferred_item(statement) for statement in analysis.functional_requirements
    )

    # Extend quality requirements from analysis
    updated_discovery.quality_requirements.extend(
        _create_inferred_item(statement) for statement in analysis.quality_requirements
    )

    # Extend constraints from analysis
    updated_discovery.constraints.extend(
        _create_inferred_item(statement) for statement in analysis.constraints
    )

    # Extend assumptions from analysis
    updated_discovery.assumptions.extend(
        _create_inferred_item(statement) for statement in analysis.assumptions
    )

    # Extend out-of-scope items from analysis
    updated_discovery.out_of_scope.extend(
        _create_inferred_item(statement) for statement in analysis.out_of_scope
    )

    # Extend open questions from analysis
    updated_discovery.open_questions.extend(
        OpenQuestion(question=question) for question in analysis.open_questions
    )

    return updated_discovery

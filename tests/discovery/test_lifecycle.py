"""End-to-end validation of the V0.2 greenfield discovery lifecycle."""

import json
from pathlib import Path

import pytest

from forge.ai import FakeProvider
from forge.discovery.analysis import RequirementsAnalysisError, analyze_requirements
from forge.discovery.clarification import (
    ClarificationAnswer,
    record_developer_answers,
    select_clarification_round,
)
from forge.discovery.intake import intake_idea
from forge.discovery.models import DiscoveryItem, InformationSource, QuestionStatus
from forge.discovery.persistence import create_discovery, load_discovery, save_discovery
from forge.discovery.review import (
    ReviewDecision,
    ReviewError,
    can_handoff,
    prepare_specification_review,
    record_review_decision,
    specification_revision,
)
from forge.discovery.specification import build_specification, render_specification_markdown
from forge.initialization import InitializationMode, initialize_project

IDEA = (
    "I want to build a fitness coaching application where coaches can manage clients, "
    "create training programs, and track progress."
)


def _analysis_json() -> str:
    """Return deterministic, provenance-free candidate data from the fake provider."""
    return json.dumps(
        {
            "project_name": "Fitness Coaching App",
            "project_summary": "A workspace for coaches to manage clients and training",
            "problem_statement": "Coaches need to coordinate client training",
            "goals": ["Manage clients", "Create training programs", "Track progress"],
            "target_users": [{"name": "coaches", "description": None, "goals": []}],
            "use_cases": [
                {
                    "actor": "coaches",
                    "objective": "Create training programs",
                    "expected_outcome": "A training program is available for a client",
                }
            ],
            "functional_requirements": [
                "Manage clients",
                "Create training programs",
                "Track progress",
            ],
            "quality_requirements": [],
            "constraints": [],
            "assumptions": [],
            "out_of_scope": [],
            "open_questions": ["Should clients have their own accounts?"],
        }
    )


def test_greenfield_discovery_reloads_with_explicit_approved_handoff(tmp_path: Path) -> None:
    initialization = initialize_project(tmp_path, InitializationMode.GREENFIELD, "Fitness App")
    assert initialization.workspace_dir == tmp_path / ".forge"

    initial = intake_idea(IDEA)
    assert initial.original_idea == IDEA
    assert initial.functional_requirements == []
    state = create_discovery(tmp_path, initial)
    assert not can_handoff(state.specification, state.current_decision)

    analyzed = analyze_requirements(state.discovery, FakeProvider(_analysis_json()))
    assert analyzed.original_idea == IDEA
    assert all(
        item.source is InformationSource.INFERRED for item in analyzed.functional_requirements
    )
    state = save_discovery(tmp_path, state.with_discovery(analyzed))

    selected = select_clarification_round(state.discovery, max_questions=5)
    assert len(selected.questions) == 5
    assert sum(question.blocking for question in selected.questions) == 4
    blocked_specification = build_specification(selected.discovery)
    blocked_review = prepare_specification_review(blocked_specification)
    assert blocked_review.blocking_issues
    with pytest.raises(ReviewError, match="blocked"):
        record_review_decision(
            blocked_review, blocked_specification, decision=ReviewDecision.APPROVE
        )

    developer_answers = {
        "Are these intended users: coaches?": "Yes, coaches are the intended users.",
        "Is this a required capability: Manage clients?": "Yes, coaches must manage clients.",
        "Is this a required capability: Create training programs?": (
            "Yes, creating training programs is required."
        ),
        "Is this a required capability: Track progress?": "Yes, tracking progress is required.",
        "Should clients have their own accounts?": None,
    }
    clarified = record_developer_answers(
        selected.discovery,
        [
            ClarificationAnswer(
                question_id=question.id, answer=developer_answers[question.question]
            )
            for question in selected.questions
        ],
    )
    # The idea directly states this scope item; AI candidates remain INFERRED.
    clarified.in_scope.append(
        DiscoveryItem(
            statement="manage clients",
            source=InformationSource.USER,
            evidence_ref="original_idea",
        )
    )
    state = save_discovery(tmp_path, state.with_discovery(clarified))

    specification = build_specification(state.discovery)
    assert specification == state.specification
    assert specification.discovery.identity.name is not None
    assert specification.discovery.problem is not None
    assert specification.discovery.problem.goals
    assert specification.discovery.target_users
    assert specification.discovery.use_cases
    assert specification.discovery.functional_requirements
    assert specification.discovery.in_scope[0].source is InformationSource.USER
    assert all(
        requirement.source is InformationSource.INFERRED
        for requirement in specification.discovery.functional_requirements
    )
    assert all(
        question.answer is not None
        and question.answer.source is InformationSource.CLARIFIED
        and question.answer.evidence_ref == f"clarification:{question.id}"
        for question in specification.discovery.open_questions
        if question.status is QuestionStatus.RESOLVED
    )
    markdown = render_specification_markdown(specification)
    assert "## Functional Requirements" in markdown
    assert "## Gaps and Unresolved Issues" in markdown
    assert "PROPOSED" in markdown
    assert "CLARIFIED" in markdown
    assert "USER" in markdown

    review = prepare_specification_review(specification)
    assert review.markdown == markdown
    assert review.blocking_issues == ()
    assert len(review.proposed_requirements) == 3
    assert review.unresolved_questions[0].status is QuestionStatus.DEFERRED
    assert not can_handoff(specification, state.current_decision)
    approval = record_review_decision(
        review, specification, decision=ReviewDecision.APPROVE, feedback="Approved for planning"
    )
    state = save_discovery(tmp_path, state.with_decision(approval))

    restored = load_discovery(tmp_path)
    assert restored.discovery.original_idea == IDEA
    assert restored.discovery == state.discovery
    assert restored.specification_revision == review.revision_id
    assert specification_revision(restored.specification) == review.revision_id
    assert restored.current_decision == approval
    assert can_handoff(restored.specification, restored.current_decision)


def test_invalid_ai_analysis_does_not_change_saved_discovery(tmp_path: Path) -> None:
    initialize_project(tmp_path, InitializationMode.GREENFIELD, "Fitness App")
    state = create_discovery(tmp_path, intake_idea(IDEA))
    path = tmp_path / ".forge" / "discovery.json"
    previous_bytes = path.read_bytes()

    with pytest.raises(RequirementsAnalysisError, match="malformed"):
        analyze_requirements(state.discovery, FakeProvider("not JSON"))

    assert path.read_bytes() == previous_bytes
    assert load_discovery(tmp_path) == state

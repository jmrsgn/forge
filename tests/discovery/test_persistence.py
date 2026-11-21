"""Focused tests for safe discovery state persistence."""

import json
from pathlib import Path

import pytest

from forge.configuration import ProjectConfig
from forge.discovery.clarification import (
    ClarificationAnswer,
    record_developer_answers,
    select_clarification_round,
)
from forge.discovery.intake import intake_idea
from forge.discovery.models import (
    DiscoveryItem,
    InformationSource,
    ProjectDiscovery,
    ProjectIdentity,
    ProjectProblem,
    ProjectTargetUser,
    Requirement,
    UseCase,
)
from forge.discovery.persistence import (
    DiscoveryPersistenceError,
    create_discovery,
    load_discovery,
    save_discovery,
)
from forge.discovery.review import (
    ReviewDecision,
    can_handoff,
    prepare_specification_review,
    record_review_decision,
    specification_revision,
)
from forge.discovery.state import new_discovery_state
from forge.workspace import create_workspace


def _workspace(project_dir: Path) -> None:
    """Initialize the existing Forge workspace structure for storage tests."""
    create_workspace(project_dir, ProjectConfig(schema_version=1, name="Fitness App"))


def _user(statement: str) -> DiscoveryItem:
    """Build a user-provided claim for a complete reviewable discovery."""
    return DiscoveryItem(
        statement=statement, source=InformationSource.USER, evidence_ref="original_idea"
    )


def _complete_discovery() -> ProjectDiscovery:
    """Supply the required specification fields without unresolved blockers."""
    return ProjectDiscovery(
        original_idea="Fitness coaches manage clients and create workout programs.",
        identity=ProjectIdentity(name=_user("Fitness app"), summary=_user("Coach workspace")),
        problem=ProjectProblem(
            statement=_user("Coaches need to manage clients"), goals=[_user("Manage clients")]
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
            )
        ],
    )


def test_round_trip_preserves_provenance_clarification_and_revision(tmp_path: Path) -> None:
    _workspace(tmp_path)
    idea = "Fitness coaches manage clients.\nKeep their wording — exactly."
    selected = select_clarification_round(intake_idea(idea), max_questions=1)
    discovery = record_developer_answers(
        selected.discovery,
        [
            ClarificationAnswer(
                question_id=selected.questions[0].id,
                answer="Fitness coaches",
                confirmed_claim=True,
            )
        ],
    )
    second_round = select_clarification_round(discovery, max_questions=1)
    discovery = second_round.discovery
    discovery.functional_requirements.append(
        Requirement(statement="Send reminders", source=InformationSource.INFERRED)
    )
    created = create_discovery(tmp_path, discovery)
    before_revision = specification_revision(created.specification)

    restored = load_discovery(tmp_path)
    assert restored.discovery == discovery
    assert restored.discovery.original_idea == idea
    assert restored.discovery.clarification_rounds == 2
    assert restored.discovery.clarification_history[0].question_ids == [
        question.id for question in selected.questions
    ]
    assert restored.discovery.clarification_history[1].round_number == 2
    assert restored.discovery.clarification_history[1].question_ids == [
        question.id for question in second_round.questions
    ]
    assert restored.discovery.target_users[0].name.source is InformationSource.CLARIFIED
    assert restored.discovery.target_users[0].name.evidence_ref == (
        f"clarification:{selected.questions[0].id}"
    )
    assert restored.discovery.functional_requirements[0].source is InformationSource.INFERRED
    assert specification_revision(restored.specification) == before_revision
    assert restored.current_decision is None


def test_approval_survives_reload_and_latest_rejection_wins(tmp_path: Path) -> None:
    _workspace(tmp_path)
    state = create_discovery(tmp_path, _complete_discovery())
    review = prepare_specification_review(state.specification)
    approval = record_review_decision(review, state.specification, decision=ReviewDecision.APPROVE)
    state = save_discovery(tmp_path, state.with_decision(approval))

    restored = load_discovery(tmp_path)
    assert restored.current_decision == approval
    assert can_handoff(restored.specification, restored.current_decision)

    rejection = record_review_decision(
        review, restored.specification, decision=ReviewDecision.REJECT, feedback="Reconsider scope"
    )
    rejected = save_discovery(tmp_path, restored.with_decision(rejection))
    restored = load_discovery(tmp_path)
    assert [entry.sequence for entry in restored.review_history] == [1, 2]
    assert restored.current_decision == rejection
    assert not can_handoff(restored.specification, restored.current_decision)
    assert rejected.generation == state.generation + 1

    with pytest.raises(DiscoveryPersistenceError, match="changed since"):
        save_discovery(tmp_path, state)
    assert load_discovery(tmp_path).current_decision == rejection


def test_changed_specification_makes_prior_approval_stale(tmp_path: Path) -> None:
    _workspace(tmp_path)
    state = create_discovery(tmp_path, _complete_discovery())
    review = prepare_specification_review(state.specification)
    approval = record_review_decision(review, state.specification, decision=ReviewDecision.APPROVE)
    state = save_discovery(tmp_path, state.with_decision(approval))

    updated_discovery = ProjectDiscovery.model_validate(state.discovery.model_dump())
    updated_discovery.assumptions.append(
        DiscoveryItem(statement="Clients use email", source=InformationSource.INFERRED)
    )
    save_discovery(tmp_path, state.with_discovery(updated_discovery))

    restored = load_discovery(tmp_path)
    assert restored.current_decision is None
    assert restored.review_history[0].record == approval
    assert not can_handoff(restored.specification, restored.current_decision)
    assert restored.specification_revision != approval.revision_id


@pytest.mark.parametrize(
    "damage", ["json", "version", "unknown", "metadata", "order", "revision", "decision"]
)
def test_invalid_persisted_data_fails_closed(tmp_path: Path, damage: str) -> None:
    _workspace(tmp_path)
    create_discovery(tmp_path, _complete_discovery())
    path = tmp_path / ".forge" / "discovery.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if damage == "json":
        path.write_text("{broken", encoding="utf-8")
    else:
        if damage == "version":
            data["schema_version"] = 2
        elif damage == "unknown":
            data["discovery"]["identity"]["unexpected"] = "not allowed"
        elif damage == "metadata":
            data.pop("review_history")
        elif damage == "revision":
            data["specification_revision"] = "rev-" + "0" * 64
        else:
            data["review_history"] = [
                {
                    "sequence": 2 if damage == "order" else 1,
                    "record": {
                        "revision_id": data["specification_revision"],
                        "decision": "reject" if damage == "order" else "invalid",
                    },
                }
            ]
        path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(DiscoveryPersistenceError):
        load_discovery(tmp_path)


def test_failed_replace_keeps_previous_valid_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _workspace(tmp_path)
    state = create_discovery(tmp_path, _complete_discovery())
    path = tmp_path / ".forge" / "discovery.json"
    previous_bytes = path.read_bytes()

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError(5, "simulated write failure")

    monkeypatch.setattr("forge.discovery.persistence.os.replace", fail_replace)
    with pytest.raises(DiscoveryPersistenceError, match="Cannot write"):
        save_discovery(tmp_path, state)

    assert path.read_bytes() == previous_bytes
    assert load_discovery(tmp_path) == state


def test_create_never_overwrites_existing_discovery(tmp_path: Path) -> None:
    _workspace(tmp_path)
    first = create_discovery(tmp_path, intake_idea("First idea"))
    path = tmp_path / ".forge" / "discovery.json"
    previous_bytes = path.read_bytes()

    with pytest.raises(DiscoveryPersistenceError, match="already exists"):
        create_discovery(tmp_path, intake_idea("Replacement idea"))

    assert path.read_bytes() == previous_bytes
    assert load_discovery(tmp_path) == first


def test_load_reports_missing_file_and_rejects_symlink(tmp_path: Path) -> None:
    _workspace(tmp_path)
    with pytest.raises(DiscoveryPersistenceError, match="does not exist"):
        load_discovery(tmp_path)

    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    (tmp_path / ".forge" / "discovery.json").symlink_to(outside)
    with pytest.raises(DiscoveryPersistenceError, match="symbolic link"):
        load_discovery(tmp_path)


def test_update_cannot_replace_the_original_idea(tmp_path: Path) -> None:
    _workspace(tmp_path)
    state = create_discovery(tmp_path, intake_idea("Original idea"))
    path = tmp_path / ".forge" / "discovery.json"
    previous_bytes = path.read_bytes()

    with pytest.raises(ValueError, match="original project idea"):
        state.with_discovery(intake_idea("Different idea"))
    with pytest.raises(DiscoveryPersistenceError, match="original project idea"):
        save_discovery(tmp_path, new_discovery_state(intake_idea("Different idea")))

    assert path.read_bytes() == previous_bytes

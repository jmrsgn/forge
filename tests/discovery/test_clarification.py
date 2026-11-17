"""Focused tests for bounded clarification and trusted answer capture."""

import pytest
from pydantic import ValidationError

from forge.discovery.clarification import (
    ClarificationAnswer,
    ClarificationError,
    record_developer_answers,
    select_clarification_round,
)
from forge.discovery.intake import intake_idea
from forge.discovery.models import (
    DiscoveryItem,
    InformationSource,
    OpenQuestion,
    ProjectDiscovery,
    ProjectProblem,
    ProjectTargetUser,
    QuestionStatus,
    Requirement,
)


def _user(statement: str) -> DiscoveryItem:
    return DiscoveryItem(
        statement=statement, source=InformationSource.USER, evidence_ref="original_idea"
    )


def _analyzed_discovery() -> ProjectDiscovery:
    discovery = intake_idea("Fitness coaches manage clients and create workout programs.")
    discovery.problem = ProjectProblem(statement=_user("Coaches need to manage clients"))
    discovery.target_users.append(ProjectTargetUser(name=_user("Fitness coaches")))
    discovery.functional_requirements.append(
        Requirement(
            statement="Manage clients", source=InformationSource.USER, evidence_ref="original_idea"
        )
    )
    return discovery


def test_round_prioritizes_missing_information_and_existing_blockers() -> None:
    discovery = intake_idea("Build a fitness app.")
    discovery.functional_requirements.append(
        Requirement(statement="Manage clients", source=InformationSource.INFERRED)
    )
    discovery.open_questions.extend(
        [
            OpenQuestion(question="Which colors should it use?"),
            OpenQuestion(question="Will clients have accounts?", blocking=True),
        ]
    )
    before = discovery.model_dump()

    result = select_clarification_round(discovery, max_questions=3)

    assert [question.question for question in result.questions] == [
        "Who are the intended users?",
        "What problem should the application solve?",
        "Will clients have accounts?",
    ]
    assert all(question.blocking and question.id for question in result.questions)
    assert result.discovery.clarification_rounds == 1
    assert result.discovery.open_questions[0].id is None
    assert discovery.model_dump() == before


def test_scope_conflict_is_blocking_and_confirmed_claims_are_not_reasked() -> None:
    discovery = _analyzed_discovery()
    discovery.out_of_scope.append(
        DiscoveryItem(statement="Manage clients", source=InformationSource.INFERRED)
    )
    discovery.functional_requirements.append(
        Requirement(statement="Manage clients", source=InformationSource.INFERRED)
    )

    result = select_clarification_round(discovery)

    assert [question.question for question in result.questions] == [
        "Is this capability in scope: Manage clients?"
    ]
    assert result.questions[0].blocking is True


def test_inferred_decisions_are_prioritized_before_optional_refinements() -> None:
    discovery = _analyzed_discovery()
    discovery.functional_requirements.append(
        Requirement(statement="Track progress", source=InformationSource.INFERRED)
    )
    discovery.assumptions.append(
        DiscoveryItem(statement="Clients use mobile devices", source=InformationSource.INFERRED)
    )
    discovery.open_questions.append(OpenQuestion(question="Which colors should it use?"))

    result = select_clarification_round(discovery)

    assert [question.question for question in result.questions] == [
        "Is this a required capability: Track progress?",
        "Is this assumption correct: Clients use mobile devices?",
        "Which colors should it use?",
    ]
    assert result.questions[0].blocking is True
    assert result.questions[1].blocking is False
    assert not any("Manage clients" in question.question for question in result.questions)


def test_duplicate_and_previously_answered_questions_are_skipped() -> None:
    discovery = _analyzed_discovery()
    discovery.open_questions.extend(
        [
            OpenQuestion(question="Should clients have accounts?"),
            OpenQuestion(question="  SHOULD clients have accounts?  "),
            OpenQuestion(
                question="Which platform?",
                id="q-platform",
                status=QuestionStatus.RESOLVED,
                answer=DiscoveryItem(
                    statement="Web",
                    source=InformationSource.CLARIFIED,
                    evidence_ref="clarification:q-platform",
                ),
            ),
        ]
    )

    result = select_clarification_round(discovery)

    assert len(result.questions) == 1
    assert result.questions[0].question == "Should clients have accounts?"
    assert result.questions[0].id is not None
    assert result.discovery.open_questions[2].status is QuestionStatus.RESOLVED
    assert select_clarification_round(result.discovery).questions == ()


def test_answer_is_preserved_with_clarified_evidence_and_no_claim_overwrite() -> None:
    discovery = _analyzed_discovery()
    discovery.open_questions.append(OpenQuestion(question="Should clients have accounts?"))
    question_round = select_clarification_round(discovery)
    question = question_round.questions[0]
    before = question_round.discovery.model_dump()
    answer = "  Yes, clients should see their workouts.  "

    result = record_developer_answers(
        question_round.discovery, [ClarificationAnswer(question_id=question.id, answer=answer)]
    )

    resolved = result.open_questions[0]
    assert resolved.status is QuestionStatus.RESOLVED
    assert resolved.answer.statement == answer
    assert resolved.answer.source is InformationSource.CLARIFIED
    assert resolved.answer.evidence_ref == f"clarification:{question.id}"
    assert result.functional_requirements == discovery.functional_requirements
    assert result.original_idea == discovery.original_idea
    assert question_round.discovery.model_dump() == before
    with pytest.raises(ClarificationError, match="already answered"):
        record_developer_answers(
            result, [ClarificationAnswer(question_id=question.id, answer="No")]
        )


def test_direct_answers_fill_empty_core_fields_verbatim() -> None:
    original = intake_idea("Build an application for fitness coaching.")
    question_round = select_clarification_round(original)
    answers = [
        ClarificationAnswer(
            question_id=question_round.questions[0].id,
            answer="  Fitness coaches  ",
            confirmed_claim=True,
        ),
        ClarificationAnswer(
            question_id=question_round.questions[1].id,
            answer="Coaches need to organize client training.",
            confirmed_claim=True,
        ),
        ClarificationAnswer(
            question_id=question_round.questions[2].id,
            answer="Create workout programs",
            confirmed_claim=True,
        ),
    ]

    result = record_developer_answers(question_round.discovery, answers)

    assert result.target_users[0].name.statement == "  Fitness coaches  "
    assert result.problem.statement.statement == "Coaches need to organize client training."
    assert result.functional_requirements[0].statement == "Create workout programs"
    assert all(
        item.source is InformationSource.CLARIFIED
        for item in (
            result.target_users[0].name,
            result.problem.statement,
            result.functional_requirements[0],
        )
    )
    assert result.functional_requirements[0].evidence_ref == (
        f"clarification:{question_round.questions[2].id}"
    )
    assert ProjectDiscovery.model_validate_json(result.model_dump_json()) == result
    assert original.target_users == []
    assert original.problem is None
    assert original.functional_requirements == []


def test_unconfirmed_answer_does_not_create_a_target_user() -> None:
    question_round = select_clarification_round(intake_idea("Build a coaching app."))
    result = record_developer_answers(
        question_round.discovery,
        [ClarificationAnswer(question_id=question_round.questions[0].id, answer="Fitness coaches")],
    )

    assert result.open_questions[0].answer.statement == "Fitness coaches"
    assert result.target_users == []


def test_invalid_or_duplicate_answers_do_not_mutate_discovery() -> None:
    discovery = _analyzed_discovery()
    discovery.open_questions.append(OpenQuestion(question="Should clients have accounts?"))
    question_round = select_clarification_round(discovery)
    question_id = question_round.questions[0].id
    before = question_round.discovery.model_dump()

    with pytest.raises(ClarificationError, match="Duplicate answer"):
        record_developer_answers(
            question_round.discovery,
            [
                ClarificationAnswer(question_id=question_id, answer="Yes"),
                ClarificationAnswer(question_id=question_id, answer="No"),
            ],
        )
    with pytest.raises(ClarificationError, match="Unknown question"):
        record_developer_answers(
            question_round.discovery, [ClarificationAnswer(question_id="unknown", answer="Yes")]
        )
    with pytest.raises(ClarificationError, match="cannot directly populate"):
        record_developer_answers(
            question_round.discovery,
            [ClarificationAnswer(question_id=question_id, answer="Yes", confirmed_claim=True)],
        )
    with pytest.raises(ValidationError):
        ClarificationAnswer(question_id=question_id, answer="   ")
    with pytest.raises(ValidationError):
        ClarificationAnswer(question_id=question_id)
    with pytest.raises(ValidationError, match="confirmed claim requires an answer"):
        ClarificationAnswer(question_id=question_id, answer=None, confirmed_claim=True)
    with pytest.raises(ValidationError):
        ClarificationAnswer(question_id=question_id, answer="Yes", source="clarified")

    assert question_round.discovery.model_dump() == before


def test_multiple_rounds_deferred_unanswered_and_limit() -> None:
    discovery = _analyzed_discovery()
    discovery.open_questions.extend(
        OpenQuestion(question=question)
        for question in ("Question one?", "Question two?", "Question three?", "Question four?")
    )

    first = select_clarification_round(discovery, max_questions=2, max_rounds=2)
    after_answers = record_developer_answers(
        first.discovery,
        [
            ClarificationAnswer(question_id=first.questions[0].id, answer="Yes"),
            ClarificationAnswer(question_id=first.questions[1].id, answer=None),
        ],
    )
    second = select_clarification_round(after_answers, max_questions=2, max_rounds=2)
    stopped = select_clarification_round(second.discovery, max_questions=2, max_rounds=2)

    assert [question.question for question in second.questions] == [
        "Question three?",
        "Question four?",
    ]
    assert [question.status for question in stopped.discovery.open_questions] == [
        QuestionStatus.RESOLVED,
        QuestionStatus.DEFERRED,
        QuestionStatus.UNRESOLVED,
        QuestionStatus.UNRESOLVED,
    ]
    assert stopped.discovery.clarification_rounds == 2
    assert stopped.questions == ()
    assert stopped.limit_reached is True


def test_question_state_and_identifiers_are_validated() -> None:
    with pytest.raises(ValidationError, match="Deferred questions require an id"):
        OpenQuestion(question="Which platform?", status=QuestionStatus.DEFERRED)
    with pytest.raises(ValidationError, match="matching CLARIFIED evidence"):
        OpenQuestion(
            question="Which platform?",
            id="q-platform",
            status=QuestionStatus.RESOLVED,
            answer=_user("Web"),
        )
    with pytest.raises(ValidationError, match="Question ids must be unique"):
        ProjectDiscovery(
            original_idea="Build an app.",
            open_questions=[
                OpenQuestion(question="First?", id="q-1"),
                OpenQuestion(question="Second?", id="q-1"),
            ],
        )
    with pytest.raises(ClarificationError, match="positive integer"):
        select_clarification_round(_analyzed_discovery(), max_rounds=0)

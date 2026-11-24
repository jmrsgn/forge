"""Select clarification questions and record explicit developer answers."""

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Self

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator

from forge.discovery.models import (
    ClarificationRoundHistory,
    DiscoveryItem,
    InformationSource,
    NonBlankText,
    OpenQuestion,
    ProjectDiscovery,
    ProjectProblem,
    ProjectTargetUser,
    QuestionStatus,
    Requirement,
)
from forge.error.clarification_errors import ClarificationError

_USERS_QUESTION = "Who are the intended users?"
_PROBLEM_QUESTION = "What problem should the application solve?"
_CAPABILITY_QUESTION = "What must the application let its users do?"


class ClarificationAnswer(BaseModel):
    """Developer text; only a trusted caller may mark it as a confirmed claim.

    An explicit None defers the question.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    question_id: NonBlankText
    answer: NonBlankText | None
    confirmed_claim: StrictBool = False

    @model_validator(mode="after")
    def validate_confirmation_requires_answer(self) -> Self:
        """Reject a confirmed claim when the developer deferred the question."""

        if self.confirmed_claim and self.answer is None:
            raise ValueError("A confirmed claim requires an answer")

        return self


@dataclass(frozen=True, slots=True)
class ClarificationRound:
    """The selected questions, updated discovery copy, and round-limit signal."""

    discovery: ProjectDiscovery
    questions: tuple[OpenQuestion, ...]
    limit_reached: bool = False


def _normalize_text(text: str) -> str:
    """Normalize text for comparison without changing the stored wording."""

    return " ".join(text.casefold().split())


def _generate_question_id(text: str) -> str:
    """Derive a stable ID from normalized question text."""

    return f"q-{sha256(_normalize_text(text).encode('utf-8')).hexdigest()[:16]}"


def _collect_confirmed_statements(discovery: ProjectDiscovery) -> set[str]:
    """Find established claims so their inferred duplicates are not reasked."""

    items = [
        *discovery.functional_requirements,
        *discovery.quality_requirements,
        *discovery.constraints,
        *discovery.assumptions,
        *discovery.out_of_scope,
        *(user.name for user in discovery.target_users),
    ]

    return {
        _normalize_text(item.statement)
        for item in items
        if item.source in (InformationSource.USER, InformationSource.CLARIFIED)
    }


def select_clarification_round(
    discovery: ProjectDiscovery, *, max_questions: int = 3, max_rounds: int = 3
) -> ClarificationRound:
    """Choose the next small set of questions without changing ``discovery``.

    Build candidates from missing information, scope conflicts, existing open
    questions, and inferred claims. Prioritize blockers, then skip duplicates
    and questions already asked, answered, or deferred. Return a discovery copy
    with IDs for the selected questions and an incremented round count.

    Once ``max_rounds`` is reached, return no questions with
    ``limit_reached=True``; this does not mean all questions are resolved.

    For open questions "Which platform?" (unasked, index 0) and "Can clients
    sign in?" (already assigned the illustrative id "q-existing", index 1),
    the lookup collections contain::

        question_index_by_text = {
            "which platform?": 0,
            "can clients sign in?": 1,
        }
        unavailable_question_texts = {"can clients sign in?"}
        question_text_by_id = {"q-existing": "can clients sign in?"}
    """

    # The number is a simple priority band; insertion order breaks ties.
    question_candidates: list[tuple[int, str, bool, int | None]] = []

    def add_question_candidate(
        priority: int, text: str, blocking: bool, index: int | None = None
    ) -> None:
        """Stage a question candidate with its priority and existing index."""
        question_candidates.append((priority, text, blocking, index))

    if type(max_questions) is not int or max_questions < 1:
        raise ClarificationError("max_questions must be a positive integer")

    if type(max_rounds) is not int or max_rounds < 1:
        raise ClarificationError("max_rounds must be a positive integer")

    updated_discovery = ProjectDiscovery.model_validate(discovery.model_dump())

    if updated_discovery.clarification_rounds >= max_rounds:
        return ClarificationRound(discovery=updated_discovery, questions=(), limit_reached=True)

    if not updated_discovery.target_users:
        add_question_candidate(0, _USERS_QUESTION, True)
    if updated_discovery.problem is None or updated_discovery.problem.statement is None:
        add_question_candidate(0, _PROBLEM_QUESTION, True)
    if not updated_discovery.functional_requirements:
        add_question_candidate(0, _CAPABILITY_QUESTION, True)

    out_of_scope_list = {_normalize_text(item.statement) for item in updated_discovery.out_of_scope}

    # Check if any inferred items are already confirmed; if so, don't ask about them.
    for requirement in updated_discovery.functional_requirements:
        if _normalize_text(requirement.statement) in out_of_scope_list:
            add_question_candidate(
                0, f"Is this capability in scope: {requirement.statement}?", True
            )

    for index, question in enumerate(updated_discovery.open_questions):
        if question.status is QuestionStatus.UNRESOLVED:
            add_question_candidate(
                1 if question.blocking else 4, question.question, question.blocking, index
            )

    confirmed_statements = _collect_confirmed_statements(updated_discovery)

    # Check users that are not yet confirmed.
    for user in updated_discovery.target_users:
        if (
            user.name.source is InformationSource.INFERRED
            and _normalize_text(user.name.statement) not in confirmed_statements
        ):
            add_question_candidate(2, f"Are these intended users: {user.name.statement}?", True)

    # Check constraints that are not yet confirmed.
    for constraint in updated_discovery.constraints:
        if (
            constraint.source is InformationSource.INFERRED
            and _normalize_text(constraint.statement) not in confirmed_statements
        ):
            add_question_candidate(2, f"Is this constraint required: {constraint.statement}?", True)

    # Check functional requirements that are not yet confirmed.
    for requirement in updated_discovery.functional_requirements:
        if (
            requirement.source is InformationSource.INFERRED
            and _normalize_text(requirement.statement) not in confirmed_statements
        ):
            add_question_candidate(
                2, f"Is this a required capability: {requirement.statement}?", True
            )

    # Check assumptions that are not yet confirmed.
    for assumption in updated_discovery.assumptions:
        if (
            assumption.source is InformationSource.INFERRED
            and _normalize_text(assumption.statement) not in confirmed_statements
        ):
            add_question_candidate(3, f"Is this assumption correct: {assumption.statement}?", False)

    # Check quality requirements that are not yet confirmed.
    for requirement in updated_discovery.quality_requirements:
        if (
            requirement.source is InformationSource.INFERRED
            and _normalize_text(requirement.statement) not in confirmed_statements
        ):
            add_question_candidate(
                5, f"Is this quality requirement important: {requirement.statement}?", False
            )

    question_index_by_text = {
        # Example entry: "which platform?": 0
        _normalize_text(question.question): index
        for index, question in enumerate(updated_discovery.open_questions)
    }

    unavailable_question_texts = {
        # Example member: "can clients sign in?"
        _normalize_text(question.question)
        for question in updated_discovery.open_questions
        if question.id is not None or question.status is not QuestionStatus.UNRESOLVED
    }

    question_text_by_id = {
        # Example entry: "q-existing": "can clients sign in?"
        question.id: _normalize_text(question.question)
        for question in updated_discovery.open_questions
        if question.id is not None
    }

    selected_questions: list[OpenQuestion] = []

    for _, text, blocking, index in sorted(question_candidates, key=lambda candidate: candidate[0]):
        question_text = _normalize_text(text)
        if question_text in unavailable_question_texts:
            # Skip questions that are already asked, answered, or deferred.
            continue

        question_id = _generate_question_id(text)
        if question_id in question_text_by_id and question_text_by_id[question_id] != question_text:
            raise ClarificationError("Question id collision")

        if index is None:
            index = question_index_by_text.get(question_text)

        if index is None:
            question = OpenQuestion(question=text, blocking=blocking, id=question_id)
            updated_discovery.open_questions.append(question)
            # Map the newly appended question text to its index.
            question_index_by_text[question_text] = len(updated_discovery.open_questions) - 1
        else:
            existing_question = updated_discovery.open_questions[index]
            question = OpenQuestion.model_validate(
                {
                    **existing_question.model_dump(),
                    "id": question_id,
                    "blocking": existing_question.blocking or blocking,
                }
            )
            # Replace the existing question with the updated one, preserving its index.
            updated_discovery.open_questions[index] = question

        # Register the question ID for collision detection.
        question_text_by_id[question_id] = question_text

        # Prevent the question from being selected again.
        unavailable_question_texts.add(question_text)

        # Include the question in the current clarification round.
        selected_questions.append(question)

        if len(selected_questions) == max_questions:
            break

    if selected_questions:
        updated_discovery.clarification_rounds += 1
        updated_discovery.clarification_history.append(
            ClarificationRoundHistory(
                round_number=updated_discovery.clarification_rounds,
                question_ids=[question.id for question in selected_questions],
            )
        )

    return ClarificationRound(discovery=updated_discovery, questions=tuple(selected_questions))


def record_developer_answers(
    discovery: ProjectDiscovery, answers: Sequence[ClarificationAnswer]
) -> ProjectDiscovery:
    """Apply developer answers to a copy of ``discovery``.

    Require each question ID to exist and still be unresolved. Store answer
    text verbatim as ``CLARIFIED`` with a matching clarification evidence ref;
    an explicit ``answer=None`` defers the question. A trusted caller may set
    ``confirmed_claim=True`` to fill an empty core field for one of the three
    built-in questions. Existing claims are never overwritten, and invalid
    submissions leave the input discovery unchanged.
    """
    updated = ProjectDiscovery.model_validate(discovery.model_dump())
    by_id = {
        question.id: index
        for index, question in enumerate(updated.open_questions)
        if question.id is not None
    }
    seen: set[str] = set()
    replacements: dict[int, OpenQuestion] = {}
    confirmed_indices: set[int] = set()
    for submission in answers:
        if not isinstance(submission, ClarificationAnswer):
            raise ClarificationError("Answers must be ClarificationAnswer values")
        if submission.question_id in seen:
            raise ClarificationError("Duplicate answer for a clarification question")
        seen.add(submission.question_id)
        index = by_id.get(submission.question_id)
        if index is None:
            raise ClarificationError("Unknown question id")
        question = updated.open_questions[index]
        if question.status is not QuestionStatus.UNRESOLVED:
            raise ClarificationError("Question is already answered or deferred")
        if submission.confirmed_claim:
            if question.question not in (_USERS_QUESTION, _PROBLEM_QUESTION, _CAPABILITY_QUESTION):
                raise ClarificationError("Question cannot directly populate a discovery claim")
            confirmed_indices.add(index)
        answer = (
            DiscoveryItem(
                statement=submission.answer,
                source=InformationSource.CLARIFIED,
                evidence_ref=f"clarification:{question.id}",
            )
            if submission.answer is not None
            else None
        )
        replacements[index] = OpenQuestion(
            question=question.question,
            blocking=question.blocking,
            id=question.id,
            status=QuestionStatus.RESOLVED if answer is not None else QuestionStatus.DEFERRED,
            answer=answer,
        )

    for index, question in replacements.items():
        updated.open_questions[index] = question
        if question.answer is None or index not in confirmed_indices:
            continue
        if question.question == _USERS_QUESTION and not updated.target_users:
            updated.target_users.append(ProjectTargetUser(name=question.answer))
        elif question.question == _PROBLEM_QUESTION:
            if updated.problem is None:
                updated.problem = ProjectProblem()
            if updated.problem.statement is None:
                updated.problem.statement = question.answer
        elif question.question == _CAPABILITY_QUESTION and not updated.functional_requirements:
            updated.functional_requirements.append(
                Requirement(
                    statement=question.answer.statement,
                    source=InformationSource.CLARIFIED,
                    evidence_ref=question.answer.evidence_ref,
                )
            )
    return updated

"""Select clarification questions and record explicit developer answers."""

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Self

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator

from forge.discovery.models import (
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

_USERS_QUESTION = "Who are the intended users?"
_PROBLEM_QUESTION = "What problem should the application solve?"
_CAPABILITY_QUESTION = "What must the application let its users do?"


class ClarificationError(ValueError):
    """The requested clarification round or answer is invalid."""


class ClarificationAnswer(BaseModel):
    """Developer text; only a trusted caller may mark it as a confirmed claim.

    An explicit None defers the question.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    question_id: NonBlankText
    answer: NonBlankText | None
    confirmed_claim: StrictBool = False

    @model_validator(mode="after")
    def confirmation_requires_answer(self) -> Self:
        if self.confirmed_claim and self.answer is None:
            raise ValueError("A confirmed claim requires an answer")
        return self


@dataclass(frozen=True, slots=True)
class ClarificationRound:
    discovery: ProjectDiscovery
    questions: tuple[OpenQuestion, ...]
    limit_reached: bool = False


def _key(text: str) -> str:
    return " ".join(text.casefold().split())


def _question_id(text: str) -> str:
    return f"q-{sha256(_key(text).encode('utf-8')).hexdigest()[:16]}"


def _trusted_statements(discovery: ProjectDiscovery) -> set[str]:
    items = [
        *discovery.functional_requirements,
        *discovery.quality_requirements,
        *discovery.constraints,
        *discovery.assumptions,
        *discovery.out_of_scope,
        *(user.name for user in discovery.target_users),
    ]
    return {
        _key(item.statement)
        for item in items
        if item.source in (InformationSource.USER, InformationSource.CLARIFIED)
    }


def select_clarification_round(
    discovery: ProjectDiscovery, *, max_questions: int = 3, max_rounds: int = 3
) -> ClarificationRound:
    """Select new questions, preferring scope blockers and existing open questions."""
    if type(max_questions) is not int or max_questions < 1:
        raise ClarificationError("max_questions must be a positive integer")
    if type(max_rounds) is not int or max_rounds < 1:
        raise ClarificationError("max_rounds must be a positive integer")

    updated = ProjectDiscovery.model_validate(discovery.model_dump())
    if updated.clarification_rounds >= max_rounds:
        return ClarificationRound(discovery=updated, questions=(), limit_reached=True)

    # The number is a simple priority band; insertion order breaks ties.
    candidates: list[tuple[int, str, bool, int | None]] = []

    def add(priority: int, text: str, blocking: bool, index: int | None = None) -> None:
        candidates.append((priority, text, blocking, index))

    if not updated.target_users:
        add(0, _USERS_QUESTION, True)
    if updated.problem is None or updated.problem.statement is None:
        add(0, _PROBLEM_QUESTION, True)
    if not updated.functional_requirements:
        add(0, _CAPABILITY_QUESTION, True)

    out_of_scope = {_key(item.statement) for item in updated.out_of_scope}
    for requirement in updated.functional_requirements:
        if _key(requirement.statement) in out_of_scope:
            add(0, f"Is this capability in scope: {requirement.statement}?", True)

    for index, question in enumerate(updated.open_questions):
        if question.status is QuestionStatus.UNRESOLVED:
            add(1 if question.blocking else 4, question.question, question.blocking, index)

    trusted = _trusted_statements(updated)
    for user in updated.target_users:
        if (
            user.name.source is InformationSource.INFERRED
            and _key(user.name.statement) not in trusted
        ):
            add(2, f"Are these intended users: {user.name.statement}?", True)
    for constraint in updated.constraints:
        if (
            constraint.source is InformationSource.INFERRED
            and _key(constraint.statement) not in trusted
        ):
            add(2, f"Is this constraint required: {constraint.statement}?", True)
    for requirement in updated.functional_requirements:
        if (
            requirement.source is InformationSource.INFERRED
            and _key(requirement.statement) not in trusted
        ):
            add(2, f"Is this a required capability: {requirement.statement}?", True)
    for assumption in updated.assumptions:
        if (
            assumption.source is InformationSource.INFERRED
            and _key(assumption.statement) not in trusted
        ):
            add(3, f"Is this assumption correct: {assumption.statement}?", False)
    for requirement in updated.quality_requirements:
        if (
            requirement.source is InformationSource.INFERRED
            and _key(requirement.statement) not in trusted
        ):
            add(5, f"Is this quality requirement important: {requirement.statement}?", False)

    by_text = {
        _key(question.question): index for index, question in enumerate(updated.open_questions)
    }
    unavailable = {
        _key(question.question)
        for question in updated.open_questions
        if question.id is not None or question.status is not QuestionStatus.UNRESOLVED
    }
    ids = {
        question.id: _key(question.question)
        for question in updated.open_questions
        if question.id is not None
    }
    selected: list[OpenQuestion] = []
    for _, text, blocking, index in sorted(candidates, key=lambda candidate: candidate[0]):
        key = _key(text)
        if key in unavailable:
            continue
        question_id = _question_id(text)
        if question_id in ids and ids[question_id] != key:
            raise ClarificationError("Question id collision")
        if index is None:
            index = by_text.get(key)
        if index is None:
            question = OpenQuestion(question=text, blocking=blocking, id=question_id)
            updated.open_questions.append(question)
            by_text[key] = len(updated.open_questions) - 1
        else:
            existing = updated.open_questions[index]
            question = OpenQuestion.model_validate(
                {
                    **existing.model_dump(),
                    "id": question_id,
                    "blocking": existing.blocking or blocking,
                }
            )
            updated.open_questions[index] = question
        ids[question_id] = key
        unavailable.add(key)
        selected.append(question)
        if len(selected) == max_questions:
            break

    if selected:
        updated.clarification_rounds += 1
    return ClarificationRound(discovery=updated, questions=tuple(selected))


def record_developer_answers(
    discovery: ProjectDiscovery, answers: Sequence[ClarificationAnswer]
) -> ProjectDiscovery:
    """Record explicit developer text without interpreting or promoting other claims."""
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

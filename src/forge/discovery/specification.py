"""Build and render a reviewable specification from discovery data."""

import json
import re
from collections import defaultdict
from collections.abc import Iterator
from hashlib import sha256
from html import escape
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from forge.discovery.models import (
    DiscoveryItem,
    InformationSource,
    NonBlankText,
    ProjectDiscovery,
    QuestionStatus,
)

SPECIFICATION_SCHEMA_VERSION = 1


class SpecificationIssue(BaseModel):
    """An objective gap, unresolved question, or recorded scope conflict."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NonBlankText
    kind: Literal["gap", "unresolved_question", "contradiction"]
    statement: NonBlankText
    related_ids: list[str] = Field(default_factory=list)


class DiscoverySpecification(BaseModel):
    """A validated discovery snapshot with stable item IDs and derived issues.

    The discovery record is the sole copy of each claim. IDs and issues are
    checked against it so callers cannot provide inconsistent specifications.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    discovery: ProjectDiscovery
    item_ids: dict[str, str]
    issues: list[SpecificationIssue]

    @model_validator(mode="after")
    def validate_derived_data(self) -> Self:
        """Reject identifiers or issues that disagree with the discovery."""
        expected_ids = _item_ids(self.discovery)
        if self.item_ids != expected_ids:
            raise ValueError("Specification item IDs do not match discovery claims")
        if len({issue.id for issue in self.issues}) != len(self.issues):
            raise ValueError("Specification issue IDs must be unique")
        if self.issues != _issues(self.discovery, expected_ids):
            raise ValueError("Specification issues do not match discovery")
        return self


def _digest(*parts: str) -> str:
    """Hash text deterministically without relying on Python's hash seed."""
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()[:16]


def _key(value: str) -> str:
    """Normalize text only for comparisons, preserving the stored wording."""
    return " ".join(value.casefold().split())


def _claims(discovery: ProjectDiscovery) -> Iterator[tuple[str, str, DiscoveryItem]]:
    """Yield paths and stable category keys for every provenance-bearing claim."""
    for field in ("name", "summary"):
        item = getattr(discovery.identity, field)
        if item is not None:
            yield f"identity.{field}", f"identity.{field}", item

    if discovery.problem is not None:
        if discovery.problem.statement is not None:
            yield "problem.statement", "problem.statement", discovery.problem.statement
        for index, item in enumerate(discovery.problem.goals):
            yield f"problem.goals.{index}", "problem.goals", item

    for index, user in enumerate(discovery.target_users):
        context = _key(user.name.statement)
        yield f"target_users.{index}.name", "target_users.name", user.name
        if user.description is not None:
            yield (
                f"target_users.{index}.description",
                f"target_users.{context}.description",
                user.description,
            )
        for goal_index, item in enumerate(user.goals):
            yield f"target_users.{index}.goals.{goal_index}", f"target_users.{context}.goals", item

    for index, use_case in enumerate(discovery.use_cases):
        context = _key(use_case.actor.statement + "|" + use_case.objective.statement)
        for field in ("actor", "objective", "expected_outcome"):
            yield (
                f"use_cases.{index}.{field}",
                f"use_cases.{context}.{field}",
                getattr(use_case, field),
            )

    for category in (
        "in_scope",
        "out_of_scope",
        "functional_requirements",
        "quality_requirements",
        "constraints",
        "assumptions",
    ):
        for index, item in enumerate(getattr(discovery, category)):
            yield f"{category}.{index}", category, item

    for index, question in enumerate(discovery.open_questions):
        if question.answer is not None:
            yield (
                f"open_questions.{index}.answer",
                f"questions.{_key(question.question)}.answer",
                question.answer,
            )


def _item_ids(discovery: ProjectDiscovery) -> dict[str, str]:
    """Assign content IDs; array positions locate items but never define IDs."""
    ids = {"original_idea": "original_idea"}
    occurrences: dict[str, int] = defaultdict(int)
    for path, category, item in _claims(discovery):
        base = f"S-{_digest(category, item.statement, item.source.value, item.evidence_ref or '')}"
        occurrences[base] += 1
        ids[path] = base if occurrences[base] == 1 else f"{base}-{occurrences[base]}"

    for index, use_case in enumerate(discovery.use_cases):
        base = f"UC-{_digest(use_case.actor.statement, use_case.objective.statement, use_case.expected_outcome.statement)}"
        occurrences[base] += 1
        ids[f"use_cases.{index}"] = (
            base if occurrences[base] == 1 else f"{base}-{occurrences[base]}"
        )

    for index, question in enumerate(discovery.open_questions):
        if question.id is not None:
            ids[f"open_questions.{index}"] = question.id
        else:
            base = f"Q-{_digest(_key(question.question))}"
            occurrences[base] += 1
            ids[f"open_questions.{index}"] = (
                base if occurrences[base] == 1 else f"{base}-{occurrences[base]}"
            )

    if len(ids.values()) != len(set(ids.values())):
        raise ValueError("Specification item ID collision")
    return ids


def _issues(discovery: ProjectDiscovery, ids: dict[str, str]) -> list[SpecificationIssue]:
    """Report only missing sections, unanswered questions, and exact scope conflicts."""
    issues: list[SpecificationIssue] = []

    def add(
        kind: Literal["gap", "unresolved_question", "contradiction"],
        statement: str,
        related: list[str],
    ) -> None:
        """Append an issue with a stable ID derived from its meaning."""
        issues.append(
            SpecificationIssue(
                id=f"ISS-{_digest(kind, statement, *related)}",
                kind=kind,
                statement=statement,
                related_ids=related,
            )
        )

    missing = (
        (discovery.identity.name is None, "Project name is missing."),
        (discovery.identity.summary is None, "Project summary is missing."),
        (
            discovery.problem is None or discovery.problem.statement is None,
            "Problem statement is missing.",
        ),
        (
            discovery.problem is None or not discovery.problem.goals,
            "Project objectives are missing.",
        ),
        (not discovery.target_users, "Target users are missing."),
        (not discovery.in_scope, "In-scope items are missing."),
        (not discovery.use_cases, "Use cases are missing."),
        (not discovery.functional_requirements, "Functional requirements are missing."),
    )
    
    for absent, statement in missing:
        if absent:
            add("gap", statement, [])

    for index, question in enumerate(discovery.open_questions):
        if question.status is not QuestionStatus.RESOLVED:
            state = "deferred" if question.status is QuestionStatus.DEFERRED else "unanswered"
            add(
                "unresolved_question",
                f"{question.question} ({state})",
                [ids[f"open_questions.{index}"]],
            )

    excluded: dict[str, list[str]] = defaultdict(list)
    for index, item in enumerate(discovery.out_of_scope):
        excluded[_key(item.statement)].append(ids[f"out_of_scope.{index}"])
    for category in ("in_scope", "functional_requirements"):
        for index, item in enumerate(getattr(discovery, category)):
            for excluded_id in excluded[_key(item.statement)]:
                add(
                    "contradiction",
                    f"The same item is both in and out of scope: {item.statement}",
                    [ids[f"{category}.{index}"], excluded_id],
                )
    return issues


def build_specification(discovery: ProjectDiscovery) -> DiscoverySpecification:
    """Return a review draft without changing the input discovery record."""
    snapshot = ProjectDiscovery.model_validate(discovery.model_dump())
    ids = _item_ids(snapshot)
    return DiscoverySpecification(
        schema_version=SPECIFICATION_SCHEMA_VERSION,
        discovery=snapshot,
        item_ids=ids,
        issues=_issues(snapshot, ids),
    )


def _inline(value: str) -> str:
    """Keep untrusted claim text from creating Markdown structure."""
    escaped = escape(value, quote=False).replace("\\", "\\\\")
    for marker in ("`", "*", "_", "[", "]", "#", "|", "!"):
        escaped = escaped.replace(marker, f"\\{marker}")
    return escaped.replace("\r\n", "<br>").replace("\n", "<br>").replace("\r", "<br>")


def _claim(path: str, item: DiscoveryItem, ids: dict[str, str]) -> str:
    """Render one claim with its provenance and evidence reference."""
    status = "PROPOSED" if item.source is InformationSource.INFERRED else item.source.value.upper()
    evidence = f"; evidence: {_inline(item.evidence_ref)}" if item.evidence_ref else ""
    return f"- **{_inline(ids[path])}** {_inline(item.statement)} — {status}{evidence}"


def _section(
    title: str, category: str, items: list[DiscoveryItem], ids: dict[str, str]
) -> list[str]:
    """Render a collection of claims or a visible empty marker."""
    lines = [f"## {title}", ""]
    lines.extend(_claim(f"{category}.{index}", item, ids) for index, item in enumerate(items))
    if not items:
        lines.append("_Not specified._")
    return [*lines, ""]


def render_specification_markdown(specification: DiscoverySpecification) -> str:
    """Render the validated structured specification deterministically."""
    specification = DiscoverySpecification.model_validate(specification.model_dump())
    discovery = specification.discovery
    ids = specification.item_ids
    lines = [
        "# Discovery Specification (Review Draft)",
        "",
        f"Schema version: {specification.schema_version}",
        "",
        "## Original Idea",
        "",
        "Reference: `original_idea`",
        "",
    ]
    fence = "`" * max(
        3, max((len(run) for run in re.findall(r"`+", discovery.original_idea)), default=0) + 1
    )
    lines.extend((fence, discovery.original_idea, fence, ""))

    lines.extend(("## Project Identity", ""))
    for field, label in (("name", "Name"), ("summary", "Summary")):
        item = getattr(discovery.identity, field)
        lines.append(f"**{label}:**")
        lines.append(
            _claim(f"identity.{field}", item, ids) if item is not None else "_Not specified._"
        )
        lines.append("")

    lines.extend(("## Problem and Objectives", ""))
    if discovery.problem is None or discovery.problem.statement is None:
        lines.append("_Problem not specified._")
    else:
        lines.append(_claim("problem.statement", discovery.problem.statement, ids))
    lines.extend(("", "### Objectives", ""))
    goals = discovery.problem.goals if discovery.problem is not None else []
    lines.extend(_claim(f"problem.goals.{i}", item, ids) for i, item in enumerate(goals))
    if not goals:
        lines.append("_Not specified._")
    lines.append("")

    lines.extend(("## Target Users", ""))
    for index, user in enumerate(discovery.target_users):
        lines.append(_claim(f"target_users.{index}.name", user.name, ids))
        if user.description is not None:
            lines.append("  " + _claim(f"target_users.{index}.description", user.description, ids))
        for goal_index, goal in enumerate(user.goals):
            lines.append("  " + _claim(f"target_users.{index}.goals.{goal_index}", goal, ids))
    if not discovery.target_users:
        lines.append("_Not specified._")
    lines.append("")

    lines.extend(_section("In Scope", "in_scope", discovery.in_scope, ids))
    lines.extend(_section("Out of Scope", "out_of_scope", discovery.out_of_scope, ids))
    lines.extend(("## Use Cases", ""))
    for index, use_case in enumerate(discovery.use_cases):
        lines.append(f"### {_inline(ids[f'use_cases.{index}'])}")
        lines.append("")
        for field, label in (
            ("actor", "Actor"),
            ("objective", "Objective"),
            ("expected_outcome", "Expected outcome"),
        ):
            lines.append(f"**{label}:**")
            lines.append(_claim(f"use_cases.{index}.{field}", getattr(use_case, field), ids))
        lines.append("")
    if not discovery.use_cases:
        lines.extend(("_Not specified._", ""))

    for title, category in (
        ("Functional Requirements", "functional_requirements"),
        ("Quality Requirements", "quality_requirements"),
        ("Constraints", "constraints"),
        ("Assumptions", "assumptions"),
    ):
        lines.extend(_section(title, category, getattr(discovery, category), ids))

    lines.extend(("## Open Questions and Decisions", ""))
    for index, question in enumerate(discovery.open_questions):
        label = "BLOCKING" if question.blocking else "optional"
        lines.append(
            f"- **{_inline(ids[f'open_questions.{index}'])}** {_inline(question.question)} "
            f"— {question.status.value.upper()}, {label}"
        )
        if question.answer is not None:
            lines.append("  " + _claim(f"open_questions.{index}.answer", question.answer, ids))
    if not discovery.open_questions:
        lines.append("_None recorded._")
    lines.extend(("", "## Gaps and Unresolved Issues", ""))
    for issue in specification.issues:
        references = (
            f" (items: {', '.join(_inline(item_id) for item_id in issue.related_ids)})"
            if issue.related_ids
            else ""
        )
        lines.append(
            f"- **{_inline(issue.id)}** [{issue.kind}] {_inline(issue.statement)}{references}"
        )
    if not specification.issues:
        lines.append("_None identified by structural checks._")
    return "\n".join(lines) + "\n"

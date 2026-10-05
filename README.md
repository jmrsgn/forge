# Forge

> AI-assisted software engineering toolkit for structured, context-aware, and human-controlled development.

Forge is an AI-assisted software engineering toolkit designed to orchestrate coding agents through a structured development workflow.

Instead of sending broad implementation prompts directly to a coding agent, Forge aims to establish project context, analyze the requested change, create an implementation plan, maintain human oversight, execute the approved work, and validate the result.

## Vision

Forge is being designed around two project entry points:

### New Project

Transform an idea or initial requirements into structured project knowledge, architecture, technology decisions, and a development roadmap before implementation begins.

### Existing Project

Analyze an existing repository to understand its technology, architecture, dependencies, conventions, and project knowledge before performing development tasks.

Both eventually converge into the same development workflow:

```text
Project Knowledge
       ↓
Task
       ↓
ANALYZE
       ↓
PLAN
       ↓
HUMAN APPROVAL
       ↓
IMPLEMENT
       ↓
VALIDATE
       ↓
REVIEW
       ↓
DONE
```

## Principles

Forge is being developed around several core principles:

- understand before implementing;
- plan before modification;
- keep humans in control of important decisions;
- provide agents with minimal relevant context;
- respect existing repository architecture and conventions;
- validate generated changes before considering work complete;
- remain independent of a single programming language or AI provider;
- start simple and introduce complexity only when necessary.

## Status

Forge is currently in early development.

**Current milestone:** `V0.1 — Forge Foundation`

The initial milestone focuses on establishing the Python application, CLI, configuration model, internal architecture, project initialization foundation, and AI provider abstraction.

Advanced AI-assisted development capabilities are not implemented yet.

## Development

Forge requires Python 3.12 or newer and uses `uv` for project and dependency management.

Install the project dependencies:

```bash
uv sync
```

Run the test suite:

```bash
uv run pytest
```

Run lint checks:

```bash
uv run ruff check .
```

## License

Forge is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
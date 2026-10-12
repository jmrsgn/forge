# Forge

> AI-assisted software engineering orchestration toolkit for structured, context-aware, and human-controlled development.

---

## 1. Project Overview

**Forge** is an AI-assisted software engineering toolkit designed to orchestrate coding agents through a structured development workflow.

Instead of relying on ad-hoc prompts such as:

```text
"Implement feature X."
```

Forge provides a controlled workflow where an AI agent first understands the repository and requested change, creates an implementation plan, waits for human approval when required, performs the change, validates the result, and reviews the implementation.

The initial focus of Forge is the **software development portion of the SDLC**.

The long-term vision is to expand Forge into an AI-assisted SDLC toolkit capable of supporting workflows from business requirements through architecture, development, testing, and deployment.

Forge is inspired by modern AI-assisted SDLC tooling and agentic development practices, including concepts demonstrated by Nexus, but Forge is an independent project with its own architecture and implementation.

---

## 2. Problem Statement

AI coding agents are powerful but can become unreliable when they lack sufficient project context or are given broad implementation instructions without a structured workflow.

Common problems include:

- modifying unrelated files;
- misunderstanding project architecture;
- ignoring existing conventions;
- generating unnecessary abstractions;
- loading excessive repository context;
- implementing before understanding the change;
- failing to validate generated code;
- losing architectural knowledge between sessions;
- depending heavily on large prompts and conversation history.

Forge aims to solve these problems by introducing an orchestration layer between the developer, coding agent, and repository.

```text
Developer
    ↓
Forge
    ↓
Context + Rules + Workflow
    ↓
Coding Agent
    ↓
Repository
```

Forge should help the coding agent answer four questions before considering work complete:

1. What is being changed?
2. What parts of the system are affected?
3. How should the change be implemented?
4. How do we verify that the implementation is correct?

---

## 3. Vision

Forge should evolve into a lightweight, extensible AI engineering platform.

The long-term direction is:

```text
Business Idea
    ↓
Requirements
    ↓
Product Specification
    ↓
Architecture
    ↓
Development Planning
    ↓
Implementation
    ↓
Testing / QA
    ↓
Deployment
```

AI may assist throughout this lifecycle, but humans remain responsible for important decisions and approvals.

Forge should prioritize **AI-assisted engineering**, not autonomous software development without oversight.

---

## 4. Core Capabilities

Forge supports two primary project entry points.

### 4.1 New Project

Forge can begin before a source-code repository or application exists.

The user provides an idea, product concept, business requirement, or initial set of requirements.

Forge helps transform that input into a structured software project foundation.

```text
Idea / Requirements
        ↓
Requirements Analysis
        ↓
Clarification
        ↓
Project Specification
        ↓
Architecture & Stack Recommendation
        ↓
Human Review
        ↓
Project Knowledge Generation
        ↓
Repository / Project Initialization
        ↓
Development Workflow
```

Forge may assist with:

- understanding the proposed application;
- identifying incomplete or ambiguous requirements;
- asking relevant clarification questions;
- defining functional requirements;
- identifying non-functional requirements;
- recommending an appropriate technology stack;
- proposing system architecture;
- identifying major components or services;
- defining development phases;
- generating persistent project context;
- preparing the project for AI-assisted implementation.

The primary output of this stage is **structured project knowledge**, not immediately generated application code.

Possible generated knowledge includes:

```text
.forge/
└── knowledge/
    ├── PROJECT.md
    ├── REQUIREMENTS.md
    ├── ARCHITECTURE.md
    └── ROADMAP.md
```

Additional project or agent instructions may be generated as the project progresses.

All important architectural and technology decisions should remain reviewable by the developer before Forge initializes or modifies the implementation.

### 4.2 Existing Project

Forge can also be introduced into an existing repository.

In this mode, Forge analyzes the current project to reconstruct enough knowledge to operate safely within it.

```text
Existing Repository
        ↓
Repository Analysis
        ↓
Technology Detection
        ↓
Architecture Discovery
        ↓
Convention / Dependency Discovery
        ↓
Project Knowledge Generation
        ↓
Human Review
        ↓
Forge Development Workflow
```

Forge may identify:

- languages;
- frameworks;
- build systems;
- repository structure;
- dependencies;
- databases;
- infrastructure;
- testing frameworks;
- architectural patterns;
- project conventions;
- existing documentation.

Forge then creates or supplements persistent project knowledge rather than requiring the developer to manually explain the entire repository.

### 4.3 Shared Development Workflow

Both entry points eventually converge into the same development workflow.

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

The generated project knowledge provides persistent context for the agents participating in this workflow.

---

## 5. Initial User Experience

Forge should initially operate primarily through a CLI.

The exact commands are provisional and may evolve as the architecture develops.

### New Project

A developer can initialize Forge without an existing application.

Conceptually:

```bash
forge init
```

Forge determines that no existing project is present and begins project discovery.

Example:

```text
Forge — New Project

Describe what you want to build:

> A fitness coaching platform where coaches can manage
> clients, create training programs, and track progress.

Forge will analyze the project requirements before
initializing the application.
```

Forge may then conduct an interactive requirements process.

After sufficient information has been collected, Forge produces a proposed project foundation:

```text
Project analysis complete.

Project Type:
  Fitness Coaching Platform

Recommended Architecture:
  Mobile Application
  Backend API
  Relational Database

Recommended Stack:
  Flutter
  Spring Boot
  PostgreSQL

Generated:
  PROJECT.md
  REQUIREMENTS.md
  ARCHITECTURE.md
  ROADMAP.md

Review required before project initialization.
```

The user may approve, reject, or modify recommendations before implementation begins.

### Existing Project

Forge can also initialize against an existing repository.

Conceptually:

```bash
forge init .
```

Forge analyzes the repository and constructs project knowledge.

Example:

```text
Existing project detected.

Language: Java 17
Framework: Spring Boot
Build: Maven
Database: PostgreSQL
Container: Docker
Deployment: Kubernetes

Architecture and project conventions analyzed.

Generated Forge project knowledge.

Review required before continuing.
```

Once either initialization path is complete, Forge can operate against development tasks.

Example:

```bash
forge analyze "Add refresh token support"
```

The task then enters the shared Forge development workflow.

---

## 6. High-Level Architecture

The initial architecture should remain small.

```text
                New Project Requirements
                         │
                         │
Existing Repository ─────┤
                         ▼
                    Forge CLI
                         │
                         ▼
                 Orchestration Layer
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
 Requirements         Context          Workflow
   Engine             Engine            Engine
        │                │                │
        └────────────────┼────────────────┘
                         │
                         ▼
                     Agent Layer
                         │
                         ▼
                  Provider Adapter
                         │
                         ▼
                  AI Provider(s)
                         │
                         ▼
                Project Knowledge
                         │
                         ▼
                    Repository
```

Major architectural areas are expected to include:

- CLI;
- requirements analysis;
- project discovery;
- repository analysis;
- context management;
- workflow orchestration;
- agent definitions;
- project rules;
- AI provider abstraction;
- validation;
- project knowledge.

Implementation details should remain modular so these areas can evolve independently.

---

## 7. Agent Model

Forge may use specialized agents rather than one unrestricted general-purpose agent.

Initial conceptual agents include:

### Requirements Analyst

Transforms an initial project idea or incomplete requirements into structured software requirements.

Responsibilities may include identifying ambiguity, asking clarification questions, discovering functional and non-functional requirements, and identifying missing information.

### Architect

Transforms approved requirements into proposed system architecture and technology recommendations.

Responsibilities may include technology-stack recommendations, component boundaries, data architecture, integration approaches, infrastructure considerations, and architectural tradeoffs.

### Analyzer

Understands the repository and determines the likely impact of a requested change.

### Planner

Transforms analysis into an actionable implementation plan.

### Developer

Executes an approved implementation plan.

### Validator

Runs appropriate project validation and interprets failures.

### Reviewer

Reviews the completed change for correctness, architecture, testing, security, and unnecessary modifications.

Agents are conceptual responsibilities.

They do not necessarily require separate AI model instances or processes. Multiple responsibilities may initially share the same underlying model while using different instructions and tools.

---

## 8. Project Knowledge

Forge should avoid sending an entire repository to an AI model whenever possible.

Project knowledge may originate from two sources.

For a new project, Forge derives knowledge from requirements discovery, developer decisions, architecture discussions, and approved recommendations.

For an existing project, Forge derives knowledge from repository analysis, existing documentation, configuration, source code, dependencies, and developer clarification.

Both approaches should eventually produce a consistent project knowledge model that Forge can use during future development tasks.

Context should be selected according to the task.

The general principle is:

```text
Task
 ↓
Determine Scope
 ↓
Find Relevant Context
 ↓
Compact Context
 ↓
Send to Agent
```

Potential context sources include:

- repository structure;
- project documentation;
- source-code relationships;
- configuration files;
- architecture documentation;
- coding conventions;
- previous architectural decisions;
- Forge project rules.

Early versions should favor simple and understandable context retrieval.

Advanced knowledge graphs, vector databases, embeddings, or complex retrieval infrastructure should only be introduced when demonstrated to be necessary.

---

## 9. Forge Project Files

A Forge-enabled repository may eventually contain a structure similar to:

```text
.forge/
├── project.yaml
├── agents/
├── skills/
├── rules/
└── knowledge/
    ├── PROJECT.md
    ├── REQUIREMENTS.md
    ├── ARCHITECTURE.md
    └── ROADMAP.md
```

### `PROJECT.md`

Defines what the product is, its purpose, users, boundaries, and high-level goals.

### `REQUIREMENTS.md`

Contains approved functional and non-functional requirements.

### `ARCHITECTURE.md`

Contains the approved system architecture, technology decisions, major components, integrations, and important architectural constraints.

### `ROADMAP.md`

Contains the high-level development phases and major project milestones.

Possible responsibilities:

### `project.yaml`

Project-level Forge configuration.

### `agents/`

Instructions for specialized agent responsibilities.

### `skills/`

Reusable engineering workflows or capabilities.

### `rules/`

Project-specific development and architectural constraints.

### `knowledge/`

Compact persistent knowledge about the project.

The exact structure is provisional and should not be treated as a finalized implementation contract.

---

## 10. Technology Direction

Forge will initially be implemented in **Python**.

Python is the implementation language of the Forge orchestration platform and does not restrict which languages Forge can operate on.

Forge should eventually support repositories using technologies such as:

- Java / Spring Boot;
- Dart / Flutter;
- JavaScript / TypeScript;
- React;
- Python;
- Go;
- other languages where suitable tooling is available.

Initial Python technologies under consideration include:

```text
Python 3.12+
Typer
Pydantic
Rich
MCP / FastMCP
Tree-sitter
Git tooling
```

These technologies are architectural candidates rather than permanent requirements until implemented and validated.

External AI providers should be accessed through abstractions where practical so Forge is not unnecessarily coupled to one model or vendor.

---

## 11. Engineering Principles

Forge development should follow these principles.

### Human Controlled

AI assists engineering decisions but does not silently expand project scope.

Important changes should remain reviewable by the developer.

### Understand Before Implementing

Forge should gather sufficient repository and task context before modifying code.

### Plan Before Modification

Complex changes should have an explicit implementation plan before execution.

### Minimal Relevant Context

Provide agents with the context required for the current task rather than indiscriminately loading the repository.

### Scope Discipline

Implementation should remain within the approved task and plan.

### Validate Before Completion

Generated code should not be considered complete simply because files were successfully modified.

### Repository-Aware

Forge should respect the architecture, conventions, dependencies, and existing patterns of the repository it operates on.

### Language Independent

Forge's orchestration architecture should not assume that target projects use Python.

Language-specific behavior should be isolated behind appropriate adapters or tooling.

### Provider Independent

Core Forge architecture should avoid unnecessary dependence on a single AI provider.

### Start Simple

Do not introduce distributed systems, vector databases, knowledge graphs, multi-agent swarms, web dashboards, or other infrastructure until there is a demonstrated need.

---

## 12. Security Principles

Forge operates against source-code repositories and must treat repository contents carefully.

Forge should:

- never intentionally collect credentials;
- never expose secrets in prompts or logs unnecessarily;
- detect or avoid sensitive files where practical;
- avoid modifying secret-management files without explicit reason;
- avoid committing credentials or tokens;
- make consequential repository changes visible to the developer;
- clearly separate generated recommendations from executed actions.

Future integrations with external services should follow least-privilege principles.

---

## 13. Out of Scope for Initial Versions

Forge may analyze software requirements and generate project specifications, but the initial versions will not attempt to automate an organization's entire business or product-management lifecycle.

The following remain intentionally excluded from the initial implementation:

- enterprise business-process automation;
- autonomous business decision-making;
- complete product-management replacement;
- UI/UX generation;
- autonomous production deployment;
- production infrastructure management;
- complex knowledge graphs;
- vector databases;
- cloud-hosted Forge services;
- web dashboards;
- large multi-agent swarms;
- fully autonomous development.

Forge should first prove that requirements can be transformed into reliable project knowledge and then into controlled software development.

---

## 14. Initial Development Milestones

Forge development should establish project understanding before attempting AI-controlled code modification.

Each milestone should build toward the complete Forge workflow while remaining independently testable.

### V0.1 — Forge Foundation

**Goal:** Establish the core Forge application, CLI, configuration model, and internal architecture.

Target capabilities:

- establish the Python project and CLI;
- define the Forge project model;
- define configuration handling;
- establish the orchestration architecture;
- create the initial `.forge/` structure;
- distinguish between new-project and existing-project initialization;
- establish the foundation for AI provider integration.

V0.1 should focus on Forge itself rather than advanced AI behavior.

### V0.2 — New Project Discovery

**Goal:** Transform an initial software idea or incomplete requirements into structured project requirements.

Target capabilities:

- accept an initial project idea or requirements;
- identify missing or ambiguous information;
- conduct structured requirements clarification;
- identify intended users and major use cases;
- derive functional requirements;
- derive relevant non-functional requirements;
- identify project boundaries and constraints;
- produce structured requirements for human review.

```text id="eyv85v"
Idea
 ↓
Requirements Analysis
 ↓
Clarification
 ↓
Structured Requirements
 ↓
Human Review
```

No application implementation should occur during this milestone.

### V0.3 — Project Knowledge Generation

**Goal:** Transform approved requirements into persistent project knowledge and an initial technical foundation.

Target capabilities:

- generate `PROJECT.md`;
- generate `REQUIREMENTS.md`;
- recommend an appropriate technology stack;
- propose high-level system architecture;
- explain important architectural tradeoffs;
- generate `ARCHITECTURE.md`;
- identify major development phases;
- generate `ROADMAP.md`;
- allow human review and modification before decisions are finalized.

```text id="mtwmqe"
Approved Requirements
        ↓
Architecture Analysis
        ↓
Stack Recommendation
        ↓
Human Review
        ↓
Project Knowledge
```

At completion, Forge should have enough approved context to prepare the actual software project for development.

### V0.4 — Existing Project Discovery

**Goal:** Allow Forge to understand an existing software repository and construct compatible project knowledge.

Target capabilities:

- inspect repository structure;
- detect languages and frameworks;
- detect build systems;
- identify major dependencies;
- detect databases and infrastructure where possible;
- discover testing frameworks;
- inspect existing documentation;
- identify architectural patterns and project conventions;
- reconstruct project knowledge;
- identify information that cannot be reliably inferred;
- request developer clarification where necessary;
- generate or supplement Forge knowledge files.

```text id="ydyj64"
Existing Repository
        ↓
Repository Analysis
        ↓
Technology & Architecture Discovery
        ↓
Project Knowledge
        ↓
Human Review
```

V0.3 and V0.4 should ultimately produce a compatible project knowledge model regardless of whether Forge started from a new idea or an existing repository.

### V0.5 — Task Analysis

**Goal:** Use project knowledge to understand a requested engineering change before planning implementation.

Conceptually:

```bash id="ukzzte"
forge analyze "<task>"
```

Target capabilities:

- interpret the requested task;
- retrieve relevant project knowledge;
- identify relevant files and components;
- determine dependencies and relationships;
- identify applicable project rules;
- estimate the change surface;
- identify potential architectural impact;
- identify missing information;
- produce a structured task analysis.

```text id="ofecq6"
Task
 ↓
Project Knowledge
 ↓
Relevant Context
 ↓
Change-Surface Analysis
 ↓
Task Analysis
```

### V0.6 — Planning

**Goal:** Transform an approved task analysis into a concrete implementation plan.

Conceptually:

```bash id="m8mknn"
forge plan
```

Target capabilities:

- define proposed modifications;
- identify affected files or components;
- define expected behavior;
- define acceptance criteria;
- identify required tests;
- identify implementation risks;
- identify architectural concerns;
- present the complete plan for human approval.

No code modification should occur during planning.

```text id="aiprvn"
Task Analysis
      ↓
Implementation Plan
      ↓
Human Review
      ↓
Approved Plan
```

### V0.7 — Implementation

**Goal:** Execute an approved implementation plan through a coding agent while maintaining scope control.

Target capabilities:

- integrate with an AI coding provider;
- provide the coding agent with relevant project context;
- execute approved modifications;
- minimize unnecessary context loading;
- track modified files;
- detect significant deviations from the approved plan;
- require reconsideration when implementation discovers significant new scope.

Implementation should operate from the approved plan rather than directly from the original user prompt.

```text id="abgzev"
Approved Plan
      ↓
Relevant Context
      ↓
Coding Agent
      ↓
Repository Changes
```

### V0.8 — Validation & Review

**Goal:** Determine whether the implementation works and whether the completed change satisfies the approved plan.

Target capabilities:

- detect appropriate validation commands;
- compile or build the project where applicable;
- execute automated tests;
- execute linting or static analysis where available;
- interpret validation failures;
- verify acceptance criteria;
- review modified code;
- identify unintended changes;
- identify architectural violations;
- identify security concerns;
- identify missing tests;
- generate a final change summary.

```text id="onl9yd"
Implementation
      ↓
Validation
      ↓
Tests / Build / Analysis
      ↓
Review
      ↓
PASS ─────────────→ DONE
 │
 FAIL
 │
 ▼
Implementation Reconsideration
```

A failed validation should not automatically terminate the task.

Forge may eventually support controlled implementation-validation loops, but automatic retries should be designed separately and remain bounded by the approved scope.

---

## 15. Future Direction

After the core developer workflow is stable, Forge may expand outward into additional SDLC phases.

Possible future lifecycle:

```text
Business
 ↓
Requirements
 ↓
Product
 ↓
Architecture
 ↓
Planning
 ↓
Development
 ↓
Testing
 ↓
Deployment
```

Potential future capabilities include:

- requirements agents;
- architecture agents;
- ADR generation;
- task decomposition;
- QA planning;
- CI/CD assistance;
- deployment review;
- project retrospectives;
- persistent engineering knowledge;
- MCP integrations;
- IDE integrations.

These are future directions rather than current requirements.

---

## 16. Source of Truth

Forge development should distinguish between three forms of context:

```text
FORGE.md
    ↓
What are we building?

Repository
    ↓
What currently exists?

Current Task / Conversation
    ↓
What are we changing now?
```

This document defines the project's stable vision, scope, principles, and high-level architecture.

It should **not** become a running implementation log.

Detailed implementation information should live in the repository and, when necessary, dedicated technical documentation.

When a major architectural decision changes the meaning of Forge, this document should be updated.

---

## 17. Current Status

**Project:** Forge  
**Status:** Planning / Foundation  
**Primary implementation language:** Python  
**Initial interface:** CLI  
**Initial focus:** AI-assisted software project initialization and development orchestration

Forge has two primary entry points:

1. **New Project** — transform an idea or requirements into an approved project specification, architecture, technology stack, roadmap, and persistent project knowledge.

2. **Existing Project** — analyze an existing repository and reconstruct the project knowledge necessary for Forge-assisted development.

Both entry points converge into the Forge development workflow:

```text
Project Knowledge
       ↓
Analyze Task
       ↓
Plan
       ↓
Human Approval
       ↓
Implement
       ↓
Validate
       ↓
Review
```

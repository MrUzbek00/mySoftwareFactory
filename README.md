# Software Factory Skills

`software-factory-skills` is a reusable skills library for controlled AI
software-engineering workflows. It defines small, auditable procedures that
future coding agents can follow before they are allowed to modify code.

The current repository implements only the first three stages:

```text
Task
  |
  v
inspect-repository
  |
  v
plan-change
  |
  v
isolate-task
  |
  v
STOP
```

Implementation, validation, pull requests, and review automation are
deliberately outside this MVP.

## What This Repository Is

This repository is a foundational skills layer for a future AI Software
Factory. It contains operational instructions, structured output contracts,
schemas, safety rules, examples, and deterministic scripts that future agents
can use as building blocks.

## What This Repository Is Not

This repository is not:

- an AI coding agent
- a multi-agent orchestration system
- an LLM framework
- a CI/CD platform
- a production deployment system

## Architecture

```text
Future Software Factory

PM / Orchestrator
        |
        v
Engineering Worker
        |
        v
software-factory-skills
        |
        v
Repository / Git / Tooling
```

Skills define repeatable procedures. Future roles and orchestration systems can
decide which skills an agent may use for a task.

## Current Skills

| Skill | Purpose |
| --- | --- |
| `inspect-repository` | Collect task-relevant repository context without loading unrelated code. |
| `plan-change` | Convert a task request and repository context into a structured engineering plan. |
| `isolate-task` | Create a safe branch and Git worktree before implementation begins. |

## Future Skills

The repository is structured so later phases can add:

- `implement-change`
- `validate-change`
- `before-after`
- `create-pull-request`
- `review-pull-request`
- `revise-pull-request`
- `security-review`
- `update-documentation`
- `completion-report`

These are intentionally not implemented yet.

## Design Principles

- deterministic where possible
- structured outputs
- least privilege
- isolated workspaces
- small context windows
- auditable execution
- explicit failure
- human escalation

LLM reasoning is used for understanding requirements, identifying relevant
architecture, planning changes, classifying risk, and reporting unknowns.
Deterministic software is used for Git operations, schema validation, file
validation, and other procedures where code can reliably enforce rules.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Run the full local check before considering a change complete:

```bash
ruff check .
pytest
```

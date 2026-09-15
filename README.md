# Software Factory Skills

`software-factory-skills` is a reusable skills library for controlled AI
software-engineering workflows. It defines small, auditable procedures that
future coding agents can follow before they are allowed to modify code.

The repository implements the full task pipeline, from an unfamiliar repository
to a reviewed pull request:

```text
Task
  |
  v
inspect-repository
  |
  v
plan-change            [approval gate if HIGH/CRITICAL]
  |
  v
isolate-task
  |
  v
implement-change
  |
  v
validate-change        [gate: must pass]
  |
  +--> before-after           (optional)
  +--> security-review        [gate: no CRITICAL]
  +--> update-documentation   (optional)
  |
  v
create-pull-request
  |
  +--> review-pull-request    (optional, read-only)
  +--> revise-pull-request    (optional, loops back to validate)
  |
  v
completion-report
  |
  v
STOP
```

Merging, approving, and deployment are deliberately outside this pipeline. A
human owns the merge.

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
| `implement-change` | Execute an approved plan inside the task worktree and commit it. |
| `validate-change` | Run checks and capture real commands, exit codes, and output. |
| `before-after` | Run the same probes at the base commit and the task head. |
| `security-review` | Scan added lines for secrets, dangerous sinks, and new dependencies. |
| `update-documentation` | Correct documentation the change made untrue. |
| `create-pull-request` | Push the branch and open one pull request with that evidence. |
| `review-pull-request` | Read an open pull request and report findings. Read-only. |
| `revise-pull-request` | Address feedback with fast-forward commits. Never rewrites. |
| `completion-report` | Validate every artifact and report contradictions between them. |

## Deterministic Scripts

Operations that software can enforce are handled by scripts rather than by
model-generated shell commands:

| Script | Enforces |
| --- | --- |
| `isolate-task/scripts/create_worktree.py` | safe branch naming, clean tree, no overwrite |
| `validate-change/scripts/run_validation.py` | real commands, real exit codes, real output |
| `before-after/scripts/capture_before_after.py` | both sides measured, scratch worktree cleaned up |
| `security-review/scripts/scan_diff.py` | added lines only, secrets redacted on match |
| `create-pull-request/scripts/open_pull_request.py` | no force push, no protected head, one PR |
| `review-pull-request/scripts/fetch_pull_request.py` | read-only; cannot approve, merge, or comment |
| `revise-pull-request/scripts/push_revision.py` | fast-forward only; refuses a diverged branch |
| `completion-report/scripts/build_report.py` | schema validation and cross-artifact checks |

## Out of Scope

These remain deliberately unimplemented, and are not a roadmap gap:

- merging or approving a pull request
- enabling auto-merge or dismissing reviews
- deploying, releasing, or touching production
- modifying branch protection or repository settings

Each is a human decision that this pipeline deliberately stops short of.

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

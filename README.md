# Software Factory Skills

`software-factory-skills` is a reusable skills library for controlled AI
software-engineering workflows. It defines small, auditable procedures that
future coding agents can follow before they are allowed to modify code.

The repository implements the full task pipeline, from an unfamiliar repository
to a reviewed pull request:

```text
Technical requirements document      (project input, optional layer)
  |
  v
start-from-spec
  |
  +--> ingest-requirements    traceable requirements, unknowns, conflicts
  +--> clarify-project        [gate: user confirms the project context]
  +--> decompose-spec         [gate: user approves the backlog]
  |
  v
prepare-task                  [gate: only a READY task passes]
  |
  v
Task                                 (scoped input, enters here directly)
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

Specification intake turns a project-level document into scoped work. It runs
only when the input is a specification; a single ticket skips it entirely.

| Skill | Purpose |
| --- | --- |
| `start-from-spec` | Route a specification to a new project, a resume, or an amendment. |
| `ingest-requirements` | Extract traceable requirements, unknowns, and conflicts from the source document. |
| `clarify-project` | Run the mandatory intake interview and produce a confirmed project context. |
| `decompose-spec` | Turn confirmed requirements into epics, features, and implementation-sized tasks. |
| `prepare-task` | Hand one READY task to the engineering workflow, refusing anything else. |

Engineering takes one scoped task from an unfamiliar repository to a reviewed
pull request.

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
| `decompose-spec/scripts/check_backlog.py` | resolvable references, acyclic dependencies, honest readiness |
| `prepare-task/scripts/prepare_task.py` | one task, READY only, confirmed context, approved backlog |
| `isolate-task/scripts/create_worktree.py` | safe branch naming, clean tree, no overwrite |
| `validate-change/scripts/run_validation.py` | real commands, real exit codes, real output, blocking quality findings |
| `before-after/scripts/capture_before_after.py` | both sides measured, scratch worktree cleaned up |
| `security-review/scripts/scan_diff.py` | added lines only, secrets redacted on match |
| `create-pull-request/scripts/open_pull_request.py` | no force push, no protected head, one PR |
| `review-pull-request/scripts/fetch_pull_request.py` | read-only; cannot approve, merge, or comment |
| `revise-pull-request/scripts/push_revision.py` | fast-forward only; refuses a diverged branch |
| `completion-report/scripts/build_report.py` | schema validation and cross-artifact checks |

## Starting a Project From a Specification

Point the factory at a technical requirements document:

```text
Use this technical requirements document: docs/requirements.docx
Start a new Software Factory project from it.
```

What happens, in order:

1. The document is read. If it cannot be opened, the factory asks for a readable
   copy rather than guessing at its contents.
2. Requirements are extracted with source coordinates — document, section,
   subsection, page — and classified. Ambiguities become unknowns and
   contradictions become conflicts, rather than being resolved silently.
3. A mandatory intake interview asks, in one batch, only what the document does
   not already answer. Where the document names a stack, the question is whether
   that stack is binding, not what stack to use.
4. A `PROJECT INTAKE SUMMARY` is presented. Nothing proceeds until it is
   confirmed.
5. The requirements are decomposed into epics, features, and tasks, each
   traceable back to the requirements it implements, with dependencies and a
   readiness state.
6. The backlog is presented. Nothing is implemented until it is approved.
7. One `READY` task at a time is handed to the existing workflow.

Project state lives under `.factory/`, outside the repository being built:

```text
.factory/
  project.json        project context, decisions, amendment history
  requirements.json   requirements index, unknowns, conflicts
  backlog.json        epics, features, tasks, dependencies, readiness
  tasks/<TASK-ID>/    task handoff and the per-task stage artifacts
```

The source document is not copied into the artifacts. It stays the source of
truth where it is, and the artifacts reference it.

## Resuming and Amending

```text
Continue the Uz-Koram project.
```

Existing artifacts are loaded, status is reported, and only newly relevant
questions are asked. The interview is not repeated.

```text
The customer changed requirement 4.8.
Use this new version of the requirements document.
```

The change is recorded as an amendment with its own identifier and impact
analysis: affected requirements, decisions, tasks, and completed work. Tasks that
depended on changed requirements leave `READY`. Earlier decisions are superseded
by new ones, never rewritten.

`examples/spec-driven-project.md` walks through the whole path, including what
the readiness gate refuses and why.

## Coding Standards

`standards/` holds criteria that several stages share, rather than instructions
belonging to one stage.

| Standard | Applied by | Checked by |
| --- | --- | --- |
| `standards/backend-code-quality.md` | `implement-change` | `validate-change`, `review-pull-request` |

The backend standard exists so that code the factory produces can be understood
without reverse-engineering it: human-readable names, explicit input and return
types, explicit nullability, typed collections, documentation where a signature
cannot carry the contract, and comments that explain why rather than what.

It is deliberately not a style guide. Framework conventions, the repository's
existing architecture, and the project's domain language all take precedence,
and a subjective naming preference can never fail a change.

Enforcement is split the way the rest of the pipeline splits it. A model judges
whether `$data` is a meaningful name, because no linter can. The script decides
whether the change proceeds:

```bash
python validate-change/scripts/run_validation.py \
  --worktree /path/to/worktrees/TASK-123-password-reset \
  --task-id TASK-123 --base origin/main --auto \
  --quality-review /artifacts/TASK-123/quality-review.json
```

A `BLOCKING` finding fails validation and blocks the pull request. An `ADVISORY`
finding is recorded and reported, and changes nothing.

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

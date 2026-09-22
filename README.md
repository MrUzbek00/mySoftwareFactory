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

## Documentation

`AGENTS.md` is the normative document. It states the rules an agent must
follow, and no other document restates them.

| Document | Covers |
| --- | --- |
| `AGENTS.md` | the rules: routing, mandatory workflow, what agents must and must not do |
| `docs/pipeline.md` | each stage, what it produces, and why each gate is where it is |
| `docs/architecture.md` | how skills, scripts, schemas, and standards fit together |
| `docs/schemas.md` | the schema index: which stage writes each artifact contract |
| `docs/running-a-project.md` | a specification to a completion report, end to end |
| `standards/backend-code-quality.md` | the criteria backend code the factory writes must satisfy |
| `docs/examples/` | two worked examples, one per entry point |

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

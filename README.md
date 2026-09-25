# MySoftware Factory

`my-software-factory` is a reusable skills library for controlled AI
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

This repository is the foundational skills layer for MySoftware Factory. It contains operational instructions, structured output contracts,
schemas, safety rules, examples, and deterministic scripts that future agents
can use as building blocks.

## What This Repository Is Not

This repository is not:

- an AI coding agent
- a multi-agent orchestration system
- an LLM framework
- a CI/CD platform
- a production deployment system

## Repository Layout

```text
SKILL.md                 root router: installs the repository as one skill
AGENTS.md                the normative rules for agent behavior
agents/openai.yaml       Codex UI metadata for the skill
skills/
  intake/                5 stages: a specification to READY tasks
  engineering/           12 stages: one task to a reviewed pull request
schemas/                 artifact contracts, one file per artifact
standards/               criteria shared by several stages
tools/
  factory-map/           the local pipeline map
  installer/             installs the skill for Claude Code and Codex
docs/                    explanation, walkthroughs, and indexes
tests/                   the suite that holds the structure in place
```

Each stage directory holds `SKILL.md`, `references/`, and, where software can
enforce part of the stage, `scripts/`.

## Current Skills

Specification intake, in `skills/intake/`, turns a project-level document into scoped work. It runs
only when the input is a specification; a single ticket skips it entirely.

| Skill | Purpose |
| --- | --- |
| `start-from-spec` | Route a specification to a new project, a resume, or an amendment. |
| `ingest-requirements` | Extract traceable requirements, unknowns, and conflicts from the source document. |
| `clarify-project` | Run the mandatory intake interview and produce a confirmed project context. |
| `decompose-spec` | Turn confirmed requirements into epics, features, and implementation-sized tasks. |
| `prepare-task` | Hand one READY task to the engineering workflow, refusing anything else. |

Engineering, in `skills/engineering/`, takes one scoped task from an unfamiliar repository to a reviewed
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

## Install as a Skill

The repository root is also one installable skill, `my-software-factory`.
Its `SKILL.md` routes a request to the right stage, and the same files work in
Claude Code and in OpenAI Codex. `agents/openai.yaml` adds Codex's UI metadata,
and Claude Code ignores it.

```bash
python tools/installer/scripts/install_skill.py --dry-run   # show what would be written
python tools/installer/scripts/install_skill.py             # install for both agents
```

By default it installs into `~/.claude/skills/my-software-factory` and
`~/.codex/skills/my-software-factory`. `CLAUDE_CONFIG_DIR` and `CODEX_HOME`
change those locations. `--target claude` or `--target codex` installs for one
agent only, and `--skills-dir PATH` installs into a directory you name, such as
a project's `.claude/skills`.

The installer copies an allowlist: the router, `skills/`, `schemas/`,
`standards/`, `docs/`, `tools/factory-map/`, and `AGENTS.md`. Tests, CI,
packaging files, and the installer itself are not installed. It refuses to overwrite an existing
directory. Pass `--replace` to update a previous install; it still refuses to
replace any directory that is not this skill. Each install records its source
commit in `.install.json`. Re-run the installer after pulling changes, because
installed copies do not update themselves.

This skill was called `software-factory-gpt` before. The installer reports an
install under that name in `legacy_installs` but never deletes it. Remove it
yourself, or both skills will load side by side.

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
| `tools/factory-map/README.md` | the local pipeline map: how to run it, how it derives state |

## Pipeline Map

`tools/factory-map/` serves an interactive map of the pipeline on the loopback
interface. It draws the seventeen stages, the seven gates, and the state of
each one, derived from the files on disk at request time.

```bash
python tools/factory-map/scripts/serve_map.py --port 8787
```

Without a `.factory` directory it reports how completely each stage is built.
With one, it reports where a task has actually got to, and every status names
the file and the field it came from. It is read-only: it writes nothing, runs
no pipeline stage, and stops at showing you what is there.

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

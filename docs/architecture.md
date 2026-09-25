# Architecture

How the parts of this repository fit together, where each kind of file lives,
and why the boundaries are where they are.

## Where the Skills Sit

```text
MySoftware Factory

PM / Orchestrator
        |
        v
Engineering Worker
        |
        v
my-software-factory (these skills)
        |
        v
Repository / Git / Tooling
```

Skills define repeatable procedures. They do not decide which procedure runs.
A future orchestrator decides which skills an agent may use for a task, and the
skill decides what that agent is allowed to do once it starts.

## Three Layers Per Stage

Every stage of the pipeline is built from the same three pieces, and the split
between them is the central design decision in this repository.

| Layer | File | Answers |
| --- | --- | --- |
| Procedure | `stages/<phase>/<stage>/SKILL.md` | what the model should understand, decide, and report |
| Enforcement | `stages/<phase>/<stage>/scripts/*.py` | what software can check without trusting the model |
| Contract | `schemas/*.schema.json` | what the stage's output must contain to count |

Paths in this table are relative to the skill folder, `my-software-factory/`. A
fourth piece, `stages/<phase>/<stage>/references/*.md`, holds the detail a model
needs only while that stage runs. Keeping it out of `SKILL.md` keeps the context
a stage loads small.

The split follows what each layer can be trusted with. A model can judge
whether `$data` is a meaningful variable name, and no linter can. A model
cannot be trusted to report its own exit codes, and a script can. So judgement
is a prompt, and consequence is code.

## Repository Layout

The repository holds one skill and the project that maintains it. They are kept
apart so that installing the skill means copying one folder, and so that nothing
an agent needs at run time depends on files that are not installed.

```text
my-software-factory/     the skill, and everything an agent needs to run it
  SKILL.md               the router
  agents/openai.yaml     Codex UI metadata
  stages/
    intake/              5 stages: a specification to READY tasks
    engineering/         12 stages: one task to a reviewed pull request
  schemas/               artifact contracts, one file per artifact
  standards/             criteria shared by several stages
  examples/              worked examples, one per entry point

AGENTS.md                the normative rules for agent behavior
README.md                entry point and orientation
tools/
  factory-map/           the local pipeline map
  installer/             installs the skill for Claude Code and Codex
docs/                    explanation for maintainers
tests/                   the suite that holds the structure in place
.github/workflows/       continuous integration

my-software-factory/stages/<phase>/<stage>/   one directory per stage, 17 in total
  SKILL.md               the procedure, and the only file the glob matches
  references/*.md        stage detail, loaded only while that stage runs
  scripts/*.py           the deterministic part of the stage
```

`AGENTS.md` stays at the repository root because agents working in this
repository load it from there automatically. The installer copies it into every
installed skill, so the rules travel with the skill without a second copy in the
repository.

Stages are grouped by the phase they belong to. Intake runs only for a
project-level specification and ends at a READY task; engineering takes one
task to a pull request. The directory name is still the stage name, and the
stage's frontmatter `name` must match it.

Run state is not in this list. Project context, requirements, backlog, and
per-task artifacts live under `.factory/` in the repository being built, which
is gitignored here and never committed. The pipeline that produces evidence and
the repository that defines the pipeline stay separate.

## Where Non-Skill Tooling Goes

A skill is a procedure an agent follows. A tool is something a person or a
script runs. They are not the same thing, and this repository keeps them apart
by a rule that is enforced rather than remembered.

`tests/test_skill_metadata.py` asserts the exact stages in each phase against
the `my-software-factory/stages/*/*/SKILL.md` glob. It also asserts that the
only other `SKILL.md` is the router at the top of the skill folder. The skills namespace is therefore closed by test: an eighteenth
stage, or a stage in the wrong phase, fails the suite until someone changes that
list on purpose.

Non-skill tooling lives under `tools/`, outside the skill folder, and carries no
`SKILL.md`.
That single rule keeps the glob honest, keeps the skills catalogue meaningful,
and lets a tool be added without arguing about whether it is a skill.

`tools/factory-map/` is the first tool to follow it. It serves an interactive
map of the pipeline on the loopback interface, deriving each stage's state from the
files on disk rather than from anything written into the page. It reads the
repository and the run-state directory and writes to neither.
`tools/factory-map/README.md` documents what each status means and which file
and field produces it.

`factory-map` stays out of the skill on purpose. It reads the repository's
`tests/` and `docs/architecture.md` to report how completely each stage is
built, and an installed skill has neither.

`tools/installer/` is the second. It copies `my-software-factory/`, plus
`AGENTS.md` and `LICENSE`, into the skills directories that Claude Code and
Codex scan. It refuses to overwrite anything that is not a previous install of
this skill.

The router, `my-software-factory/SKILL.md`, is not a stage, and the stage glob
never matches it. It routes a request to the stage where it belongs. The
procedures stay in the stage files, so an agent loads a single stage file at a
time.

## Deterministic Scripts

Operations that software can enforce are handled by scripts rather than by
model-generated shell commands.

| Script | Enforces |
| --- | --- |
| `my-software-factory/stages/intake/decompose-spec/scripts/check_backlog.py` | resolvable references, acyclic dependencies, honest readiness |
| `my-software-factory/stages/intake/prepare-task/scripts/prepare_task.py` | one task, READY only, confirmed context, approved backlog |
| `my-software-factory/stages/engineering/isolate-task/scripts/create_worktree.py` | safe branch naming, clean tree, no overwrite |
| `my-software-factory/stages/engineering/validate-change/scripts/run_validation.py` | real commands, real exit codes, real output, blocking quality findings |
| `my-software-factory/stages/engineering/before-after/scripts/capture_before_after.py` | both sides measured, scratch worktree cleaned up |
| `my-software-factory/stages/engineering/security-review/scripts/scan_diff.py` | added lines only, secrets redacted on match |
| `my-software-factory/stages/engineering/create-pull-request/scripts/open_pull_request.py` | no force push, no protected head, one PR |
| `my-software-factory/stages/engineering/review-pull-request/scripts/fetch_pull_request.py` | read-only; cannot approve, merge, or comment |
| `my-software-factory/stages/engineering/revise-pull-request/scripts/push_revision.py` | fast-forward only; refuses a diverged branch |
| `my-software-factory/stages/engineering/completion-report/scripts/build_report.py` | schema validation and cross-artifact checks |

Every script is dependency-free at runtime. `pyproject.toml` declares
`dependencies = []`, and the test and lint tooling lives in the `dev` extra, so
a factory can run a script without installing anything this repository chose.

## Standards

`my-software-factory/standards/` holds criteria that several stages share, rather than instructions
belonging to one stage.

| Standard | Applied by | Checked by |
| --- | --- | --- |
| `my-software-factory/standards/backend-code-quality.md` | `implement-change` | `validate-change`, `review-pull-request` |

The backend standard exists so that code the factory produces can be understood
without reverse-engineering it: human-readable names, explicit input and return
types, explicit nullability, typed collections, documentation where a signature
cannot carry the contract, and comments that explain why rather than what.

It is deliberately not a style guide. Framework conventions, the repository's
existing architecture, and the project's domain language all take precedence,
and a subjective naming preference can never fail a change.

Enforcement is split the way the rest of the pipeline splits it. The model
produces the review; the script decides whether the change proceeds:

```bash
python my-software-factory/stages/engineering/validate-change/scripts/run_validation.py \
  --worktree /path/to/worktrees/TASK-123-password-reset \
  --task-id TASK-123 --base origin/main --auto \
  --quality-review /artifacts/TASK-123/quality-review.json
```

A `BLOCKING` finding fails validation and blocks the pull request. An `ADVISORY`
finding is recorded and reported, and changes nothing.

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

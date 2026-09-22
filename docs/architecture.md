# Architecture

How the parts of this repository fit together, where each kind of file lives,
and why the boundaries are where they are.

## Where the Skills Sit

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

Skills define repeatable procedures. They do not decide which procedure runs.
A future orchestrator decides which skills an agent may use for a task, and the
skill decides what that agent is allowed to do once it starts.

## Three Layers Per Stage

Every stage of the pipeline is built from the same three pieces, and the split
between them is the central design decision in this repository.

| Layer | File | Answers |
| --- | --- | --- |
| Procedure | `<stage>/SKILL.md` | what the model should understand, decide, and report |
| Enforcement | `<stage>/scripts/*.py` | what software can check without trusting the model |
| Contract | `schemas/*.schema.json` | what the stage's output must contain to count |

A fourth piece, `<stage>/references/*.md`, holds the detail a model needs only
while that stage runs. Keeping it out of `SKILL.md` keeps the context a stage
loads small.

The split follows what each layer can be trusted with. A model can judge
whether `$data` is a meaningful variable name, and no linter can. A model
cannot be trusted to report its own exit codes, and a script can. So judgement
is a prompt, and consequence is code.

## Repository Layout

```text
AGENTS.md                the normative rules for agent behavior
README.md                entry point and orientation
standards/               criteria shared by several stages
schemas/                 artifact contracts, one file per artifact
docs/                    explanation, walkthroughs, and indexes
factory-map/             tooling: the local pipeline map
tests/                   the suite that holds the structure in place
.github/workflows/       continuous integration

<stage>/                 one directory per skill, 17 in total
  SKILL.md               the procedure, and the only file the glob matches
  references/*.md        stage detail, loaded only while that stage runs
  scripts/*.py           the deterministic part of the stage
```

Run state is not in this list. Project context, requirements, backlog, and
per-task artifacts live under `.factory/` in the repository being built, which
is gitignored here and never committed. The pipeline that produces evidence and
the repository that defines the pipeline stay separate.

## Where Non-Skill Tooling Goes

A skill is a procedure an agent follows. A tool is something a person or a
script runs. They are not the same thing, and this repository keeps them apart
by a rule that is enforced rather than remembered.

`tests/test_skill_metadata.py` asserts the exact sorted list of the 17 skill
directories against the `*/SKILL.md` glob. The skills namespace is therefore
closed by test: an eighteenth top-level directory containing a `SKILL.md` fails
the suite until someone changes that list on purpose.

Non-skill tooling gets its own top-level directory and carries no `SKILL.md`.
That single rule keeps the glob honest, keeps the skills catalogue meaningful,
and lets a tool be added without arguing about whether it is a skill.

`factory-map/` is the first tool to follow it. It serves an interactive map of
the pipeline on the loopback interface, deriving each stage's state from the
files on disk rather than from anything written into the page. It reads the
repository and the run-state directory and writes to neither.
`factory-map/README.md` documents what each status means and which file and
field produces it.

## Deterministic Scripts

Operations that software can enforce are handled by scripts rather than by
model-generated shell commands.

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

Every script is dependency-free at runtime. `pyproject.toml` declares
`dependencies = []`, and the test and lint tooling lives in the `dev` extra, so
a factory can run a script without installing anything this repository chose.

## Standards

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

Enforcement is split the way the rest of the pipeline splits it. The model
produces the review; the script decides whether the change proceeds:

```bash
python validate-change/scripts/run_validation.py \
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

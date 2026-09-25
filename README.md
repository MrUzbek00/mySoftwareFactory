# MySoftware Factory

**A skill that makes an AI coding agent work like a careful engineer.** It
carries a change from a request (or a whole requirements document) to a
reviewed pull request, one checked step at a time. It then stops and leaves the
merge to you.

It works in **Claude Code** and in **OpenAI Codex**, from the same files.

---

## Why use it

AI coding agents are fast, but left alone they tend to:

- edit your main branch directly, or mix unrelated changes together,
- say "all tests pass" without having run them,
- guess at requirements instead of asking,
- turn a 40-page specification into one giant change.

MySoftware Factory gives the agent a fixed procedure that prevents this:

| Instead of... | the agent... |
| --- | --- |
| editing your checkout | works on its own branch, in a separate Git worktree |
| claiming checks passed | runs them through a script that records the real command, exit code, and output |
| guessing | writes down what it does not know and asks you |
| one huge change | splits a specification into small, traceable tasks, one pull request each |
| deciding for you | stops at gates for your approval, and never merges or deploys |

Every step leaves a small JSON record, so afterwards you can see what was
planned, what ran, and what the result was.

---

## Quick start

### What you need

- **Python 3.12 or newer.** The skill's scripts use only the standard library.
- **Git.**
- **GitHub CLI (`gh`), logged in** (`gh auth login`). This is only needed for
  the steps that push branches and open or review pull requests.
- **Claude Code** or **OpenAI Codex**, or both.
- *Optional:* `pip install jsonschema` makes the record checks complete rather
  than basic.

### 1. Install the skill

Clone this repository and run the installer from its root:

```bash
git clone https://github.com/MrUzbek00/mySoftwareFactory.git
cd mySoftwareFactory

python tools/installer/scripts/install_skill.py --dry-run   # preview, writes nothing
python tools/installer/scripts/install_skill.py             # install for Claude Code and Codex
```

This copies the skill to `~/.claude/skills/my-software-factory` and
`~/.codex/skills/my-software-factory`. Start a new agent session afterwards so
it picks the skill up.

| To... | Add |
| --- | --- |
| install for one agent only | `--target claude` or `--target codex` |
| install into one project only | `--skills-dir path/to/project/.claude/skills` |
| update an existing install | `--replace` |

The installer respects `CLAUDE_CONFIG_DIR` and `CODEX_HOME` if you have moved
those folders. On Windows, use `py -3` in place of `python` if `python` is not
found.

### 2. Use it

Open your own project in the agent and describe the work. The agent uses the
skill when the request fits, or you can name the skill directly.

**Claude Code**

```text
/my-software-factory Add a --below N option to the `list` command so it only
shows items whose quantity is below N. Take it as far as a pull request.
```

**Codex**

```text
$my-software-factory Customers say `value` crashes when an item has no price.
Fix it; items with no price should count as 0.
```

**A whole specification**

```text
/my-software-factory Here is the client's requirements document:
docs/booking-spec.pdf. It's a new project. Turn it into work for the team.
```

### 3. What happens next

For a single task, the agent:

1. gives the task an ID such as `TASK-001`, reads the relevant code, and writes
   a plan,
2. **asks for your approval if the plan is high-risk**,
3. creates a branch such as `feature/TASK-001-list-below` in a separate
   worktree, leaving your checkout untouched,
4. makes the change with tests, then runs the checks through a script and
   scans the change for secrets,
5. opens **one** pull request with the evidence, as a draft when the change is
   risky,
6. writes a completion report, and **stops**. You review and merge.

For a specification, it first extracts the requirements and **interviews you**
about what the document leaves open. It then proposes a backlog of small tasks
for **your approval**, and only then starts on the tasks, one at a time.

If the agent stops to ask you something, that is by design. See
[Troubleshooting](#troubleshooting).

---

## How it works

### Two ways in

| You bring | It starts at | First result |
| --- | --- | --- |
| one feature request, bug report, ticket, or review comment | **engineering** | a plan for that one change |
| a specification, BRD, SRS, or technical requirements document | **intake** | a list of requirements and questions for you |

### The pipeline

```text
 INTAKE (specifications only)               ENGINEERING (one task at a time)

 start-from-spec                            inspect-repository
 ingest-requirements                        plan-change          ◆ plan approved (if risky)
 clarify-project    ◆ you confirm context   isolate-task
 decompose-spec     ◆ you approve backlog   implement-change
 prepare-task       ◆ only READY tasks ──►  validate-change      ◆ checks must pass
                                            before-after         (optional)
                                            security-review      ◆ no critical findings
                                            update-documentation (optional)
                                            create-pull-request
                                            review / revise      (optional)
                                            completion-report
                                            STOP                 ◆ a human merges
```

◆ marks a gate: work cannot continue until the condition holds.

### The seven gates

| Gate | What must be true | Who decides |
| --- | --- | --- |
| Context confirmed | the project summary from the interview is correct | you |
| Backlog approved | the proposed tasks are what you want | you |
| Ready | the task has no open questions or unmet dependencies | a script |
| Plan approved | a HIGH or CRITICAL risk plan is acceptable | you |
| Validation passed | every check ran and exited with code 0 | a script |
| No critical findings | the change adds no secret or other critical risk | a script |
| Human merge | the pull request should be merged | you, always |

### What it never does

It never merges or approves a pull request, deploys, force-pushes, rewrites a
branch under review, or edits your default branch directly. It never invents
test results, business rules, or credentials. It never reports a check as
passing unless the check ran and exited with code 0. The full rules are in
[`AGENTS.md`](AGENTS.md).

---

## What you get

- **One branch and one pull request per task.** The pull request lists what
  changed, what was tested, and the exact commands and exit codes.
- **A record for every step**, saved as JSON under `.factory/tasks/<TASK-ID>/`
  in your project by default, and never committed:

  | File | Written by | Holds |
  | --- | --- | --- |
  | `context.json` | inspect-repository | the relevant code, tests, risks, and unknowns |
  | `plan.json` | plan-change | the plan, its risk level, and whether approval is needed |
  | `workspace.json` | isolate-task | the branch and worktree that were created |
  | `implementation.json` | implement-change | the files changed and the commits made |
  | `validation.json` | validate-change | every check, with its command, exit code, and output |
  | `security.json` | security-review | secret and risk findings, with secrets redacted |
  | `pull-request.json` | create-pull-request | the pull request that was opened |

  At the end, the completion report checks all of these against each other
  and lists any contradiction.

- **For a specification:** `.factory/requirements.json` (every requirement,
  linked to its section of the document), `.factory/project.json` (the project
  context and your decisions), and `.factory/backlog.json` (the approved tasks).

The [pipeline map](#pipeline-map) turns these records into a picture of where
each task has got to.

---

## The 17 stages

Each stage is a short procedure in its own folder under
`my-software-factory/stages/`. The agent reads only the stage it is on.

**Intake**: from a specification to ready tasks

| Stage | What it does |
| --- | --- |
| `start-from-spec` | Decides whether this is a new project, a resumed one, or an amendment. |
| `ingest-requirements` | Extracts requirements, unknowns, and contradictions, each traced to the document. |
| `clarify-project` | Interviews you about what the document does not answer, and records your decisions. |
| `decompose-spec` | Splits the confirmed requirements into epics, features, and small tasks. |
| `prepare-task` | Hands exactly one READY task to engineering, and refuses anything else. |

**Engineering**: from one task to a reviewed pull request

| Stage | What it does |
| --- | --- |
| `inspect-repository` | Reads only the code, tests, and conventions relevant to the task. |
| `plan-change` | Writes the plan and classifies its risk. |
| `isolate-task` | Creates the task branch and worktree. |
| `implement-change` | Makes the planned change inside the worktree and commits it. |
| `validate-change` | Runs the checks, and reviews backend code against the quality standard. |
| `before-after` | Runs the same commands before and after the change to show the difference. |
| `security-review` | Scans the added lines for secrets, dangerous calls, and new dependencies. |
| `update-documentation` | Fixes documentation the change made untrue. |
| `create-pull-request` | Pushes the branch and opens one pull request with the evidence. |
| `review-pull-request` | Reviews an open pull request and reports findings, without changing it. |
| `revise-pull-request` | Addresses review feedback with new commits, never by rewriting history. |
| `completion-report` | Checks every record against the others and reports contradictions. |

Where a rule can be enforced by code (branch names, exit codes, secret
scanning, "only READY tasks"), the stage uses a script rather than trusting the
model. [`docs/architecture.md`](docs/architecture.md) lists the scripts.

---

## Repository layout

The skill is one folder. Everything else is the project that maintains it.

```text
my-software-factory/     THE SKILL: this is what gets installed
  SKILL.md               the entry point: routes each request to the right stage
  agents/openai.yaml     how the skill appears in Codex (Claude Code ignores it)
  stages/
    intake/              5 stages
    engineering/         12 stages
  schemas/               the JSON format of every record the stages write
  standards/             the backend code-quality standard
  examples/              two worked examples, one per way in

AGENTS.md                the rules every agent must follow (also installed)
tools/
  installer/             installs the skill for Claude Code and Codex
  factory-map/           the local pipeline map
docs/                    in-depth documentation
tests/                   the test suite
```

Each stage folder holds a `SKILL.md` (the procedure) and a `references/` folder
(detail it reads only when needed). Where software can enforce part of the
stage, it also has a `scripts/` folder.

---

## Documentation

| Read this | To learn |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | the rules: routing, the mandatory workflow, what agents must and must not do |
| [`docs/running-a-project.md`](docs/running-a-project.md) | a specification taken all the way to a completion report |
| [`docs/pipeline.md`](docs/pipeline.md) | each stage, what it produces, and why each gate is where it is |
| [`docs/architecture.md`](docs/architecture.md) | how stages, scripts, schemas, and standards fit together |
| [`docs/schemas.md`](docs/schemas.md) | which stage writes which record |
| [`my-software-factory/examples/`](my-software-factory/examples/) | two worked examples: a single task and a specification |
| [`my-software-factory/standards/backend-code-quality.md`](my-software-factory/standards/backend-code-quality.md) | the standard backend code must meet |
| [`tools/factory-map/README.md`](tools/factory-map/README.md) | the pipeline map in detail |

---

## Pipeline map

A read-only web page, served only on your own machine, that draws the pipeline
and colours each stage by what the records on disk say. Run it from this
repository's root:

```bash
python tools/factory-map/scripts/serve_map.py --open
python tools/factory-map/scripts/serve_map.py --open --factory path/to/project/.factory
```

The first command shows how complete each stage's implementation is. The second
shows where each task in that project has got to, and every status names the
file and field it came from. The map writes nothing and runs nothing.

---

## Updating and removing

- **Update:** pull the latest changes, then run the installer again with
  `--replace`. Installed copies do not update themselves. Each install records
  the commit it came from in `.install.json`.
- **Remove:** delete the `my-software-factory` folder from `~/.claude/skills`
  and `~/.codex/skills`.
- **Coming from `software-factory-gpt`:** that was this skill's earlier name.
  The installer lists any old copy under `legacy_installs` but never deletes
  it. Delete it yourself, or both versions will load side by side.

---

## Troubleshooting

**The agent stopped and asked me a question.** That is a gate working. It stops
to settle a specification's open points, to get your approval of a backlog, or
to get your approval of a high-risk plan. Answer, and it carries on from where
it stopped.

**It says it could not open the pull request.** The repository has no GitHub
remote, or `gh` is not logged in. Everything up to that point is committed on
the task branch. Add the remote or run `gh auth login`, then ask it to continue.

**Validation failed.** The agent must not open a pull request until the checks
pass. It works out whether the fault is in the change, the plan, or the check
setup, and goes back to that step.

**The installer says `DESTINATION_EXISTS`.** A copy is already installed. Run it
again with `--replace`. It only ever replaces a previous install of this skill.

**`python` is not found (Windows).** Use `py -3` instead.

---

## Contributing

This repository is built with its own pipeline: every change goes through a
task branch, recorded validation, and a pull request, as
[`AGENTS.md`](AGENTS.md) requires.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

ruff check .                       # lint
pytest                             # tests
```

CI runs the same two commands on every push and pull request.

---

## License

MIT. See [`LICENSE`](LICENSE).

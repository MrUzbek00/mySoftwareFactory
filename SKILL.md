---
name: software-factory-gpt
description: Controlled, auditable engineering pipeline that carries work from a technical requirements document or a single task to a reviewed pull request - ingest requirements, interview, decompose into an approved backlog, then inspect, plan, isolate on a branch and worktree, implement, validate with machine-captured evidence, capture before/after behavior, scan for secrets, update docs, open one PR, review it, revise it, and close with an audited completion report. Use when the user asks for a safe or disciplined approach to a code change, mentions "software factory", hands over a spec, BRD, or SRS to turn into work, wants a structured change plan or backlog, wants work isolated on its own branch, wants tests run as real evidence rather than claims, wants a PR reviewed or revised, or wants an audit trail for a change. Never merges or deploys.
metadata:
  short-description: Auditable spec-to-pull-request coding pipeline
---

# Software Factory GPT

A controlled engineering pipeline. It carries work from a specification or a
single task to a reviewed pull request, and stops at the merge button.

```text
Technical requirements document   (project input, conditional layer)
  |
  v
start-from-spec       -> routing: new project, resume, or amendment
  |
  +--> ingest-requirements -> traceable requirements, unknowns, conflicts
  +--> clarify-project     -> project context  [gate: user confirms]
  +--> decompose-spec      -> epics/features/tasks [gate: user approves]
  |
  v
prepare-task          -> one task contract      [gate: READY only]
  |
  v
Task                              (scoped input, enters here directly)
  |
  v
inspect-repository    -> repository context
  |
  v
plan-change           -> change plan           [approval gate if HIGH/CRITICAL]
  |
  v
isolate-task          -> branch + worktree
  |
  v
implement-change      -> commits on the branch
  |
  v
validate-change       -> machine-captured evidence   [gate: must pass]
  |
  +--> before-after        -> behavior diff       (optional)
  +--> security-review     -> secret + sink scan  [gate: no CRITICAL]
  +--> update-documentation-> doc accuracy        (optional)
  |
  v
create-pull-request   -> one PR, awaiting review
  |
  +--> review-pull-request -> findings            (optional, read-only)
  +--> revise-pull-request -> fast-forward commits(optional, loops to validate)
  |
  v
completion-report     -> audited record
  |
  v
STOP  <- a human owns the merge
```

## Entry Routing

Route the request before doing anything else.

| Input | Enter at |
| --- | --- |
| Specification, BRD, SRS, technical requirements document | stage S1 |
| One feature request, ticket, bug report, or review comment | stage 1 |
| A `READY` task from a backlog this skill generated | stage S5, then stage 1 |

A project-level specification is never handed to `plan-change` or
`implement-change` as a single task. It is decomposed first. A scoped task never
needs the intake layer; stages S1-S5 are skipped entirely.

When the user wants only one part of the pipeline, such as a read-only review of
an open pull request, run that stage alone and say which stages were skipped.

## How to Use This Skill

Run the stages in order. Each has its own procedure file. Read the one for the
stage you are in, and do not read ahead until the previous stage's output
contract is satisfied.

Stages S1-S5 run only for project-level input.

| # | Stage | Read this file | Writes? |
| --- | --- | --- | --- |
| S1 | Route spec | `start-from-spec/SKILL.md` | no |
| S2 | Ingest requirements | `ingest-requirements/SKILL.md` | artifacts only |
| S3 | Clarify project | `clarify-project/SKILL.md` | artifacts only |
| S4 | Decompose spec | `decompose-spec/SKILL.md` | artifacts only |
| S5 | Prepare task | `prepare-task/SKILL.md` | artifacts only |

Stages 1-12 take one scoped task to a reviewed pull request.

| # | Stage | Read this file | Writes? |
| --- | --- | --- | --- |
| 1 | Inspect | `inspect-repository/SKILL.md` | no |
| 2 | Plan | `plan-change/SKILL.md` | no |
| 3 | Isolate | `isolate-task/SKILL.md` | local git |
| 4 | Implement | `implement-change/SKILL.md` | worktree only |
| 5 | Validate | `validate-change/SKILL.md` | no |
| 6 | Before/after | `before-after/SKILL.md` | scratch worktree |
| 7 | Security | `security-review/SKILL.md` | no |
| 8 | Docs | `update-documentation/SKILL.md` | worktree only |
| 9 | Pull request | `create-pull-request/SKILL.md` | push + PR |
| 10 | Review | `review-pull-request/SKILL.md` | no |
| 11 | Revise | `revise-pull-request/SKILL.md` | worktree + push |
| 12 | Report | `completion-report/SKILL.md` | no |

Stages 6, 8, 10, and 11 are optional, and each says when it applies. Skipping one
is a decision to state, not a step to omit silently.

Supporting material lives next to the stage directories:

- `schemas/`: the JSON Schemas every stage output must validate against.
- `standards/`: criteria shared by several stages, not owned by one.
- `*/references/`: deeper guidance to read on demand, not up front.
- `*/scripts/`: deterministic scripts. Use them instead of improvising Git,
  test, or `gh` commands.
- `AGENTS.md`: the normative rules this pipeline enforces.
- `docs/examples/sample-task.md`: a worked single-task request.
- `docs/examples/spec-driven-project.md`: a worked spec-to-backlog path,
  including what the readiness gate refuses and why.

## Agent Portability

This skill runs unchanged in Claude Code and in OpenAI Codex. Only the host's
mechanics differ, so the stage files are written in terms of what to do, not
which tool to call.

- **Paths.** Every path in this skill, including those in the stage files, is
  relative to the directory that contains this `SKILL.md`. Resolve it to an
  absolute path once and run scripts by that absolute path, because the working
  directory is the repository being changed, not this skill.
- **Scripts.** Run them with Python 3.12 or later: `python <skill-dir>/<stage>/scripts/<script>.py`,
  or `py -3` on Windows when `python` is not on `PATH`. They use the standard
  library only. Installing `jsonschema` makes schema checks complete rather than
  required-key checks; nothing else is needed. Stages that publish or read pull
  requests also need `git` and an authenticated `gh`.
- **User gates.** When a stage says to ask, confirm, or get approval, put the
  question to the user and end your turn until they answer. Never answer on the
  user's behalf, and never treat silence or an auto-approve mode as consent to
  pass a gate.
- **Permissions and sandboxes.** When the host blocks a command a stage needs,
  such as a network push or a write outside the workspace, report the blocked
  step and stop. Do not route around the block with a different command.
- **Artifacts.** Persist each stage's JSON with ordinary file writes, under
  `tasks/<TASK-ID>/` in the project artifact root. That directory is what
  `completion-report` audits and what `factory-map` draws.

## Project Artifacts

A project keeps its state under an artifact root, `.factory/` by default (see
`start-from-spec/SKILL.md`). Artifacts are never committed to the repository
being built:

```text
.factory/
  project.json        project context, decisions, amendment history
  requirements.json   requirements index, unknowns, conflicts
  backlog.json        epics, features, tasks, dependencies, readiness
  tasks/<TASK-ID>/    task handoff and the per-task stage artifacts
```

The source document is never copied into the artifacts. It stays where it is as
the source of truth, and the artifacts reference it by document, section, and
page.

## Deterministic Scripts

Scripts, not generated shell commands, handle these operations, because code can
enforce rules that prose cannot:

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
| `completion-report/scripts/build_report.py` | schema validation and cross-artifact contradiction checks |

`factory-map/scripts/serve_map.py` is optional tooling, not a stage. It serves a
read-only map of where a run has got to, derived from the artifact root.

## Coding Standards

`implement-change` applies `standards/backend-code-quality.md` while writing,
`validate-change` reviews changed backend files against it, and
`review-pull-request` reuses it. A `BLOCKING` finding fails validation and blocks
the pull request. An `ADVISORY` finding is recorded and changes nothing.

It is not a style guide. The target repository's framework conventions, existing
architecture, and domain language take precedence, and a subjective naming
preference is never blocking.

## Entry Rules

1. **Route first.** A specification starts at S1; a scoped task starts at 1. A
   plan built on uninspected code is not a plan, and a backlog built on an
   unread document is not a backlog.
2. **Carry `task_id` through every stage.** If the user has no task ID, assign
   one (e.g. `TASK-001`) and state it.
3. **Stages S1, 1, 2, 5, 7, 10, and 12 are read-only.**
4. **Stages 4, 8, and 11 write only inside the task worktree.** Never the source
   checkout, never another task's workspace. Intake stages write only project
   artifacts, never application code.
5. **Persist each stage's JSON artifact as it completes.** Stage 12 audits them,
   and a task that fails early is only diagnosable if earlier artifacts exist.
6. **Report unknowns instead of inventing them.** An ambiguity in a specification
   is an unknown to raise, not a decision to make silently.
7. **Never claim a check passed** unless the script recorded exit code zero.
8. **Stop at review.** Merging is never in scope.

## Gates

- **After stage S3.** The user must confirm the `PROJECT INTAKE SUMMARY` before
  a backlog is presented. Do not repeat a completed interview on resume.
- **After stage S4.** The user must approve the backlog before any task is
  handed to the engineering workflow.
- **At stage S5.** Only a `READY` task passes, and the script decides that, not
  judgment.
- **After stage 2.** When `requires_human_approval` is `true` (automatic for
  `HIGH` and `CRITICAL` risk), stop and get explicit approval before isolating.
- **After stage 5.** When `status` is `fail`, do not proceed. Attribute the
  failure to the implementation, the plan, or the check configuration, and
  return to the stage that owns it. A `BLOCKING` quality finding fails here too.
- **After stage 7.** Any `CRITICAL` finding is a hard stop. Rotate the
  credential first; a scrubbed branch with a live secret is not a fix.
- **After stage 11.** Revision restarts at stage 5. New commits are new code and
  need their own evidence.
- **After stage 12.** Stop entirely. Merging, approving, deploying, and
  dismissing reviews are outside this skill in every circumstance.

## Stage Handoffs

- `start-from-spec` → `ingest-requirements` → `clarify-project` →
  `decompose-spec`: one mode (new, resume, or amendment) drives the whole chain.
  An amendment records impact; it never overwrites a recorded decision.
- `decompose-spec` → `prepare-task`: pass `project_context_path`,
  `requirements_index_path`, `backlog_path`, and one `task_id`.
- `prepare-task` → `inspect-repository`: pass the task handoff. From here the
  task is indistinguishable from one the user wrote by hand.
- `inspect-repository` → `plan-change`: pass the repository context as
  `repository_context`.
- `plan-change` → `isolate-task`: proceed only when `ready_for_isolation` is
  true and any required approval is given. Stage 3 needs `repository_path`,
  `task_id`, `task_type`, `task_slug`, `base_branch`, `worktree_root`.
- `isolate-task` → `implement-change`: pass `workspace_result` and the approved
  `change_plan`.
- `implement-change` → `validate-change`: proceed only when
  `ready_for_validation` is true and all work is committed.
- `validate-change` → stages 6, 7, 8: proceed only when `status` is `pass`.
- stages 6-8 → `create-pull-request`: proceed only when
  `ready_for_pull_request` is true and no `CRITICAL` security finding stands.
- `create-pull-request` → `review-pull-request` / `revise-pull-request`: pass
  the pull request number.
- `revise-pull-request` → `validate-change`: re-validate, then continue.
- anything → `completion-report`: pass every artifact produced, including for a
  task that stopped early.

## Design Principles

Deterministic where possible; structured outputs; least privilege; isolated
workspaces; small context windows; auditable execution; explicit failure;
human escalation.

The model does the reasoning: requirements, architecture, planning,
implementation, review judgment, risk, and unknowns. Deterministic code does
the enforcement: Git operations, check execution, evidence capture, secret
scanning, publishing, and schema validation.

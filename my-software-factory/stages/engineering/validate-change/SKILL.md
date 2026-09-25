---
name: validate-change
description: Run tests, linters, and checks against an implemented task worktree and produce machine-captured evidence.
---

# Validate Change

## Purpose

Prove that an implemented change works, using evidence captured by software
rather than asserted by an agent.

## When to Use

Use this skill after `implement-change` reports `ready_for_validation`, and
before any pull request is opened.

Read `references/validation-evidence.md` when deciding which checks a repository
actually supports.

Read `standards/backend-code-quality.md` before reviewing changed backend files.
It defines the criteria, the slugs findings must cite, and the severity split.

## Preconditions

- An implementation result exists for the task.
- All task work is committed.
- The worktree is on the task branch.

## Required Inputs

- `task_id`
- `workspace_result`
- `implementation_result`
- `optional_explicit_checks`

## Required Workflow

Use `scripts/run_validation.py` for check execution instead of running ad hoc
commands and summarizing them from memory. The script records the real command,
the real exit code, the real duration, and a tail of the real output.

The deterministic workflow is:

1. Verify the worktree exists and is a Git repository.
2. Confirm the working tree is clean.
3. Resolve the check list from explicit checks, detection, or both.
4. Run each check with a timeout.
5. Capture exit codes and output tails.
6. Compute the diff summary against the base branch.
7. Return a structured validation report.

Example CLI:

```bash
python stages/engineering/validate-change/scripts/run_validation.py \
  --worktree /path/to/worktrees/TASK-123-password-reset \
  --task-id TASK-123 \
  --base origin/main \
  --auto
```

Explicit checks override detection and are preferred when the repository
documents its own commands:

```bash
python stages/engineering/validate-change/scripts/run_validation.py \
  --worktree /path/to/worktrees/TASK-123-password-reset \
  --task-id TASK-123 \
  --base origin/main \
  --check lint="ruff check ." \
  --check tests="pytest -q"
```

## Check Detection

Detection only proposes a check when the corresponding configuration actually
exists in the worktree:

- `pyproject.toml` mentioning `ruff` or `pytest`
- `package.json` with `lint`, `typecheck`, or `test` scripts
- `go.mod`
- `Cargo.toml`

A tool that is not on `PATH` is reported as `not_run`, never as a pass.

## Backend Code Quality Review

Automated checks prove a change runs. They cannot tell whether another developer
can understand it. This review does that, and it is part of validation rather
than an optional afterthought.

Review every changed backend file against `standards/backend-code-quality.md`.
Skip files the standard does not govern — templates, generated code, migrations
that only restate a schema — and record which ones you skipped.

For each changed backend file, check:

```text
[ ] Classes have clear responsibilities.
[ ] Public methods are self-explanatory.
[ ] Function and method parameters use meaningful names.
[ ] Input types are explicit where the language supports them.
[ ] Output and return types are explicit where the language supports them.
[ ] Nullable behavior is explicit.
[ ] Collection contents are typed or documented where necessary.
[ ] Important exceptions and error behavior are clear.
[ ] Domain terminology is consistent with the requirements and the repository.
[ ] Variables are human-readable.
[ ] Generic ambiguous names are avoided where practical.
[ ] Documentation exists where it adds contract information a signature cannot.
[ ] Comments explain non-obvious why, not obvious what.
[ ] No unnecessary comment noise was introduced.
[ ] Functions remain cohesive.
[ ] Framework conventions are respected.
```

Write the result to a JSON file and pass it to the script. The script counts
blocking findings and decides the gate; the review supplies the judgment it
counts.

```bash
python stages/engineering/validate-change/scripts/run_validation.py \
  --worktree /path/to/worktrees/TASK-123-password-reset \
  --task-id TASK-123 \
  --base origin/main \
  --auto \
  --quality-review /artifacts/TASK-123/quality-review.json
```

The review file is shaped like:

```json
{
  "status": "findings",
  "reviewed_files": ["app/Services/ContractService.php"],
  "skipped_files": ["resources/views/contracts/show.blade.php"],
  "findings": [
    {
      "criterion": "return-types",
      "severity": "BLOCKING",
      "file": "app/Services/ContractService.php",
      "symbol": "ContractService::createContract",
      "detail": "Returns Contract on success and false on validation failure, with no declared return type. A caller cannot tell which it received.",
      "suggestion": "Declare : Contract and throw a validation exception instead."
    }
  ]
}
```

`status` is `pass` with no findings, `findings` with at least one, and
`not_reviewed` when no backend file changed — with `not_reviewed_reason` saying
so. Never report `pass` for a review that did not happen.

`criterion` must be one of the slugs in the standard. A finding the standard does
not cover is a review comment, not a validation finding.

## Severity

| Severity | Effect |
| --- | --- |
| `BLOCKING` | Validation fails. `ready_for_pull_request` becomes `false`. |
| `ADVISORY` | Recorded and reported. The gate is unaffected. |

Blocking means the contract cannot be understood, or can be used incorrectly:
ambiguous public API behavior, missing types that hide what a function does,
inconsistent return types across failure paths, undocumented nullable behavior a
caller will hit, or a name that actively misleads.

Advisory means everything that would merely be better: a local variable name, a
docblock's wording, a style preference.

A subjective naming preference is never blocking. A review that fails a change
over taste teaches everyone to ignore the review, which costs more than the
preference was worth.

## Check Status Values

- `pass` — the command exited zero.
- `fail` — the command exited non-zero.
- `timeout` — the command exceeded its timeout.
- `not_run` — the executable was not found on `PATH`.

Overall `status` is `pass` only when every check, including the built-in
`working-tree-clean` check, passed, and no `BLOCKING` code quality finding was
recorded.

## Rules

- Do not report a check as passing unless the script recorded exit code zero.
- Do not summarize output the script did not capture.
- Do not modify code to make a check pass; that is implementation work, and it
  returns to `implement-change`.
- Do not disable, skip, or narrow a failing test to reach a green result.
- Do not treat `not_run` as acceptable without saying so explicitly.
- Do not mark the task ready for a pull request when any check failed.
- Do not report a quality review that was not performed, and do not report
  `pass` when backend files were changed but not read.
- Do not raise a subjective preference to `BLOCKING` to force a rewrite.
- Do not downgrade a genuine contract ambiguity to `ADVISORY` to clear the gate.
- Do not fix quality findings here. Fixing code is `implement-change`'s work,
  and the change returns there.
- Do not add a linter or static-analysis dependency to the target repository to
  support this review. That is a planned change with its own risk and approval.

## Interpreting Failures

A failing check means one of:

- the implementation is wrong — return to `implement-change`
- the plan was wrong — return to `plan-change`
- the check itself is misconfigured — report it, do not silently drop it

Choose deliberately and state which.

## Output Contract

Return the script's structured validation report, shaped like:

```json
{
  "status": "pass",
  "task_id": "TASK-123",
  "branch": "feature/TASK-123-password-reset",
  "worktree_path": "/path/to/worktrees/TASK-123-password-reset",
  "base_branch": "origin/main",
  "head_commit": "abc123",
  "checks": [
    {
      "name": "tests",
      "command": "pytest -q",
      "status": "pass",
      "exit_code": 0,
      "duration_seconds": 12.4,
      "output_tail": "..."
    }
  ],
  "diff_summary": { "files_changed": 4, "insertions": 120, "deletions": 8 },
  "code_quality": {
    "status": "pass",
    "reviewed_files": ["app/Services/ContractService.php"],
    "skipped_files": [],
    "findings": [],
    "counts": { "BLOCKING": 0, "ADVISORY": 0 }
  },
  "ready_for_pull_request": true,
  "generated_at": "2026-09-15T00:00:00Z"
}
```

`code_quality` is present only when a review was supplied. Its absence means no
review was passed to the script, which for a change touching backend code is
itself worth reporting.

Validate persisted outputs against `schemas/validation-report.schema.json`.

## Failure Conditions

- The worktree does not exist or is not a Git repository.
- The working tree has uncommitted changes.
- No checks were provided or detected.
- A required check could not be executed.
- The quality review file is missing, malformed, cites an unknown criterion, or
  contradicts itself by reporting `pass` alongside findings.

## Escalation Conditions

Escalate when validation requires network access, production credentials, a
live database, or external services that are not available locally, and when a
check fails in a way that suggests the approved plan was wrong.

## Completion Criteria

- Every check has a recorded command, status, and exit code.
- The evidence came from the script, not from recollection.
- The diff summary reflects the change against the base branch.
- Every changed backend file was reviewed against the standard, or is listed as
  skipped with a reason.
- Quality findings cite a criterion slug and an honest severity.
- Failures are attributed to implementation, plan, or check configuration.
- `ready_for_pull_request` accurately reflects the evidence.

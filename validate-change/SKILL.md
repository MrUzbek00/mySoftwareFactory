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
python validate-change/scripts/run_validation.py \
  --worktree /path/to/worktrees/TASK-123-password-reset \
  --task-id TASK-123 \
  --base origin/main \
  --auto
```

Explicit checks override detection and are preferred when the repository
documents its own commands:

```bash
python validate-change/scripts/run_validation.py \
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

## Check Status Values

- `pass` — the command exited zero.
- `fail` — the command exited non-zero.
- `timeout` — the command exceeded its timeout.
- `not_run` — the executable was not found on `PATH`.

Overall `status` is `pass` only when every check, including the built-in
`working-tree-clean` check, passed.

## Rules

- Do not report a check as passing unless the script recorded exit code zero.
- Do not summarize output the script did not capture.
- Do not modify code to make a check pass; that is implementation work, and it
  returns to `implement-change`.
- Do not disable, skip, or narrow a failing test to reach a green result.
- Do not treat `not_run` as acceptable without saying so explicitly.
- Do not mark the task ready for a pull request when any check failed.

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
  "ready_for_pull_request": true,
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Validate persisted outputs against `schemas/validation-report.schema.json`.

## Failure Conditions

- The worktree does not exist or is not a Git repository.
- The working tree has uncommitted changes.
- No checks were provided or detected.
- A required check could not be executed.

## Escalation Conditions

Escalate when validation requires network access, production credentials, a
live database, or external services that are not available locally, and when a
check fails in a way that suggests the approved plan was wrong.

## Completion Criteria

- Every check has a recorded command, status, and exit code.
- The evidence came from the script, not from recollection.
- The diff summary reflects the change against the base branch.
- Failures are attributed to implementation, plan, or check configuration.
- `ready_for_pull_request` accurately reflects the evidence.

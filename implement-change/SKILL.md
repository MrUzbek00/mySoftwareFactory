---
name: implement-change
description: Execute an approved change plan inside an isolated task worktree, committing only the planned change.
---

# Implement Change

## Purpose

Execute an approved change plan inside an isolated worktree. This skill writes
code, but only the code the plan describes.

## When to Use

Use this skill after `isolate-task` has created a branch and worktree, and only
when the change plan is approved. Do not use it to explore, to plan, or to work
directly in the source repository.

Read `references/implementation-discipline.md` when deciding whether a change is
inside the plan's scope.

## Preconditions

- A structured change plan exists and is approved.
- `requires_human_approval` is `false`, or approval has been explicitly given.
- An isolated branch and worktree exist for this task.
- The worktree working tree is clean.

## Required Inputs

- `task_id`
- `change_plan`
- `workspace_result`

## Workflow

1. Confirm the worktree path from `workspace_result` and work only inside it.
2. Confirm the branch matches the task ID before writing anything.
3. Re-read each file the plan lists as affected before modifying it.
4. Execute the plan's `implementation_steps` in order.
5. Write or update the tests named in the plan's `test_plan`.
6. Run the tests locally as you go; do not defer all verification to validation.
7. Commit in logical units with messages that carry the task ID.
8. Record any deviation from the plan, with the reason.
9. Stop and report when the plan is complete or when a step is blocked.

## Rules

- Work only inside the task worktree. Never write to the source repository
  checkout or another task's workspace.
- Implement the plan, not adjacent improvements. Unplanned refactors, renames,
  formatting sweeps, and dependency upgrades are out of scope.
- Do not weaken, skip, or delete a test to make a suite pass.
- Do not invent test results. Run the tests or report that you did not.
- Do not commit secrets, credentials, tokens, or `.env` files.
- Do not amend or rewrite commits that already exist on the remote.
- Do not run destructive Git commands.
- If the plan turns out to be wrong, stop and return to `plan-change` rather
  than improvising a different change.

## Commit Convention

Use:

```text
<type>(<TASK-ID>): <imperative summary>
```

Examples:

```text
feat(TASK-123): add password reset token expiry
fix(TASK-124): reject refresh tokens after logout
test(TASK-123): cover expired reset token path
```

## Required Reasoning

Determine:

- Does this edit correspond to a named implementation step?
- Does this edit match existing architecture and conventions?
- What test proves this edit works?
- Does this edit change a public contract the plan did not list?
- Is anything in the plan now known to be wrong?

## Deviation Handling

A deviation is any change that the plan did not describe. Record each one in
`plan_deviations` with what changed and why. Deviations that alter the risk
level, touch a public contract, change a database schema, or expand scope are
escalation conditions, not entries in a list.

## Output Contract

Return a structured implementation result shaped like:

```json
{
  "status": "implemented",
  "task_id": "TASK-123",
  "branch": "feature/TASK-123-password-reset",
  "worktree_path": "/path/to/worktrees/TASK-123-password-reset",
  "steps_completed": [],
  "steps_skipped": [],
  "files_added": [],
  "files_modified": [],
  "files_deleted": [],
  "tests_added": [],
  "commits": [{ "sha": "abc1234", "message": "feat(TASK-123): ..." }],
  "plan_deviations": [],
  "unknowns": [],
  "blocked_reason": null,
  "ready_for_validation": true
}
```

Validate persisted outputs against `schemas/implementation-result.schema.json`.

## Failure Conditions

- The worktree does not exist or is not on the task branch.
- The change plan is missing, unapproved, or not ready.
- A planned file cannot be located in the repository.
- A planned step cannot be implemented as described.
- The change requires credentials or services that are not available.

## Escalation Conditions

Escalate when implementation would touch a security boundary, migrate or
transform existing data, change a public contract the plan did not list, raise
the plan's risk level, or require a materially different design than the one
approved.

## Completion Criteria

- Every implementation step is completed or explicitly skipped with a reason.
- Planned tests exist and were actually run.
- All work is committed on the task branch.
- The worktree is clean.
- Deviations and unknowns are explicit.
- `ready_for_validation` accurately reflects whether validation can proceed.

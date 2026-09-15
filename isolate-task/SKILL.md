---
name: isolate-task
description: Create a safe isolated Git branch and worktree for one task before implementation begins.
---

# Isolate Task

## Purpose

Create a safe isolated Git workspace before any implementation starts. One task
gets one branch and one worktree.

## When to Use

Use this skill after `plan-change` reports that a task is ready for isolation.
Do not use it to implement code.

Read `references/git-isolation.md` when explaining worktree safety, conflict
handling, or cleanup policy.

## Preconditions

- Repository inspection is complete.
- A structured change plan exists.
- The change plan is ready for isolation.
- The base branch or ref is known.
- A worktree root is available.

## Required Inputs

- `repository_path`
- `task_id`
- `task_type`
- `task_slug`
- `base_branch`
- `worktree_root`

Supported task types:

- `feature`
- `fix`
- `refactor`
- `chore`
- `docs`
- `test`

## Branch Naming

Use:

```text
<type>/<TASK-ID>-<slug>
```

Examples:

```text
feature/TASK-123-password-reset
fix/TASK-124-refresh-token
refactor/TASK-125-user-service
docs/TASK-126-api-guide
```

Normalize the slug safely. Reject slugs that contain path separators, traversal
segments, control characters, or unsafe branch-name characters.

## Required Workflow

Use `scripts/create_worktree.py` for worktree creation instead of improvising
Git commands.

The deterministic workflow is:

1. Verify repository exists.
2. Verify it is a Git repository.
3. Check current Git status.
4. Fetch the remote when a matching remote exists.
5. Verify base branch exists.
6. Detect whether target branch already exists.
7. Detect whether target worktree already exists.
8. Determine base commit.
9. Create isolated branch.
10. Create Git worktree.
11. Verify the new workspace.
12. Return structured workspace metadata.

Example CLI:

```bash
python isolate-task/scripts/create_worktree.py \
  --repo /path/to/project \
  --task-id TASK-123 \
  --type feature \
  --slug password-reset \
  --base origin/main \
  --worktree-root /path/to/worktrees
```

## Rules

- Do not continue when ambiguous existing state could be overwritten.
- Do not modify the default or protected branch directly.
- Do not reuse another task's writable workspace.
- Do not delete existing worktrees or branches.
- Do not run destructive Git commands.
- Do not force push.

The script must not run:

- `git reset --hard`
- `git clean -fd`
- `git push --force`
- checkout operations over uncommitted files
- branch or worktree deletion

## Output Contract

Successful output is shaped like:

```json
{
  "status": "created",
  "task_id": "TASK-123",
  "branch": "feature/TASK-123-password-reset",
  "worktree_path": "/path/to/worktrees/TASK-123-password-reset",
  "base_branch": "origin/main",
  "base_commit": "abc123",
  "head_commit": "abc123",
  "created_at": "2026-09-15T00:00:00Z"
}
```

Errors are shaped like:

```json
{
  "status": "error",
  "error_code": "BRANCH_ALREADY_EXISTS",
  "message": "..."
}
```

Validate successful persisted outputs against
`schemas/workspace-result.schema.json`.

## Failure Conditions

- Repository path does not exist.
- Repository is not a Git repository.
- Current working tree is dirty.
- Base branch cannot be resolved.
- Target branch already exists.
- Target worktree path already exists.
- Inputs are malformed or unsafe.
- Git cannot create or verify the worktree.

## Escalation Conditions

Escalate when isolation requires touching protected branches, overwriting
existing work, deleting stale branches or worktrees, or using credentials not
already available in the local environment.

## Completion Criteria

- A new branch exists for the task.
- A new worktree exists for the task.
- The worktree HEAD matches the selected base commit.
- Structured metadata preserves the task ID.
- The agent stops before implementation.

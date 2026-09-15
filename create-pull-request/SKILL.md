---
name: create-pull-request
description: Push a validated task branch and open a single pull request with evidence, stopping before review and merge.
---

# Create Pull Request

## Purpose

Publish one validated task branch as one pull request, carrying the plan and the
validation evidence with it. This is the last automated stage. A human owns the
review and the merge.

## When to Use

Use this skill after `validate-change` reports `ready_for_pull_request`. Do not
use it to publish unvalidated work, and do not use it to merge.

Read `references/pull-request-policy.md` when deciding what belongs in the body
and when a pull request should open as a draft.

## Preconditions

- A validation report exists with `status` of `pass`.
- All task work is committed on the task branch.
- The branch is an isolated task branch, not a protected branch.
- The GitHub CLI is installed and authenticated.
- Human approval has been given when the plan required it.

## Required Inputs

- `task_id`
- `workspace_result`
- `change_plan`
- `validation_report`
- `base_branch`

## Required Workflow

Use `scripts/open_pull_request.py` instead of improvising `git push` and
`gh` commands.

The deterministic workflow is:

1. Verify the worktree and resolve the head branch.
2. Refuse protected branches and non-task branches as head.
3. Verify the branch carries the task ID.
4. Verify the working tree is clean.
5. Verify the GitHub CLI is authenticated.
6. Fetch the remote and verify the branch has commits ahead of the base.
7. Refuse when an open pull request already exists for the branch.
8. Push the branch with upstream tracking, never with force.
9. Create the pull request.
10. Read the pull request back to confirm it exists.
11. Return structured pull request metadata.

Example CLI:

```bash
python create-pull-request/scripts/open_pull_request.py \
  --worktree /path/to/worktrees/TASK-123-password-reset \
  --task-id TASK-123 \
  --base main \
  --title "feat(TASK-123): add password reset token expiry" \
  --body-file /path/to/pr-body.md \
  --draft
```

## Pull Request Body

Write the body to a file first, then pass `--body-file`. The body must contain:

- the task ID and a one-paragraph summary of the change
- what changed, in terms a reviewer can check
- the test plan that was executed
- the validation evidence: each check, its command, and its exit code
- risk level and anything a reviewer should look at closely
- unknowns, deviations from the plan, and anything deliberately out of scope

Do not claim a check passed unless the validation report recorded it as passed.

## Rules

- One task, one branch, one pull request.
- Never force push. The script has no force path, and neither do you.
- Never push to or target a protected branch as the head branch.
- Never merge the pull request, enable auto-merge, or approve it.
- Never dismiss reviews, bypass required checks, or edit branch protection.
- Never open a pull request when validation failed or was not run.
- Never include secrets, tokens, or credentials in the title or body.
- Stop after the pull request is created and report the URL.

## Draft Policy

Open as a draft when the plan's `risk_level` is `HIGH` or `CRITICAL`, when the
change touches a public contract or database schema, when any validation check
was `not_run`, or when unknowns remain. Otherwise a ready pull request is
appropriate.

## Output Contract

Return a structured pull request result shaped like:

```json
{
  "status": "created",
  "task_id": "TASK-123",
  "branch": "feature/TASK-123-password-reset",
  "base_branch": "main",
  "head_commit": "abc123",
  "pull_request_number": 42,
  "pull_request_url": "https://github.com/owner/repo/pull/42",
  "draft": false,
  "created_at": "2026-09-15T00:00:00Z"
}
```

Errors are shaped like:

```json
{
  "status": "error",
  "error_code": "PROTECTED_HEAD_BRANCH",
  "message": "..."
}
```

Validate successful persisted outputs against
`schemas/pull-request-result.schema.json`.

## Failure Conditions

- Validation did not pass.
- The working tree has uncommitted changes.
- The head branch is protected, detached, or not a task branch.
- The branch has no commits ahead of the base.
- An open pull request already exists for the branch.
- The GitHub CLI is missing or unauthenticated.
- The push was rejected.

## Escalation Conditions

Escalate when the push is rejected, when the base branch has moved in a way that
requires a rebase decision, when branch protection blocks the pull request, when
the repository requires credentials that are not already available locally, or
when anyone asks for the pull request to be merged.

## Completion Criteria

- The branch exists on the remote with upstream tracking.
- Exactly one pull request exists for the task.
- The body carries the plan summary and real validation evidence.
- The pull request URL and number are reported.
- The task stops here, awaiting human review.

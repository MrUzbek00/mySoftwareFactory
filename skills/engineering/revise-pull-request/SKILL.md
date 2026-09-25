---
name: revise-pull-request
description: Address review feedback on an open pull request with new commits, pushed fast-forward only, never rewritten.
---

# Revise Pull Request

## Purpose

Turn review feedback into commits on the existing pull request branch, without
rewriting the history a reviewer has already read.

## When to Use

Use this skill when an open pull request has review feedback to address. Do not
use it to make unrelated changes to a branch under review.

Read `references/revision-discipline.md` when deciding how to respond to a
comment you disagree with.

## Preconditions

- The pull request is open and its head is the task branch.
- The task worktree still exists and is clean.
- The review feedback has been read.

## Required Inputs

- `task_id`
- `pull_request_number`
- `workspace_result`
- `pull_request_review` or the fetched review threads

## Workflow

1. Fetch the current review threads with
   `skills/engineering/review-pull-request/scripts/fetch_pull_request.py`.
2. List every unresolved thread and decide for each: address, or decline with a
   reason.
3. Implement the accepted changes in the task worktree, under the rules in
   `implement-change`.
4. Re-run `validate-change`. Revisions are changes and need the same evidence.
5. Re-run `security-review` when the revision touched anything it covers.
6. Commit with the task ID, one logical change per commit.
7. Push with `scripts/push_revision.py`.
8. Report what was addressed and what was declined.

Example push:

```bash
python skills/engineering/revise-pull-request/scripts/push_revision.py \
  --worktree /path/to/worktrees/TASK-123-password-reset \
  --task-id TASK-123 \
  --pr 42
```

The script emits the mechanical fields. Merge your `feedback_addressed` and
`feedback_declined` entries into that payload before persisting it.

## Why Fast-Forward Only

`push_revision.py` refuses to push when the local branch and the remote branch
have diverged, and it has no force path.

Rewriting a branch under review destroys the link between a reviewer's comment
and the code it referred to: threads go outdated, review state resets, and any
commits someone else pushed are silently dropped. New commits keep the
conversation intact. Squashing, if the project wants it, belongs to the merge —
which is a human's decision, not this stage's.

When the script reports `DIVERGED_BRANCH` or `BRANCH_BEHIND`, stop and escalate.
Resolving it means choosing what happens to someone else's commits.

## Rules

- Add commits. Never amend, rebase, squash, or force push a branch under review.
- Address the feedback that was given, not adjacent improvements you noticed.
- Never silently ignore a thread. Address it or decline it with a reason.
- Do not mark a thread resolved on the author's behalf unless the user asks.
- Do not weaken a test to satisfy a comment.
- Re-validate after revising. A previously passing validation does not describe
  the new commits.
- Do not merge, approve, or enable auto-merge.

## Declining Feedback

Declining is legitimate when a comment rests on a misreading, conflicts with the
approved plan, or requests work that belongs in another task. It is not
legitimate as a way to avoid effort.

A decline must name the thread and give a reason a reviewer can evaluate. Record
it in `feedback_declined`; do not leave it silent and do not argue in the code.

## Output Contract

Return a structured revision result shaped like:

```json
{
  "status": "revised",
  "task_id": "TASK-123",
  "branch": "feature/TASK-123-password-reset",
  "pull_request_number": 42,
  "pull_request_url": "https://github.com/owner/repo/pull/42",
  "head_commit": "ghi789",
  "feedback_addressed": [
    { "thread": "auth.py:88 expired tokens not invalidated", "resolution": "clear the row on rejection; added a replay test" }
  ],
  "feedback_declined": [
    { "thread": "rename the module", "reason": "out of scope for TASK-123; raised as a separate task" }
  ],
  "commits": [{ "sha": "ghi789", "message": "fix(TASK-123): invalidate expired reset tokens" }],
  "pushed": true,
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Validate persisted outputs against `schemas/revision-result.schema.json`.

## Failure Conditions

- The pull request is not open.
- The pull request head does not match the local branch.
- The worktree is dirty.
- The branch has diverged from or is behind the remote.
- There are no new commits to push.
- Validation fails after revision.

## Escalation Conditions

Escalate when the branch has diverged, when feedback asks for a design change
that the approved plan does not cover, when feedback conflicts between
reviewers, when addressing it would raise the risk level, and whenever anyone
asks for the pull request to be merged.

## Completion Criteria

- Every unresolved thread is addressed or declined with a reason.
- Revisions were validated, not assumed.
- New commits were pushed fast-forward with the task ID.
- History a reviewer already read is intact.
- The pull request still awaits human review.

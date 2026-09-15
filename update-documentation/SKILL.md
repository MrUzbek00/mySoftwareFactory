---
name: update-documentation
description: Update the documentation a change actually invalidated, and record what was reviewed and deliberately left alone.
---

# Update Documentation

## Purpose

Keep documentation true after a change, without turning a task into a
documentation rewrite.

## When to Use

Use this skill after `validate-change` passes and before
`create-pull-request`, when the change alters something a document describes.

Read `references/documentation-scope.md` when deciding whether a document is in
scope.

## Preconditions

- The implementation is complete and validated.
- The task worktree is clean.

## Required Inputs

- `task_id`
- `change_plan`
- `implementation_result`
- `workspace_result`

## Workflow

1. List the behaviors, contracts, commands, options, and defaults the change
   altered.
2. Search the repository for documents that describe any of them.
3. For each document found, decide: update, review with no change, or out of
   scope.
4. Make the smallest edit that restores accuracy.
5. Commit documentation changes with the task ID.
6. Record every document in one of the three categories.

## Where to Look

Search for the changed symbol, flag, route, config key, or error message across:

- `README` files at the repository root and in affected packages
- `docs/` trees and site content
- `AGENTS.md`, `CONTRIBUTING`, and setup guides
- API references, OpenAPI or schema files kept by hand
- inline docstrings and module headers on the code you changed
- example files, sample configs, and `.env.example`
- changelogs, when the repository maintains one by hand

A document that shows a command's output, a config sample, or a code snippet is
easy to miss and is exactly where staleness hides.

## Rules

- Update only what the change made untrue.
- Do not rewrite documents for tone, structure, or style.
- Do not fix unrelated stale documentation. Report it; do not absorb it.
- Do not add documentation the repository does not already keep — a project
  without a changelog does not gain one from this task.
- Do not document behavior that was not implemented.
- Do not invent a documentation convention the repository does not use.
- Never publish a secret, internal hostname, or credential in an example.

## Recording Decisions

Every document you looked at ends up in one of three lists, so a reviewer can
tell the difference between "checked and fine" and "never looked":

- `documents_updated` — changed, with the reason.
- `documents_reviewed_no_change` — read, still accurate.
- `documents_out_of_scope` — related but deliberately untouched, including
  stale content that belongs to a different task.

## Output Contract

Return a structured documentation update shaped like:

```json
{
  "status": "updated",
  "task_id": "TASK-123",
  "branch": "feature/TASK-123-password-reset",
  "documents_updated": [
    { "path": "docs/auth.md", "reason": "reset tokens now expire after 15 minutes" }
  ],
  "documents_reviewed_no_change": ["README.md"],
  "documents_out_of_scope": ["docs/billing.md"],
  "unknowns": [],
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Use `status` of `no_change_required` when the change invalidated nothing, and
say which documents you checked to reach that conclusion.

Validate persisted outputs against `schemas/documentation-update.schema.json`.

## Failure Conditions

- The worktree is dirty or not on the task branch.
- A document that must change is generated from a source that is unavailable.
- The correct documented behavior cannot be determined.

## Escalation Conditions

Escalate when documentation implies a contract the change breaks, when a
published API reference would need a versioning decision, when translated or
mirrored copies exist outside the repository, and when documentation and code
disagreed *before* this change — that is a separate task and a reviewer should
know.

## Completion Criteria

- Every affected document is updated or explicitly categorized.
- Edits are minimal and match the repository's existing conventions.
- Documentation changes are committed with the task ID.
- Stale content found but left alone is reported, not silently skipped.

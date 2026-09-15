---
name: review-pull-request
description: Review an open pull request against its stated intent and report findings, without approving, merging, or posting uninvited.
---

# Review Pull Request

## Purpose

Read a pull request the way a careful reviewer would, and produce findings a
human can act on. Reviewing is not approving.

## When to Use

Use this skill on an open pull request — one this pipeline opened, or someone
else's that the user asked you to look at.

Read `references/review-standards.md` for what counts as a finding.

## Preconditions

- The pull request exists and is open.
- The GitHub CLI is installed and authenticated.

## Required Inputs

- `pull_request_number` or `branch`
- `repository_path`
- `optional_task_id`
- `optional_change_plan`

## Required Workflow

Use `scripts/fetch_pull_request.py`. It is strictly read-only: it has no code
path that approves, merges, closes, or comments.

The deterministic workflow is:

1. Verify the GitHub CLI is authenticated.
2. Fetch metadata, including state, draft status, and review decision.
3. Fetch the check runs and their states.
4. Fetch review threads and count the unresolved ones.
5. Fetch the diff, writing it to a file when it is large.
6. Return the assembled context.

Example CLI:

```bash
python review-pull-request/scripts/fetch_pull_request.py \
  --repo-path /path/to/project \
  --pr 42 \
  --out-dir /path/to/scratch
```

## Reading Order

Read in this order, because each step frames the next:

1. **The description** — what the author says this does.
2. **The check results** — what the machine says about it.
3. **The diff** — what it actually does.
4. **The tests** — what the change proves about itself.
5. **The existing threads** — what reviewers have already raised.

A diff read before the intent produces nitpicks. Intent read before the diff
produces review.

## What to Look For

- **Correctness** — does it do what the description claims, including at the
  boundaries the tests do not cover?
- **Contract** — does it change a public API, schema, config key, or default in
  a way the description does not mention?
- **Security** — new input paths, authorization decisions, secret handling,
  injection sinks.
- **Tests** — does a test exist that would fail without this change? Were any
  weakened, skipped, or deleted?
- **Scope** — does the diff contain changes unrelated to the stated purpose?
- **Failure modes** — what happens on error, on empty input, on a retry, on
  concurrent callers?

## Rules

- Do not approve, merge, enable auto-merge, close, or request changes as a
  formal review action.
- Do not post comments on the pull request unless the user explicitly asks you
  to, and then only the findings you actually produced.
- Do not review code you have not read. If the diff was truncated, say so and
  review only what you read.
- Do not report style preferences as findings when the repository has a
  formatter that is already passing.
- Do not assume a red check is flaky. Read it.
- Do not treat the author's description as evidence that the code does what it
  says.
- Separate what you verified from what you inferred.

## Verdicts

- `looks_sound` — no findings that should block, and the checks pass.
- `changes_suggested` — findings exist that a reviewer should weigh.
- `blocked` — a correctness, security, or contract problem that must be resolved
  before merge, or a failing check with no explanation.

## Output Contract

Return a structured review shaped like:

```json
{
  "status": "reviewed",
  "task_id": "TASK-123",
  "pull_request_number": 42,
  "pull_request_url": "https://github.com/owner/repo/pull/42",
  "branch": "feature/TASK-123-password-reset",
  "base_branch": "main",
  "head_commit": "def456",
  "verdict": "changes_suggested",
  "findings": [
    {
      "severity": "HIGH",
      "file": "app/auth.py",
      "line": 88,
      "summary": "Expired tokens are rejected but not invalidated",
      "rationale": "A replayed token still matches on the next request because the row is never cleared."
    }
  ],
  "checks": [{ "name": "tests", "state": "SUCCESS" }],
  "unresolved_threads": 1,
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Validate persisted outputs against `schemas/pull-request-review.schema.json`.

## Failure Conditions

- The pull request does not exist or is not open.
- The GitHub CLI is missing or unauthenticated.
- The diff cannot be retrieved.

## Escalation Conditions

Escalate when the pull request touches a security boundary, when a check fails
for a reason you cannot explain, when the diff is too large to review honestly
in one pass, and whenever anyone asks you to approve or merge it.

## Completion Criteria

- Every finding names a file, a line, and why it matters.
- Verified observations are distinguished from inferences.
- Check results are reported as fetched.
- No approval, merge, or uninvited comment occurred.

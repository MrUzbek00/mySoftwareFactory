---
name: security-review
description: Scan what a task added for secrets, dangerous patterns, and dependency changes, then review the result with judgment.
---

# Security Review

## Purpose

Catch security problems this task introduced, before they reach a remote where
they are permanent. A deterministic scan runs first; judgment interprets it.

## When to Use

Use this skill after `validate-change` passes and before
`create-pull-request`. Run it on every task, including small ones — the cost is
seconds and the failure mode is a published secret.

Read `references/security-heuristics.md` for what the scanner can and cannot
see.

## Preconditions

- All task work is committed.
- The base ref is fetchable so the diff can be computed.

## Required Inputs

- `task_id`
- `workspace_result`
- `change_plan`

## Required Workflow

Use `scripts/scan_diff.py`. It reads only the lines the change **added**, so it
reports what this task introduced rather than what the repository already had.

The deterministic workflow is:

1. Resolve the base commit with `merge-base`.
2. Take the diff from base to HEAD.
3. Walk the added lines, tracking file and line number.
4. Match each line against the rule set.
5. Redact any matched secret before recording it.
6. Collect added lines in dependency manifests.
7. Return findings, dependency changes, and severity counts.

Example CLI:

```bash
python security-review/scripts/scan_diff.py \
  --worktree /path/to/worktrees/TASK-123-password-reset \
  --task-id TASK-123 \
  --base origin/main
```

Exit code is `0` when clean and `1` when there are findings.

## What the Scan Covers

- Secret material: private keys, cloud keys, provider tokens, JWTs, and
  credential-shaped assignments.
- Dangerous sinks: `eval`/`exec`, `os.system`, `shell=True`, `pickle.loads`,
  unsafe `yaml.load`, `innerHTML` assignment, string-built SQL.
- Weakened protections: disabled TLS verification, wildcard CORS, permissive
  file modes, weak hashes.
- Dependency manifest changes, which always warrant a look.

## What the Scan Cannot Cover

Pattern matching does not understand your application. It cannot see a missing
authorization check, a broken tenancy boundary, an IDOR, a race condition, or a
logic flaw that leaks data through a legitimate-looking path.

After reading the scan, reason explicitly about:

- Does this change read or write data belonging to a user other than the caller?
- Does it add or alter an authentication or authorization decision?
- Does it widen what an unauthenticated caller can reach?
- Does it log, serialize, or return data that was previously internal?
- Does it introduce a new trust boundary or cross an existing one?

A clean scan plus unanswered questions is not a clean review.

## Rules

- Never copy a matched secret into a report, a commit, a pull request body, or
  a chat message. The scanner redacts; do not undo that.
- Treat any `CRITICAL` finding as a hard stop. Do not proceed to a pull request.
- Treat a secret found in the diff as potentially already committed. Say so, and
  say that rotation is required — removing it from the working tree does not
  remove it from history.
- Do not dismiss a finding as a false positive without stating why it is one.
- Do not silence the scan by narrowing the diff or skipping the stage.

## Severity Response

- `CRITICAL` — stop. Remove the material, rotate the credential, escalate.
- `HIGH` — resolve before the pull request, or justify explicitly in the body.
- `MEDIUM` — resolve or record as a known risk for the reviewer.
- `LOW` — note it; proceed.

## Output Contract

Return the scan result, shaped like:

```json
{
  "status": "findings",
  "task_id": "TASK-123",
  "branch": "feature/TASK-123-password-reset",
  "base_commit": "abc123",
  "head_commit": "def456",
  "findings": [
    {
      "rule": "hardcoded-credential",
      "severity": "HIGH",
      "file": "app/config.py",
      "line": 42,
      "evidence": "API_KEY = <redacted:32chars>"
    }
  ],
  "dependency_changes": [{ "file": "requirements.txt", "added_lines": ["requests==2.32.0"] }],
  "counts": { "CRITICAL": 0, "HIGH": 1, "MEDIUM": 0, "LOW": 0 },
  "requires_human_review": true,
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Validate persisted outputs against `schemas/security-review.schema.json`.

## Failure Conditions

- The base ref cannot be resolved.
- The diff cannot be computed.
- The worktree is not a Git repository.

## Escalation Conditions

Escalate on any `CRITICAL` finding, on any secret that may already exist in
commit history, on a dependency added from an unfamiliar source, and whenever
the reasoning questions above surface a plausible authorization or data-exposure
problem.

## Completion Criteria

- The scan ran against the real diff.
- Every finding is resolved, justified, or escalated.
- The judgment questions were answered, not skipped.
- No secret material appears anywhere in the output.
- `requires_human_review` reflects the actual result.

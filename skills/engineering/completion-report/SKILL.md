---
name: completion-report
description: Audit every stage artifact for a task, cross-check them against each other, and report contradictions rather than a summary.
---

# Completion Report

## Purpose

Close the task with an auditable record. The report is assembled from the
artifacts each stage actually produced, not from recollection of what happened.

## When to Use

Use this skill as the final stage of a task, after a pull request exists — or
after a task ends early, to record where and why it stopped.

Read `references/audit-trail.md` for what the cross-checks are protecting
against.

## Preconditions

- Each completed stage persisted its structured output as a JSON file.
- The schemas directory is available.

## Required Inputs

- `task_id`
- `paths to each stage artifact`

## Required Workflow

Use `scripts/build_report.py`. It validates each artifact against its schema and
cross-checks the artifacts against each other.

The deterministic workflow is:

1. Load each provided artifact.
2. Validate it against its stage schema.
3. Confirm every artifact carries the same task ID.
4. Confirm every artifact agrees on the branch.
5. Confirm a pull request was not opened on failed validation.
6. Confirm the pull request head matches the validated commit.
   Confirm `BLOCKING` code quality findings did not reach a pull request.
7. Confirm a blocked implementation did not produce a pull request.
8. Confirm `CRITICAL` security findings did not reach a pull request.
9. Report missing required stages.
10. Return the assembled report.

Example CLI:

```bash
python skills/engineering/completion-report/scripts/build_report.py \
  --task-id TASK-123 \
  --schemas-dir schemas \
  --artifact inspect-repository=/artifacts/TASK-123/context.json \
  --artifact plan-change=/artifacts/TASK-123/plan.json \
  --artifact isolate-task=/artifacts/TASK-123/workspace.json \
  --artifact implement-change=/artifacts/TASK-123/implementation.json \
  --artifact validate-change=/artifacts/TASK-123/validation.json \
  --artifact security-review=/artifacts/TASK-123/security.json \
  --artifact create-pull-request=/artifacts/TASK-123/pull-request.json
```

Exit code is `0` when complete and consistent, `1` otherwise.

## Required Stages

These must be present for a task that reached a pull request:

`inspect-repository`, `plan-change`, `isolate-task`, `implement-change`,
`validate-change`, `create-pull-request`.

`prepare-task`, `before-after`, `security-review`, `update-documentation`,
`review-pull-request`, and `revise-pull-request` are optional and reported as
absent when not provided. Absent means not run — say which it was.

`prepare-task` is present only for a task that came from a specification-driven
backlog. Include it when it exists: it carries the source requirements, so the
report answers why the task existed, not only what was done. The script confirms
the handoff was `READY`.

## Persisting Artifacts

This stage only works if earlier stages wrote their outputs down. Persist each
stage's JSON as it completes, under a per-task directory:

```text
artifacts/TASK-123/
  context.json
  plan.json
  workspace.json
  implementation.json
  validation.json
  security.json
  pull-request.json
```

Keep them out of the repository being changed, unless the project asks for them.

## Rules

- Do not hand-write the report. Run the script.
- Do not omit an artifact because it is inconvenient. A missing artifact is a
  finding.
- Do not resolve an inconsistency by editing an artifact. Fix the underlying
  problem and re-run the stage that produced it.
- Do not report `complete` when the script reports `incomplete`.
- Do not describe the task as finished. It awaits human review.

## Reading the Inconsistencies

Each entry is a contradiction between artifacts — the class of error that a
prose summary hides. For example: a pull request whose head commit is not the
commit validation ran against means the PR contains unvalidated code.

Every inconsistency is either fixed by re-running a stage, or explained in the
report. Neither is optional.

## Output Contract

Return a structured completion report shaped like:

```json
{
  "status": "complete",
  "task_id": "TASK-123",
  "stages": [
    { "stage": "validate-change", "present": true, "valid": true, "errors": [] },
    { "stage": "before-after", "present": false, "valid": null, "errors": [] }
  ],
  "artifacts": { "validate-change": "/artifacts/TASK-123/validation.json" },
  "inconsistencies": [],
  "outcome": {
    "branch": "feature/TASK-123-password-reset",
    "validation_status": "pass",
    "security_status": "clean",
    "pull_request_url": "https://github.com/owner/repo/pull/42",
    "awaiting": "human review and merge"
  },
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Validate persisted outputs against `schemas/completion-report.schema.json`.

## Failure Conditions

- An artifact file is missing or is not valid JSON.
- An artifact names an unknown stage.
- The schemas directory does not exist.
- No artifacts were provided.

## Escalation Conditions

Escalate when an inconsistency implies unvalidated code reached a remote, when a
required artifact cannot be produced, and when stages disagree about what
happened in a way you cannot explain.

## Completion Criteria

- Every stage is marked present or absent, with schema validity recorded.
- Inconsistencies are listed, then fixed or explained.
- The outcome names the branch, the pull request, and what is being waited on.
- The report is generated by the script, not narrated.

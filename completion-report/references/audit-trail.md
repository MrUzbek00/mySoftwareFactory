# Audit Trail

The completion report exists because a summary written at the end of a task is
written by the same process that did the work, and inherits all of its mistakes.

## What the Cross-Checks Protect Against

Each check corresponds to a specific way a task can go wrong while every
individual stage still reports success.

**Task ID mismatch.** Artifacts from two different tasks got mixed, usually by
reusing a scratch directory. The report would otherwise describe a change nobody
made.

**Branch disagreement.** Stages ran against different branches — often work done
in the source checkout instead of the worktree, then a pull request opened from
somewhere else.

**Pull request without passing validation.** The single most important check. If
`create-pull-request` succeeded while validation failed, unvalidated code
reached a remote, and the gate that was supposed to prevent it did not hold.

**Head commit mismatch.** Validation ran against one commit and the pull request
points at another — commits landed after validation. The PR contains code that
was never checked, and the validation report gives false assurance.

**Blocked implementation with a pull request.** Implementation reported it could
not finish, and a pull request exists anyway. Something published partial work.

**Critical security findings with a pull request.** The security stage recorded
a `CRITICAL` finding and the task proceeded. Possibly a published secret.

## Why Artifacts, Not Memory

A stage that reports "validation passed" is making a claim. The validation
artifact contains the command, the exit code, and the output tail — a claim with
evidence attached, which can be checked later by someone who was not there.

The difference matters most when something went wrong. A summary reconstructs
what the author believes happened. The artifacts record what the tools observed.

## Persist as You Go

Write each stage's JSON when the stage finishes, not at the end. A task that
fails at stage 5 should still have artifacts for stages 1 through 4 — those are
what make the failure diagnosable.

```text
artifacts/TASK-123/
  context.json
  plan.json
  workspace.json
  implementation.json
  validation.json
  before-after.json
  security.json
  documentation.json
  pull-request.json
```

Keep them outside the repository being changed unless the project asks for them.
They are records of the process, not part of the product.

## Absent Is Not Failed

An optional stage reported as `present: false` means no artifact was provided.
That could mean the stage was deliberately skipped — a refactor with nothing
observable to probe — or that it was never run.

The report cannot tell the difference. You can, so say which.

## Inconsistencies Are Not Warnings

An inconsistency means two artifacts contradict each other, and at least one is
wrong. The fix is to re-run the stage that produced the wrong one, then rebuild
the report.

Editing an artifact to make the check pass defeats the entire mechanism. So does
reporting `complete` when the script said `incomplete`.

## Schema Validation Degrades Honestly

When `jsonschema` is installed, artifacts are fully validated and `valid` is
`true` or `false`.

When it is not installed, only required top-level keys are checked. A structurally
broken artifact can pass that weaker check, so `valid` is reported as `null`,
with a note — never as `true`. `null` means *not fully checked*, and should not
be read as passing.

## The Task Is Not Done

The final `awaiting` field says what the task is waiting on, and for a successful
task that is human review and merge.

A completion report is the end of the automated work, not the end of the change.
Nothing in this pipeline merges anything.

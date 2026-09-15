---
name: before-after
description: Capture observable behavior at the base commit and at the task head so a reviewer can see what actually changed.
---

# Before After

## Purpose

Show the change, rather than describe it. The same probes run against the base
commit and against the task head, and both results are recorded.

## When to Use

Use this skill after `validate-change` passes, when the change alters observable
behavior a reviewer would want demonstrated: an output, an exit code, a rendered
result, an API response, a CLI message.

Skip it, and say so, when the change has no observable behavior to probe — a
pure internal refactor with identical outputs, or a documentation-only change.

Read `references/observable-evidence.md` when choosing probes.

## Preconditions

- Validation passed for this task.
- All task work is committed.
- The probe commands can run offline without production credentials.

## Required Inputs

- `task_id`
- `workspace_result`
- `change_plan`
- `probe_commands`

## Required Workflow

Use `scripts/capture_before_after.py`. It builds a throwaway detached worktree
at the base commit, runs each probe on both sides, and removes the scratch
worktree afterwards.

The deterministic workflow is:

1. Verify the worktree is clean.
2. Resolve the base commit with `merge-base`.
3. Create a detached scratch worktree at that commit.
4. Run each probe in the scratch worktree — the "before" side.
5. Run each probe in the task worktree — the "after" side.
6. Compare exit codes and output.
7. Remove the scratch worktree.
8. Return a structured before and after report.

Example CLI:

```bash
python before-after/scripts/capture_before_after.py \
  --worktree /path/to/worktrees/TASK-123-password-reset \
  --task-id TASK-123 \
  --base origin/main \
  --probe reset-expiry="python -m demo reset --token expired" \
  --probe help-text="python -m demo --help"
```

## Choosing Probes

A good probe is deterministic, fast, offline, and closely tied to the behavior
the plan changed. It must run successfully on the base commit too — a probe that
only exists after the change produces a `not_run` before side and proves nothing.

Prefer:

- a CLI invocation that exercises the changed path
- a test that fails before and passes after, run by name
- a script that prints the value the change affects

Avoid:

- probes that hit the network or a production service
- probes whose output embeds a timestamp, path, or random ID
- whole test suites, which belong in `validate-change`

## Rules

- Do not modify code to make a probe more convincing.
- Do not present the after side alone. A single-sided result is not evidence.
- Do not claim a difference the report does not show.
- Do not treat `changed: false` as a failure. Sometimes it is the point, as in a
  refactor that must not alter behavior.
- Do not run probes that require credentials this environment does not already
  hold.

## Interpreting the Report

- `changed: true` on the probes the plan targeted — expected.
- `changed: false` on those probes — the change may not do what was intended.
- `changed: true` on probes the plan did not target — a possible regression.
  Investigate before proceeding.
- `status: partial` — at least one side did not run. Say so explicitly rather
  than reporting the comparison as complete.

## Output Contract

Return a structured before and after report shaped like:

```json
{
  "status": "captured",
  "task_id": "TASK-123",
  "branch": "feature/TASK-123-password-reset",
  "base_commit": "abc123",
  "head_commit": "def456",
  "probes": [
    {
      "name": "reset-expiry",
      "command": "python -m demo reset --token expired",
      "before": { "status": "ran", "exit_code": 0, "output_tail": "accepted" },
      "after": { "status": "ran", "exit_code": 1, "output_tail": "token expired" },
      "changed": true
    }
  ],
  "differences_detected": true,
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Validate persisted outputs against `schemas/before-after-report.schema.json`.

## Failure Conditions

- The worktree is dirty.
- The base commit cannot be resolved.
- The scratch worktree cannot be created.
- No probes were provided.

## Escalation Conditions

Escalate when a probe requires network access, production data, or credentials;
when the base side cannot run at all; and when a probe the plan did not target
shows an unexplained difference.

## Completion Criteria

- Every probe has a recorded before side and after side.
- Differences are attributed to the change or flagged as unexplained.
- The scratch worktree was removed.
- The report is honest about probes that did not run.

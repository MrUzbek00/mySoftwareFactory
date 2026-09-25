---
name: prepare-task
description: Hand one READY backlog task to the engineering workflow as a scoped task contract, refusing anything that is not ready.
---

# Prepare Task

## Purpose

Convert exactly one `READY` backlog task into the contract the existing
engineering workflow expects. This skill is the gate between specification
intake and implementation. It must not write code and must not start the
implementation it prepares.

## When to Use

Use this skill after the backlog is approved, once per task, immediately before
`inspect-repository`. Use it again for the next task when the previous one is
closed.

Read `references/handoff-contract.md` for how handoff fields map onto the
downstream skills and what the gate refuses.

## Preconditions

- The project context exists and its `status` is `confirmed`.
- The backlog exists and its `status` is `approved`.
- The selected task's `readiness` is `READY`.
- The target repository is known.

## Required Inputs

- `project_context_path`
- `requirements_index_path`
- `backlog_path`
- `task_id`

## Required Workflow

Use `scripts/prepare_task.py`. The gate is enforced by the script, not by
judgment.

```bash
python skills/intake/prepare-task/scripts/prepare_task.py \
  --project-context .factory/project.json \
  --requirements .factory/requirements.json \
  --backlog .factory/backlog.json \
  --task-id TASK-UZK-043 \
  --out .factory/tasks/TASK-UZK-043/task-handoff.json
```

Exit code is `0` when the handoff was produced, `1` otherwise.

The deterministic workflow is:

1. Load the project context, requirements index, and backlog.
2. Refuse unless the project context is confirmed and names a repository.
3. Refuse unless the backlog is approved.
4. Locate the task by `task_id` or `backlog_ref`.
5. Refuse unless the task is `READY` with testable acceptance criteria and no
   blockers.
6. Refuse when an attached unknown or conflict is unresolved.
7. Resolve every source requirement and refuse any that is not `CONFIRMED`,
   `CLARIFIED`, or `OPTIONAL`.
8. Refuse when a dependency is unknown, or is not `DONE` without an explicit
   override.
9. Emit the handoff, carrying source requirements and their coordinates.

After a successful handoff, set the task to `IN_PROGRESS` in the backlog and
continue with `inspect-repository`.

## Refusals

| Error code | Meaning |
| --- | --- |
| `PROJECT_NOT_CONFIRMED` | The intake summary was never confirmed. |
| `BACKLOG_NOT_APPROVED` | The backlog was never approved. |
| `UNKNOWN_TASK` | No such task in the backlog. |
| `TASK_NOT_READY` | Readiness is not `READY`, or criteria or blockers contradict it. |
| `TASK_HAS_OPEN_QUESTIONS` | An attached unknown or conflict is unresolved. |
| `REQUIREMENT_NOT_CONFIRMED` | A source requirement is missing, `AMBIGUOUS`, `BLOCKED`, or out of scope. |
| `REPOSITORY_UNKNOWN` | The project context names no repository. |
| `UNKNOWN_DEPENDENCY` | A dependency is not in the backlog. |
| `DEPENDENCY_NOT_DONE` | A dependency is not `DONE` and no override was given. |

`--allow-open-dependencies` is a human override. It does not suppress the
finding: the dependencies it let through are recorded in `open_dependencies` on
the handoff, and travel with the task.

## Rules

- One task per handoff. Never batch, never merge two tasks, never hand off an
  epic or a feature.
- Never hand off a whole specification.
- Do not edit the backlog task to make it pass the gate. Fix the underlying
  cause and re-run `decompose-spec`.
- Do not set or raise `risk_level`. `plan-change` classifies risk against the
  real codebase and owns `requires_human_approval`.
- Do not skip `inspect-repository` because intake produced context. Intake knows
  the product; only inspection knows the code.
- Do not write to the target repository.
- Do not start implementation.

## Required Reasoning

Determine:

- Is this task genuinely the next one, given dependencies and priorities?
- Does the handoff carry enough for planning without the whole specification?
- Does every acceptance criterion give `validate-change` something to prove?
- Do the constraints include the project decisions that bind this task?
- Is anything in the task's context stale since the backlog was approved?

## Output Contract

Return a task handoff shaped like:

```json
{
  "task_id": "TASK-UZK-043",
  "backlog_ref": "UZK-043",
  "project_id": "UZK",
  "task_title": "Assign application to specialist",
  "task_description": "Assign an accepted purchase application to a specialist.",
  "task_type": "feature",
  "task_slug": "assign-application",
  "repository": {
    "url": "https://github.com/owner/uz-koram",
    "path": "/workspace/uz-koram",
    "base_branch": "main",
    "project_type": "existing"
  },
  "acceptance_criteria": [
    "A manager can assign an accepted application to exactly one specialist.",
    "Assignment is rejected for an application that is not accepted.",
    "The assigned specialist sees the application in their own list."
  ],
  "constraints": ["Laravel is mandatory (DEC-001).", "Server-rendered Blade views; no SPA."],
  "dependencies": ["TASK-UZK-010", "TASK-UZK-012", "TASK-UZK-022", "TASK-UZK-042"],
  "out_of_scope": ["Reassignment after assignment.", "Notification delivery."],
  "test_requirements": ["Feature tests for the allowed and rejected assignment paths."],
  "source_requirements": [
    {
      "requirement_id": "REQ-APP-021",
      "statement": "An accepted application is assigned to a specialist by a manager.",
      "state": "CONFIRMED",
      "sources": [{ "source_id": "SPEC-1", "section": "4.2", "subsection": null, "page": "10-11" }]
    }
  ],
  "source_specifications": [
    {
      "source_id": "SPEC-1",
      "title": "Uz-Koram Technical Requirements",
      "location": "docs/Uz-Koram-Technical-Requirements.docx"
    }
  ],
  "optional_target_paths": [],
  "risk_level": "MEDIUM",
  "readiness": "READY",
  "open_dependencies": [],
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Validate persisted outputs against `schemas/task-handoff.schema.json`.

## Handoff Into the Engineering Workflow

```text
task-handoff.json
  |
  +-- task_id, task_title, task_description, repository.path  -> inspect-repository
  +-- acceptance_criteria, constraints                        -> plan-change
  +-- task_type, task_slug, repository.base_branch            -> isolate-task
  +-- source_requirements, backlog_ref                        -> create-pull-request,
  |                                                              completion-report
  v
inspect-repository -> plan-change -> isolate-task -> implement-change -> ...
```

Nothing downstream changes. The existing risk classification, approval gate,
validation gate, security gate, and human-owned merge apply exactly as before.

## Failure Conditions

- Any refusal listed above.
- An artifact is missing or is not valid JSON.
- The task is already `IN_PROGRESS` or `DONE`.

## Escalation Conditions

Escalate when a task appears `READY` but its requirements changed after
approval, when the repository named in the context no longer exists, when a
dependency override would put unvalidated assumptions into the work, and when
the user asks to hand off a task the gate refused.

## Completion Criteria

- Exactly one task was prepared.
- The gate ran as a script and exited `0`.
- The handoff carries the task ID, the source requirements, and their source
  coordinates.
- The backlog task is marked `IN_PROGRESS`.
- No code was written, and the next step is `inspect-repository`.

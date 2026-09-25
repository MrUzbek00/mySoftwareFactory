---
name: decompose-spec
description: Convert confirmed requirements into epics, features, and implementation-sized tasks with dependencies, readiness state, and traceability back to the source document.
---

# Decompose Spec

## Purpose

Turn a requirements index and a confirmed project context into a backlog of
tasks small enough for one change each. This skill must not write code and must
not design an implementation for any repository.

## When to Use

Use this skill after `clarify-project` reports a confirmed project context, and
before `prepare-task`. Use it again, scoped to the affected epics, after an
amendment.

Read `references/decomposition-rules.md` for task sizing, readiness rules, and
dependency conventions.

## Preconditions

- A requirements index exists.
- The project context exists and its `status` is `confirmed`.
- The target repository is known.

## Required Inputs

- `project_id`
- `requirements_index`
- `project_context`
- `optional_existing_backlog`

## Workflow

1. Group requirements into epics by the document's own areas, not by technical
   layer.
2. Split each epic into features.
3. Split each feature into tasks that one change can deliver.
4. For each task, write the description, business objective, actor, functional
   requirements, acceptance criteria, constraints, out-of-scope notes, and test
   requirements.
5. Link each task to the requirements it implements.
6. Derive dependencies between tasks.
7. Assign readiness to each task using the readiness rules.
8. Attach unresolved unknowns and conflicts to the tasks they block.
9. Run `scripts/check_backlog.py` and fix every violation it reports.
10. Present the backlog, the dependency graph, and the recommended first READY
    task, then wait for approval.
11. Set `status` to `approved` and stamp `approved_at` only after explicit
    approval.

## Required Workflow

Use `scripts/check_backlog.py` rather than reasoning about consistency by hand.

```bash
python skills/intake/decompose-spec/scripts/check_backlog.py \
  --project-context .factory/project.json \
  --requirements .factory/requirements.json \
  --backlog .factory/backlog.json \
  --schemas-dir schemas
```

Exit code is `0` when consistent, `1` otherwise. The script enforces:

- schema validity of all three artifacts
- unique identifiers, and task IDs prefixed `TASK-<PROJECT_ID>-`
- every referenced requirement, unknown, conflict, feature, and dependency
  resolves
- an acyclic dependency graph
- the readiness rules below

It also reports warnings that are not violations: implementable requirements no
task covers, and tasks large enough to be worth splitting.

## Readiness

| State | Meaning |
| --- | --- |
| `DRAFT` | Written but not yet checked against the readiness rules. |
| `NEEDS_CLARIFICATION` | An open question must be answered first. |
| `BLOCKED` | A dependency or unavailable external system prevents work. |
| `READY` | May enter the engineering workflow. |
| `IN_PROGRESS` | Handed off and being implemented. |
| `DONE` | Merged, or closed by a completion report. |

A task may be `READY` only when all of the following hold:

- every source requirement is `CONFIRMED`, `CLARIFIED`, or `OPTIONAL`
- no attached unknown or conflict is unresolved
- `blocked_by` is empty
- acceptance criteria exist and are testable
- dependencies are known and resolve to backlog tasks
- the project context is `confirmed` and names a target repository

## Task Identifiers

```text
TASK-<PROJECT_ID>-<NNN>      TASK-UZK-043
```

This satisfies the task ID pattern the engineering workflow already enforces, so
branches, commits, and pull requests need no special handling:

```text
feature/TASK-UZK-043-assign-application
feat(TASK-UZK-043): assign accepted application to specialist
```

`backlog_ref` carries the short human-facing form, for example `UZK-043`.

## Rules

- Do not create a task no requirement supports.
- Do not create a task so large it spans a whole epic. One task is one change.
- Do not mark a task `READY` to unblock progress. Readiness is derived, not
  chosen.
- Do not design an implementation. Naming files, tables, or endpoints here
  pre-empts `inspect-repository` and `plan-change`.
- Do not assign a binding risk level. `risk_level` here is advisory; the binding
  classification is `plan-change`'s, made against the real codebase.
- Do not drop a requirement because it is inconvenient to decompose. Uncovered
  requirements are reported, not hidden.
- Do not present the backlog as approved before the user approves it.
- For a greenfield project, scaffolding tasks describe what must exist, not how
  it should be structured. The structure is decided after repository inspection.

## Required Reasoning

Determine:

- What are the natural areas of this product, in the document's language?
- Which requirements belong together in one deliverable?
- Can this task be implemented, validated, and reviewed as one change?
- What must exist before this task can start?
- What prevents this task from being ready right now?
- Which requirements has nothing covered?

## Output Contract

Return a backlog shaped like:

```json
{
  "project_id": "UZK",
  "status": "approved",
  "approved_at": "2026-09-15T00:00:00Z",
  "epics": [
    {
      "epic_id": "EPIC-02",
      "title": "Authentication & Authorization",
      "objective": "Users authenticate and act only within their role.",
      "source_requirements": ["REQ-AUTH-001"],
      "features": [
        { "feature_id": "FEATURE-02.1", "title": "Authentication", "source_requirements": ["REQ-AUTH-001"] },
        { "feature_id": "FEATURE-02.2", "title": "Authorization", "source_requirements": ["REQ-ROLE-002"] }
      ]
    }
  ],
  "tasks": [
    {
      "task_id": "TASK-UZK-010",
      "backlog_ref": "UZK-010",
      "feature_id": "FEATURE-02.1",
      "title": "Implement login and logout",
      "description": "Provide username and password authentication with session logout.",
      "business_objective": "Only known users reach the application.",
      "actor": "All users",
      "functional_requirements": ["Username and password login.", "Logout ends the session."],
      "acceptance_criteria": [
        "Valid credentials start an authenticated session.",
        "Invalid credentials are rejected without revealing which field was wrong.",
        "Logout ends the session and protected pages redirect to login."
      ],
      "source_requirements": ["REQ-AUTH-001"],
      "dependencies": [],
      "constraints": ["Laravel is mandatory (DEC-001)."],
      "out_of_scope": ["Password reset.", "Two-factor authentication."],
      "test_requirements": ["Feature tests for valid, invalid, and logout paths."],
      "risk_level": "HIGH",
      "open_questions": [],
      "blocked_by": [],
      "readiness": "READY",
      "task_type": "feature",
      "slug": "login-logout"
    }
  ],
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Validate persisted outputs against `schemas/project-backlog.schema.json`.

## Failure Conditions

- The project context is not `confirmed`.
- The requirements index is missing or invalid.
- `check_backlog.py` reports violations that were not fixed.
- The dependency graph contains a cycle.
- The user declines to approve the backlog.

## Escalation Conditions

Escalate when a requirement cannot be decomposed without a decision the user has
not made, when an epic depends entirely on a blocked integration, when the
backlog implies work outside what the factory may do, and when the user asks to
implement the whole specification as one task.

## Completion Criteria

- Every implementable requirement is covered by a task, or is listed as
  uncovered.
- Every task traces to at least one requirement.
- Dependencies are explicit and acyclic.
- Readiness reflects the rules, not convenience.
- `check_backlog.py` exits `0`.
- The backlog was presented and explicitly approved.

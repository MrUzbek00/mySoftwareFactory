---
name: plan-change
description: Transform a task request and inspected repository context into a structured engineering plan without modifying code.
---

# Plan Change

## Purpose

Convert a task request plus inspected repository context into a concrete
engineering plan. This skill must not modify code.

## When to Use

Use this skill after `inspect-repository` has produced repository context and
before any branch, worktree, or implementation activity begins.

Read `references/planning-guidelines.md` when a plan needs examples of useful
specificity, scope control, or risk classification.

## Preconditions

- Repository inspection completed.
- Relevant context available.
- Task requirements available.

If critical requirements are missing, identify them in `unknowns` instead of
inventing them.

## Required Inputs

- `task_id`
- `task_description`
- `repository_context`
- `acceptance_criteria`
- `constraints`

## Workflow

1. Restate the goal in implementation-neutral terms.
2. Summarize current behavior using inspected context only.
3. Define desired behavior and acceptance criteria.
4. Identify affected components, files, public contracts, data models, and
   configuration.
5. Choose the smallest correct change that fits existing architecture.
6. Define implementation steps without executing them.
7. Define the test plan before implementation.
8. Classify risk and determine whether human approval is required.
9. Mark whether the task is ready for `isolate-task`.

## Required Planning Questions

- What is the current behavior?
- What is the requested behavior?
- Which components are affected?
- What is the smallest correct change?
- Could public APIs change?
- Could database schema change?
- Could configuration change?
- What tests must be added or updated?
- What regressions are plausible?
- Does this change require human approval?

## Risk Classification

Use one of:

- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

Classify examples as follows:

- `LOW`: documentation update, isolated internal refactor, trivial UI text
  change.
- `MEDIUM`: normal backend feature, standard API addition, new database field.
- `HIGH`: authentication, authorization, payment or billing, migrations with
  data transformation, infrastructure changes, public API breaking changes.
- `CRITICAL`: destructive production migration, secret management, production
  access, security boundary changes, irreversible operations.

Set `requires_human_approval` to `true` for `HIGH` and `CRITICAL` plans unless a
local policy explicitly says otherwise. Provide `approval_reason` when approval
is required.

## Rules

- Do not modify files.
- Do not add speculative refactors.
- Preserve backward compatibility unless the task explicitly requires a breaking
  change.
- Prefer existing architecture over new abstractions.
- Keep assumptions and unknowns explicit.
- Do not mark the plan ready for isolation if critical requirements are missing.

## Output Contract

Return a structured change plan shaped like:

```json
{
  "task_id": "TASK-001",
  "goal": "",
  "current_behavior": "",
  "desired_behavior": "",
  "affected_components": [],
  "affected_files": [],
  "public_contract_changes": [],
  "database_changes": [],
  "configuration_changes": [],
  "implementation_steps": [],
  "test_plan": [],
  "risks": [],
  "dependencies": [],
  "unknowns": [],
  "risk_level": "MEDIUM",
  "requires_human_approval": false,
  "approval_reason": null,
  "ready_for_isolation": true
}
```

Validate persisted outputs against `schemas/change-plan.schema.json`.

## Failure Conditions

- Repository inspection has not been completed.
- The task is too ambiguous to identify affected components.
- Acceptance criteria conflict with repository constraints.
- Required approvals are needed before planning can continue.

## Escalation Conditions

Escalate when the plan touches security boundaries, irreversible data changes,
production credentials, protected infrastructure, or ambiguous requirements that
could materially change the implementation.

## Completion Criteria

- The plan preserves the task ID.
- Current and desired behavior are distinguishable.
- Affected components and tests are identified.
- Risk is classified using the allowed values.
- Unknowns are explicit.
- `ready_for_isolation` accurately reflects whether isolation can proceed.

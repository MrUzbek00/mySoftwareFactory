---
name: start-from-spec
description: Turn a technical requirements document into a MySoftware Factory project by routing it through requirements intake, a project interview, and backlog decomposition before any code is written.
---

# Start From Spec

## Purpose

Accept a project-level specification and drive it to an approved backlog. This
skill orchestrates; it does not ingest, interview, decompose, or implement. It
must not write application code.

## When to Use

Use this skill when the user supplies a broad specification rather than a scoped
task. Triggers include:

- "start from this technical requirements document"
- "build this project based on this spec"
- "use requirements.docx as the project specification"
- "prepare this project from the technical requirements"
- "turn this specification into work for the software factory"
- "the customer changed requirement 4.8"
- "continue the <project> project"

Do not use this skill for a single feature request, bug report, or ticket. Those
enter at `inspect-repository` as they always have.

Read `references/spec-routing.md` when deciding between a new project, a resume,
and an amendment, or when the document cannot be read directly.

## Preconditions

- A specification document, path, or link is supplied, or can be requested.
- A project artifact root is known or can be defaulted to `.factory/`.

If no specification is supplied, ask for one and stop. Do not infer a project
from conversation alone.

## Required Inputs

- `specification_location`
- `optional_project_id`
- `optional_artifact_root`

## Workflow

1. Resolve the supplied document. Confirm it can actually be read.
2. Look for existing project artifacts under the artifact root.
3. Select a mode:
   - no artifacts: **new project**
   - artifacts present and the specification is unchanged: **resume**
   - artifacts present and a new or changed specification is supplied:
     **amendment**
4. For a new project, run in order:
   1. `ingest-requirements`
   2. `clarify-project` — stop at the intake summary and wait for confirmation
   3. `decompose-spec` — stop at the backlog and wait for approval
5. For a resume, load the existing artifacts, report READY and BLOCKED work, ask
   only questions that became relevant since the last session, and continue from
   the existing backlog.
6. For an amendment, follow the amendment procedure in
   `references/spec-routing.md`. Never overwrite a recorded decision silently.
7. Recommend the first READY task and hand it to `prepare-task`. Stop there.

## Modes

| Mode | Condition | Behavior |
| --- | --- | --- |
| new | no project artifacts exist | full intake: ingest, interview, decompose |
| resume | artifacts exist, same specification | load context, report status, no re-interview |
| amendment | artifacts exist, specification changed | impact analysis, then targeted updates |

## Rules

- Do not write, scaffold, or modify application code in this skill or in any
  skill it calls before the handoff.
- Do not skip the project intake interview for a new project.
- Do not present a backlog before the project context is confirmed.
- Do not hand any task to the engineering workflow before the backlog is
  approved.
- Do not pass a whole specification to `plan-change` or `implement-change` as a
  single task.
- Do not summarize a document the agent could not open. Ask for a readable copy.
- Do not create a second project under an artifact root that already holds one.
- Do not repeat a completed interview on resume.

## Required Reasoning

Determine:

- Is this project-level input or a single scoped task?
- Which mode applies: new, resume, or amendment?
- Can the supplied document actually be read, in full?
- Does a project already exist under this artifact root?
- What is the next gate, and has it been passed?

## Output Contract

Return a routing decision shaped like:

```json
{
  "mode": "new",
  "project_id": "UZK",
  "artifact_root": ".factory",
  "specification": {
    "location": "docs/Uz-Koram-Technical-Requirements.docx",
    "format": "docx",
    "readable": true
  },
  "stages_planned": ["ingest-requirements", "clarify-project", "decompose-spec"],
  "stages_completed": [],
  "current_gate": "project context confirmation",
  "blocked_reason": null
}
```

The artifacts themselves are produced by the skills this one calls and validated
against `schemas/project-context.schema.json`,
`schemas/requirements-index.schema.json`, and
`schemas/project-backlog.schema.json`.

## Artifact Layout

```text
.factory/
  project.json        project context, decisions, amendment history
  requirements.json   requirements index, unknowns, conflicts
  backlog.json        epics, features, tasks, dependencies, readiness
  tasks/<TASK-ID>/    task handoff and the per-task stage artifacts
```

Keep the artifact root outside the repository being built, unless the user asks
for it to be committed. Do not copy the source document into the artifact root;
reference its location instead.

## Failure Conditions

- No specification was supplied and none was provided on request.
- The document cannot be opened, converted, or read in full.
- The artifact root exists but holds artifacts that fail schema validation.
- The user declines to confirm the project context.
- The user declines to approve the backlog.

## Escalation Conditions

Escalate when the specification describes work the factory is not permitted to
do, when the target repository cannot be identified, when a specification change
would invalidate already-merged work, and when the user asks to implement before
a gate has been passed.

## Completion Criteria

- The mode was selected explicitly and reported.
- Every stage the mode requires ran, in order.
- The project context is confirmed and the backlog is approved, or the reason it
  is not is stated.
- A first READY task is recommended, not started.
- No application code was written by this skill.

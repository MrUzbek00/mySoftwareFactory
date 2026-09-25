# Running a Project

From a technical requirements document to a completion report. This document
describes the path end to end. `docs/pipeline.md` describes what each stage
does; this one describes what it is like to run them in order.

For a single ticket or bug report, skip this document. A scoped task enters at
`inspect-repository` and never touches the intake layer.

## Starting From a Specification

Point the factory at a technical requirements document:

```text
Use this technical requirements document: docs/requirements.docx
Start a new MySoftware Factory project from it.
```

What happens, in order:

1. The document is read. If it cannot be opened, the factory asks for a
   readable copy rather than guessing at its contents.
2. Requirements are extracted with source coordinates — document, section,
   subsection, page — and classified. Ambiguities become unknowns and
   contradictions become conflicts, rather than being resolved silently.
3. A mandatory intake interview asks, in one batch, only what the document does
   not already answer. Where the document names a stack, the question is whether
   that stack is binding, not what stack to use.
4. A `PROJECT INTAKE SUMMARY` is presented. Nothing proceeds until it is
   confirmed.
5. The requirements are decomposed into epics, features, and tasks, each
   traceable back to the requirements it implements, with dependencies and a
   readiness state.
6. The backlog is presented. Nothing is implemented until it is approved.
7. One `READY` task at a time is handed to the engineering workflow.

## Where Project State Lives

Project state lives under `.factory/`, outside the repository being built:

```text
.factory/
  project.json        project context, decisions, amendment history
  requirements.json   requirements index, unknowns, conflicts
  backlog.json        epics, features, tasks, dependencies, readiness
  tasks/<TASK-ID>/    task handoff and the per-task stage artifacts
```

The source document is not copied into the artifacts. It stays the source of
truth where it is, and the artifacts reference it by source coordinates.

## Running One Task

Each `READY` task runs the engineering stages in order: inspect, plan, isolate,
implement, validate, then the verification stages, then publication. Each stage
writes its artifact into `.factory/tasks/<TASK-ID>/` before the next one
starts, which is what makes the completion report possible.

The task stops at an open pull request. A human reads the evidence and owns the
merge.

## Resuming

```text
Continue the Uz-Koram project.
```

Existing artifacts are loaded, status is reported, and only newly relevant
questions are asked. The interview is not repeated.

## Amending

```text
The customer changed requirement 4.8.
Use this new version of the requirements document.
```

The change is recorded as an amendment with its own identifier and impact
analysis: affected requirements, decisions, tasks, and completed work. Tasks
that depended on changed requirements leave `READY`. Earlier decisions are
superseded by new ones, never rewritten, so the record of what was decided and
when survives the change.

## A Worked Example

`docs/examples/spec-driven-project.md` walks through the whole path on a
fictional project, including what the readiness gate refuses and why.

`docs/examples/sample-task.md` shows the other entry point: one scoped task
entering at `inspect-repository`, with the artifacts the first stages produce.

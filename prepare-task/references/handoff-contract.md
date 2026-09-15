# Handoff Contract

The handoff is the seam between two halves of the factory. Above it, the
question is "what does the customer want?". Below it, the question is "how is
this built in this codebase?". The contract exists so the second half never has
to read the specification.

## Field Mapping

| Handoff field | Consumed by | As |
| --- | --- | --- |
| `task_id` | every stage | `task_id` |
| `task_title` | `inspect-repository` | `task_title` |
| `task_description` | `inspect-repository`, `plan-change` | `task_description` |
| `repository.path` | `inspect-repository` | `repository_path` |
| `optional_target_paths` | `inspect-repository` | `optional_target_paths` |
| `constraints` | `inspect-repository`, `plan-change` | `optional_constraints`, `constraints` |
| `acceptance_criteria` | `plan-change` | `acceptance_criteria` |
| `task_type`, `task_slug` | `isolate-task` | `task_type`, `task_slug` |
| `repository.base_branch` | `isolate-task` | `base_branch` |
| `test_requirements` | `plan-change`, `validate-change` | test plan input |
| `source_requirements` | `create-pull-request`, `completion-report` | traceability |
| `backlog_ref` | pull request body | human-facing reference |

The field names were chosen to match what the existing skills already ask for.
No downstream skill needs modification to accept a prepared task.

## Task Identifiers

`TASK-<PROJECT_ID>-<NNN>` satisfies the pattern every existing schema enforces,
so the whole chain works unchanged:

```text
task id      TASK-UZK-043
branch       feature/TASK-UZK-043-assign-application
commit       feat(TASK-UZK-043): assign accepted application to specialist
artifacts    artifacts/TASK-UZK-043/plan.json
```

`backlog_ref` carries `UZK-043` for humans reading the backlog.

## Why the Gate Refuses

Each refusal maps to a failure mode that only shows up much later:

| Refusal | What it prevents |
| --- | --- |
| `PROJECT_NOT_CONFIRMED` | Building against assumptions the user never agreed to. |
| `BACKLOG_NOT_APPROVED` | Implementing a decomposition the user has not seen. |
| `TASK_NOT_READY` | Work whose definition is still moving. |
| `TASK_HAS_OPEN_QUESTIONS` | An invented business rule reaching production. |
| `REQUIREMENT_NOT_CONFIRMED` | Code written against one reading of an ambiguity. |
| `REPOSITORY_UNKNOWN` | A change with nowhere legitimate to land. |
| `DEPENDENCY_NOT_DONE` | A feature built on scaffolding that does not exist. |

The gate is a script because a model asked to be helpful will talk itself past
every one of these.

## What the Handoff Deliberately Omits

- The specification document itself. Requirement statements and coordinates are
  enough; the document stays the source of truth where it is.
- Any file, table, endpoint, or module name. That is `plan-change`'s output,
  after `inspect-repository`.
- A binding risk level. `risk_level` travels as advisory context; `plan-change`
  classifies risk against the real code and sets `requires_human_approval`. A
  task the backlog called `LOW` can still turn out to be `HIGH`, and the approval
  gate must fire on the later judgment, not the earlier guess.
- Approval state. Intake approval covers the backlog. It is not approval of any
  plan.

## After the Handoff

1. Mark the backlog task `IN_PROGRESS`.
2. Run `inspect-repository` against `repository.path`.
3. Continue the existing workflow to `completion-report`.
4. When the completion report closes the task, mark it `DONE` in the backlog and
   recompute readiness for tasks that depended on it.

Traceability survives the whole trip: the pull request body carries the task ID,
the backlog reference, and the requirement identifiers, so "why does this change
exist?" is answerable from the pull request alone.

## Greenfield Caveat

For an empty repository, `inspect-repository` still runs. It reports an empty or
skeletal repository, and that report is what `plan-change` uses to decide
structure. Skipping inspection because "there is nothing there" is how an
implementation acquires a layout nobody chose.

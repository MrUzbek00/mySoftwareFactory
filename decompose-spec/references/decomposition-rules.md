# Decomposition Rules

A backlog is useful when each task is small enough to plan, implement, validate,
and review as one change, and when every task can answer the question "why does
this exist?" with a requirement identifier.

## The Shape

```text
PROJECT
  └── EPICS
       └── FEATURES
            └── TASKS
```

Epics follow the product's areas, in the document's language. Features are
deliverable slices of an epic. Tasks are one change each.

```text
EPIC-02 Authentication & Authorization

FEATURE-02.1 Authentication
  TASK-UZK-010  Implement login/logout
  TASK-UZK-011  Protect authenticated routes

FEATURE-02.2 Authorization
  TASK-UZK-012  Implement roles
  TASK-UZK-013  Implement route/page permissions
```

## Task Size

A task is the right size when:

- one person could implement it in one sitting
- it has three to eight acceptance criteria
- it covers one to three requirements, rarely more
- it can be validated by tests that exist or that the task adds
- its pull request would be reviewable in one pass

A task is too large when its title contains "and", when its acceptance criteria
describe several unrelated behaviors, or when it spans more than one feature.

Too large:

```text
TASK-UZK-009  Implement the applications module
```

Right:

```text
TASK-UZK-040  Create purchase application
TASK-UZK-041  List purchase applications by role
TASK-UZK-042  Accept a purchase application
TASK-UZK-043  Assign an accepted application to a specialist
```

## Task Content

Each task carries:

| Field | Purpose |
| --- | --- |
| `task_id` | `TASK-<PROJECT_ID>-<NNN>`, compatible with the engineering workflow |
| `backlog_ref` | short human form, for example `UZK-043` |
| `title` | one behavior, imperative |
| `description` | what changes, in the document's vocabulary |
| `business_objective` | why the customer wants it |
| `actor` | who performs it |
| `functional_requirements` | what it must do |
| `acceptance_criteria` | testable statements a reviewer can check |
| `source_requirements` | the `REQ-` identifiers it implements |
| `dependencies` | tasks that must exist first |
| `constraints` | project decisions that bind this task |
| `out_of_scope` | what a reader might assume is included but is not |
| `test_requirements` | what must be proven before a pull request |
| `risk_level` | advisory only; `plan-change` decides the binding level |
| `open_questions` | unknowns and conflicts that block it |
| `blocked_by` | identifiers preventing readiness |
| `readiness` | derived, never chosen |

## Acceptance Criteria

Testable:

```text
Valid credentials start an authenticated session.
Invalid credentials are rejected without revealing which field was wrong.
An unauthenticated request to a protected page redirects to login.
```

Not testable:

```text
Login works correctly.
The page is user-friendly.
Security is handled.
```

A task whose criteria cannot be tested cannot be `READY`, because
`validate-change` will have nothing to prove.

## Dependencies

Dependencies express what must exist first, not what is conceptually related.

```text
TASK-UZK-043  Assign application to specialist

depends_on:
  TASK-UZK-010  Authentication
  TASK-UZK-012  Roles
  TASK-UZK-022  Users
  TASK-UZK-042  Accepted applications
```

Rules:

- A dependency is another task in the same backlog.
- A task never depends on itself.
- The graph must be acyclic. `check_backlog.py` will find a cycle you did not
  intend.
- When two tasks need each other, one of them is scoped wrong. Split it.
- An unresolved requirement is not a dependency. It goes in `blocked_by`.

## Readiness Is Derived

```text
source requirements implementable?      no -> NEEDS_CLARIFICATION or BLOCKED
open unknowns or conflicts attached?    yes -> NEEDS_CLARIFICATION
blocked_by non-empty?                   yes -> BLOCKED
acceptance criteria testable?           no -> DRAFT
dependencies resolve?                   no -> DRAFT
project context confirmed, repo known?  no -> DRAFT
otherwise                                   -> READY
```

Readiness is recomputed whenever requirements, decisions, or dependencies
change. A task that was `READY` before an amendment is not `READY` afterwards
just because it was.

`IN_PROGRESS` is set at handoff. `DONE` is set when the completion report closes
the task.

## Greenfield Projects

An empty repository still gets tasks, not a blueprint:

```text
TASK-UZK-001  Initialize the application skeleton
TASK-UZK-002  Configure the database connection
TASK-UZK-003  Establish the automated test harness
```

What those tasks must achieve belongs here. How they are structured — directory
layout, module boundaries, configuration style — is decided by `plan-change`
after `inspect-repository` has looked at what is actually there. Decomposition
that names files has designed the application before anyone opened the
repository.

## Existing Codebases

For an existing repository, the specification describes the target behavior, not
the current one. Decomposition still works from requirements only. Which files
change, whether a migration is needed, and what might regress are questions for
inspection and planning, one task at a time.

## Coverage

Every requirement in `CONFIRMED`, `CLARIFIED`, or `OPTIONAL` should be covered by
at least one task. `check_backlog.py` reports uncovered ones as warnings rather
than violations, because some are deliberately deferred — but each one needs an
answer: covered, deferred by decision, or out of scope.

`AMBIGUOUS` and `BLOCKED` requirements may still have tasks. Those tasks stay
unready until the blocker clears.

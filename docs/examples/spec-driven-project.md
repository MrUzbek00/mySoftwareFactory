# Spec-Driven Project

A worked example of the specification intake layer, from a technical
requirements document to one task entering the existing engineering workflow.

The project below is fictional. The point of the example is the behavior of the
skills — what is asked, what is refused, what is recorded — not the application
being described.

```text
technical-requirements.docx
        |
        v
project interview            clarify-project     [gate: confirmation]
        |
        v
project context              project.json
        |
        v
requirements                 requirements.json
        |
        v
epics / backlog              backlog.json        [gate: approval]
        |
        v
one READY task               task-handoff.json   [gate: readiness]
        |
        v
inspect-repository -> plan-change -> ... -> completion-report
```

## 1. The Request

```text
USER:
Use /docs/Uz-Koram-Technical-Requirements.docx and start the project.
```

This is project-level input, not a task. It routes to `start-from-spec`, which
selects mode `new` because no artifacts exist under `.factory/`.

`ingest-requirements` reads the document first. The interview is built from what
it found.

## 2. The Interview

```text
AGENT:
I have reviewed the specification.

Before I create the implementation backlog I need to resolve several
project-level decisions.

The specification currently tells me:
- Web application
- PHP/Laravel backend
- MySQL
- Bootstrap/JavaScript
- Admin, Manager and Specialist roles
- PDF attachments
- Excel/PDF exports
- Potential 1C integration

I need you to confirm:

1. What GitHub repository should contain the application?
2. Is it greenfield or does implementation already exist?
3. Are Laravel/MySQL/Bootstrap mandatory, or are architectural changes
   allowed?
4. Which Laravel/PHP versions should be targeted?
5. Section 6.3 says users are notified when an application is assigned, but
   not how. Email, in-app, or both?
6. Where should uploaded PDFs be stored - local disk or object storage?
7. Where will the application be deployed?
8. Should the 1C integration remain blocked until an API specification is
   supplied?
9. What level of automated testing do you require before a pull request?
10. Should generated backlog items also become GitHub Issues?
```

Note what is not asked. The specification names the stack, so the agent does not
ask what backend to use — it asks whether the stack binds. Questions 5 and 6 come
from unknowns raised during ingestion, not from a checklist.

```text
USER:
1. github.com/owner/uz-koram
2. Greenfield.
3. Mandatory - customer requirement.
4. PHP 8.3, Laravel 11.
5. In-app for now. Email later.
6. Local disk for MVP.
7. Customer VPS, staging first.
8. Yes, keep it blocked.
9. Feature tests for each module.
10. No.
```

## 3. Project Intake Summary

```text
PROJECT INTAKE SUMMARY

Project:                  Uz-Koram Procurement Portal (UZK)
Target repository:        github.com/owner/uz-koram
Project type:             greenfield
Source specification:     Uz-Koram Technical Requirements v1.0 (docx)
Stack:                    PHP 8.3, Laravel 11 (mandatory)
Architecture constraints: Server-rendered Blade views; no SPA
Database:                 MySQL 8
Frontend:                 Bootstrap 5
Authentication:           Session-based, username and password
Roles:                    Admin, Manager, Specialist
External integrations:    1C - BLOCKED, no API specification supplied
Deployment:               Customer VPS; staging then production
Testing expectations:     Feature tests per module before each pull request
Security constraints:     Uploaded PDFs are not publicly addressable
Important business rules: An approved contract is immutable
Open questions:           UNKNOWN-014 (contract editing after approval)
Blocked requirements:     REQ-INT-009 (1C export)
Decisions made:           DEC-001 .. DEC-010

Please confirm this project context.
```

```text
USER:
Approved.
```

Only now does `status` become `confirmed`. No code has been written, and none
will be until a task passes the readiness gate.

## 4. Requirements

`requirements.json`, excerpted. Every entry keeps the document's wording and
coordinates:

```json
{
  "requirement_id": "REQ-APP-021",
  "title": "Assignment of accepted applications",
  "statement": "An accepted application is assigned to a specialist by a manager.",
  "category": "functional",
  "state": "CONFIRMED",
  "priority": "MUST",
  "sources": [
    { "source_id": "SPEC-1", "section": "4.2", "subsection": null, "page": "10-11", "quote": null }
  ],
  "related_requirements": ["REQ-APP-022"],
  "open_questions": [],
  "conflicts": [],
  "notes": ""
}
```

An ambiguity the interview did not settle stays open rather than being decided:

```text
UNKNOWN-014
Related requirement:  REQ-CONTRACT-007
Question:             Can an approved contract still be edited?
Impact:               Affects authorization, audit logs and contract versioning.
Status:               NEEDS_USER_DECISION
```

A contradiction between two sections is recorded, not resolved by preferring the
later one:

```text
CONFLICT-003
Requirement A:        REQ-APP-011 - section 4.2 lets a specialist close an application.
Requirement B:        REQ-APP-019 - section 7.1 reserves closing for a manager.
Reason:               The same transition is assigned to two different roles.
Decision required:    Which role may close an application?
Status:               OPEN
```

And an interview answer becomes a decision with its own provenance:

```text
DEC-001
Question:  Is Laravel mandatory?
Decision:  Yes. Laravel must be used.
Reason:    Customer technical specification.
Source:    User confirmation during project intake.
Date:      2026-09-15
```

## 5. Backlog

```text
EPIC-02  Authentication & Authorization
  FEATURE-02.1  Authentication
    TASK-UZK-010  Implement login/logout                     READY
    TASK-UZK-011  Protect authenticated routes               READY
  FEATURE-02.2  Authorization
    TASK-UZK-012  Implement roles                            READY
    TASK-UZK-013  Implement route/page permissions           READY

EPIC-04  Purchase Applications
  FEATURE-04.2  Application workflow
    TASK-UZK-042  Accept a purchase application              READY
    TASK-UZK-043  Assign application to specialist           READY
    TASK-UZK-044  Close an application                       NEEDS_CLARIFICATION
                  blocked_by: CONFLICT-003

EPIC-07  Contracts
  FEATURE-07.1  Contract lifecycle
    TASK-UZK-070  Edit an approved contract                  BLOCKED
                  blocked_by: UNKNOWN-014

EPIC-09  Integrations
  FEATURE-09.1  1C export
    TASK-UZK-090  Export contracts to 1C                     BLOCKED
                  blocked_by: REQ-INT-009
```

Dependencies are explicit:

```text
TASK-UZK-043  Assign application to specialist

depends_on:
  TASK-UZK-010  Authentication
  TASK-UZK-012  Roles
  TASK-UZK-022  Users
  TASK-UZK-042  Accepted applications
```

The backlog is checked before it is shown:

```bash
python decompose-spec/scripts/check_backlog.py \
  --project-context .factory/project.json \
  --requirements .factory/requirements.json \
  --backlog .factory/backlog.json \
  --schemas-dir schemas
```

```json
{
  "status": "consistent",
  "counts": {
    "requirements": 87,
    "unknowns": 3,
    "conflicts": 1,
    "epics": 9,
    "tasks": 61,
    "readiness": { "READY": 12, "NEEDS_CLARIFICATION": 4, "BLOCKED": 2, "DRAFT": 43 }
  },
  "violations": [],
  "warnings": ["REQ-REP-031 is implementable but no task covers it"]
}
```

Note the shape of this: a specification that produced 87 requirements produced 61
tasks, not one. Three of them cannot be worked on, and the report says which and
why.

The backlog is presented with a recommended first task, and waits for approval.

## 6. Handoff

Once approved, exactly one task is prepared:

```bash
python prepare-task/scripts/prepare_task.py \
  --project-context .factory/project.json \
  --requirements .factory/requirements.json \
  --backlog .factory/backlog.json \
  --task-id TASK-UZK-043 \
  --out .factory/tasks/TASK-UZK-043/task-handoff.json
```

```json
{
  "task_id": "TASK-UZK-043",
  "backlog_ref": "UZK-043",
  "task_title": "Assign application to specialist",
  "task_description": "Assign an accepted purchase application to a specialist.",
  "task_type": "feature",
  "task_slug": "assign-application",
  "repository": {
    "url": "https://github.com/owner/uz-koram",
    "path": "/workspace/uz-koram",
    "base_branch": "main",
    "project_type": "greenfield"
  },
  "acceptance_criteria": [
    "A manager can assign an accepted application to exactly one specialist.",
    "Assignment is rejected for an application that is not accepted.",
    "The assigned specialist sees the application in their own list."
  ],
  "constraints": ["Laravel is mandatory (DEC-001).", "Server-rendered Blade views; no SPA."],
  "dependencies": ["TASK-UZK-010", "TASK-UZK-012", "TASK-UZK-022", "TASK-UZK-042"],
  "source_requirements": [
    {
      "requirement_id": "REQ-APP-021",
      "statement": "An accepted application is assigned to a specialist by a manager.",
      "state": "CONFIRMED",
      "sources": [{ "source_id": "SPEC-1", "section": "4.2", "subsection": null, "page": "10-11" }]
    }
  ],
  "readiness": "READY",
  "open_dependencies": []
}
```

## 7. What the Gate Refuses

Asking for a blocked task produces a refusal, not a best effort:

```bash
python prepare-task/scripts/prepare_task.py ... --task-id TASK-UZK-070
```

```json
{
  "status": "error",
  "error_code": "TASK_NOT_READY",
  "message": "TASK-UZK-070 is BLOCKED, not READY. Blocked by: UNKNOWN-014."
}
```

The same happens for an unapproved backlog, an unconfirmed project context, an
unknown target repository, an ambiguous source requirement, and a dependency
that is not done. Each exits `1` and produces no handoff.

## 8. Into the Existing Workflow

From here nothing is new:

```text
inspect-repository      what is actually in this repository?
plan-change             how is TASK-UZK-043 built here?  [approval if HIGH/CRITICAL]
isolate-task            feature/TASK-UZK-043-assign-application
implement-change        the approved plan, nothing else
validate-change         real commands, real exit codes    [gate: must pass]
security-review         added lines only                  [gate: no CRITICAL]
create-pull-request     one PR, carrying TASK-UZK-043 and REQ-APP-021
completion-report       artifacts cross-checked
```

The specification told the factory *what* to build. `inspect-repository` and
`plan-change` still decide *how*, against the real codebase — including for a
greenfield repository, where inspection reports an empty tree and planning
chooses the structure.

The risk classification, the approval gate, the validation gate, the security
gate, and the human-owned merge are exactly as they were. Intake added a front
door, not an exemption.

## 9. Afterwards

When the completion report closes the task, mark it `DONE` in the backlog and
recompute readiness for whatever depended on it.

Later sessions continue from the artifacts:

```text
USER:
Continue the Uz-Koram project.
```

`start-from-spec` selects mode `resume`, loads the context, and reports status
without re-running the interview.

```text
USER:
The customer changed requirement 4.8.
```

Mode `amendment`: record `AMD-001`, re-ingest the affected section, determine
which requirements, decisions, tasks, and completed work are affected, drop the
affected tasks out of `READY`, and present the impact before continuing. The
earlier decisions are superseded, never rewritten.

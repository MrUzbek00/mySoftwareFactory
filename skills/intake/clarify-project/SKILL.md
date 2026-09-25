---
name: clarify-project
description: Run the mandatory project intake interview, asking only what the specification does not already answer, and produce a confirmed project context.
---

# Clarify Project

## Purpose

Resolve the project-level decisions a specification cannot answer, and record
them as a confirmed project context. This skill must not write code and must not
create backlog tasks.

## When to Use

Use this skill after `ingest-requirements` has produced a requirements index and
before `decompose-spec`. It is mandatory for a new project. It is not repeated
on resume.

Read `references/intake-interview.md` for the question bank, the rules for
subtracting what the document already answers, and the intake summary template.

## Preconditions

- A requirements index exists.
- The unknowns and conflicts raised during ingestion are available.
- The user is available to answer questions.

## Required Inputs

- `project_id`
- `requirements_index`
- `optional_existing_project_context`

## Workflow

1. Read the requirements index first. Build the list of what is already known.
2. Derive candidate questions from the categories in the reference file.
3. Remove every question the specification answers unambiguously.
4. Convert each specification-answered constraint into a confirmation question
   only when its status as mandatory or preferred affects implementation.
5. Add every `UNKNOWN` and `CONFLICT` that blocks a major area of work.
6. Ask the remaining questions in one organized, numbered batch.
7. Record each answer as a `DEC-<NNN>` decision with question, decision, reason,
   source, and date.
8. Update requirement states that the answers resolve: `AMBIGUOUS` becomes
   `CLARIFIED` when a decision settles it.
9. Produce the `PROJECT INTAKE SUMMARY`.
10. Ask the user to confirm or correct it.
11. Set `status` to `confirmed` and stamp `confirmed_at` only after explicit
    confirmation.

## Question Discipline

The specification is read first so the interview does not insult it.

Wrong, when the specification names the stack:

```text
What backend do you want?
```

Right:

```text
The specification requires PHP/Laravel and MySQL.
Should these be treated as mandatory constraints, or are architectural
changes allowed?
```

Ask a question only when a different answer would produce different code. Do not
ask every category. Do not ask one trivial question per turn.

## Mandatory Coverage

Regardless of what the document says, the interview must establish:

- the target GitHub repository, and whether it already exists
- whether the project is greenfield or an existing codebase
- the default or base branch
- whether the factory may create branches and open pull requests
- whether the named stack is mandatory or preferred
- where the application will be deployed, or that this is undecided
- the testing expected before a pull request
- which integrations must stay mocked or blocked

These are the facts without which no task can become `READY`.

## Rules

- No application code may be written, scaffolded, or modified during intake.
- Do not ask a question the specification answers unambiguously.
- Do not accept a stack change that contradicts the customer's specification
  without a recorded decision that says so explicitly.
- Do not invent an answer when the user does not supply one. Leave it open and
  let the affected requirements stay unresolved.
- Do not invent credentials, endpoints, or access to external systems.
- Do not rewrite a requirement's recorded statement. A decision supplements the
  specification; it never edits its history.
- Do not mark the context confirmed without explicit user confirmation.
- Do not proceed to decomposition with the context in `draft`.

## Required Reasoning

Determine:

- What does the specification already answer unambiguously?
- Which unanswered questions change implementation, and which are cosmetic?
- Which unknowns block a whole area of work rather than one task?
- Which constraints are the customer's and which are this user's preference?
- What remains unresolved after the interview, and what does that block?

## Project Intake Summary

Present, in this order:

```text
PROJECT INTAKE SUMMARY

Project:
Target repository:
Project type:
Source specification:
Stack:
Architecture constraints:
Database:
Frontend:
Authentication:
Roles:
External integrations:
Deployment:
Testing expectations:
Security constraints:
Important business rules:
Open questions:
Blocked requirements:
Decisions made during intake:
```

Then ask for confirmation or correction. Implementation does not begin until the
user confirms.

## Output Contract

Return a project context shaped like:

```json
{
  "project_id": "UZK",
  "project_name": "Uz-Koram Procurement Portal",
  "status": "confirmed",
  "confirmed_at": "2026-09-15T00:00:00Z",
  "source_specifications": [
    {
      "source_id": "SPEC-1",
      "title": "Uz-Koram Technical Requirements",
      "location": "docs/Uz-Koram-Technical-Requirements.docx",
      "format": "docx",
      "version": "1.0"
    }
  ],
  "repository": {
    "url": "https://github.com/owner/uz-koram",
    "path": "/workspace/uz-koram",
    "exists": true,
    "project_type": "greenfield",
    "base_branch": "main",
    "may_create_branches": true,
    "may_open_pull_requests": true,
    "create_issues": false
  },
  "stack": { "mandatory": ["PHP 8.3", "Laravel 11"], "preferred": [], "prohibited": [] },
  "architecture_constraints": ["Server-rendered Blade views; no SPA."],
  "database": ["MySQL 8"],
  "frontend": ["Bootstrap 5"],
  "authentication": { "mechanism": "session", "identity_provider": null, "notes": [] },
  "roles": [{ "name": "Manager", "description": "Approves applications.", "source_requirements": ["REQ-ROLE-002"] }],
  "integrations": [{ "name": "1C", "status": "blocked", "notes": "No API specification supplied." }],
  "environment": ["Docker Compose for local development"],
  "deployment": { "targets": ["Customer VPS"], "environments": ["staging", "production"], "ci_cd": [], "notes": [] },
  "testing": { "levels": ["unit", "feature"], "minimum_before_pull_request": ["php artisan test"], "quality_gates": ["Laravel Pint"] },
  "security": { "constraints": [], "compliance": [], "audit_logging": [], "data_retention": [] },
  "business_rules": ["An approved contract is immutable."],
  "delivery": { "scope": "mvp", "priorities": ["Authentication", "Applications"], "milestones": [], "incremental": true, "definition_of_done": ["Tests pass and a pull request is open."] },
  "decisions": [
    {
      "decision_id": "DEC-001",
      "question": "Is Laravel mandatory?",
      "decision": "Yes. Laravel must be used.",
      "reason": "Customer technical specification.",
      "source": "User confirmation during project intake.",
      "date": "2026-09-15",
      "related_requirements": ["REQ-TECH-001"],
      "supersedes": null
    }
  ],
  "open_questions": ["UNKNOWN-014"],
  "blocked_requirements": ["REQ-INT-009"],
  "amendments": [],
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Validate persisted outputs against `schemas/project-context.schema.json`.

## Failure Conditions

- The requirements index is missing or invalid.
- The user does not identify a target repository.
- The user declines to confirm the summary.
- Answers contradict the specification without a recorded decision.
- Mandatory coverage cannot be established.

## Escalation Conditions

Escalate when an answer would require changing the customer's mandated
technology, when a requested integration needs credentials the user cannot
supply, when the answers imply handling regulated data, and when the user asks to
skip the interview.

## Completion Criteria

- Every question asked was one the specification did not already answer.
- Mandatory coverage is established or explicitly marked unresolved.
- Every answer is recorded as a decision with a reason and a source.
- Open questions and blocked requirements are listed, not hidden.
- The summary was presented and explicitly confirmed.
- `status` is `confirmed` and the context validates against its schema.

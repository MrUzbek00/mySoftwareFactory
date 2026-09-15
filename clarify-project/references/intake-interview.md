# Project Intake Interview

The interview exists because a specification describes a product, not a project.
It says what the application does; it rarely says which repository, which branch,
which deployment target, or which of its technology choices are negotiable.

## The Subtraction Rule

Read the requirements index first. Then, for each candidate question:

1. Does the specification answer it unambiguously? If yes, do not ask it.
2. Does the answer change what gets built? If no, do not ask it.
3. Would a wrong assumption here be expensive to undo? If yes, ask it, even if
   the answer seems obvious.

A specification-answered constraint still deserves one question, but a different
one — whether it binds:

```text
The specification requires PHP/Laravel and MySQL.
Should these be treated as mandatory constraints, or are architectural
changes allowed?
```

That is a confirmation question. "What backend do you want?" is an admission
that the document was not read.

## Batch, Do Not Drip

Ask the initial questions as one numbered list, grouped by topic, ten to fifteen
at most. Follow-ups are fine once the answers arrive. A turn-per-question
interview wastes the user's time and loses the thread.

## Question Bank

Draw from these categories. Ask only what survives the subtraction rule.

### Project and repository

- Which GitHub repository should contain the application?
- Does that repository already exist?
- Greenfield, or an existing codebase?
- What is the default or base branch?
- May the factory create branches and open pull requests?
- Should backlog items also become GitHub Issues?

### Technology

- Is the specified stack mandatory or preferred?
- Which framework and language versions are targeted?
- Which database, and is the choice fixed?
- Server-rendered, SPA, or hybrid?
- API architecture, if there is an API?
- Any package, license, or dependency restrictions?
- Existing architecture that must be respected?

### Project environment

- What is required to run this locally?
- Is Docker required, optional, or unwanted?
- How is environment configuration managed?
- Target operating system or server, if it matters?

### Deployment

- Where will the application be deployed?
- Which environments exist — staging, production, other?
- What is expected of CI/CD?
- Any hosting or provider restrictions?

### Authentication and authorization

- Which authentication mechanism is required?
- Is there an existing identity provider?
- Which roles exist?
- Which permissions attach to each role?
- Which role rules in the specification are unclear?

### Files and storage

- Local disk, S3, or another object store?
- File size and type restrictions?
- Retention requirements?

### Integrations

- Which third-party systems are involved?
- Is an API specification available for each?
- Are credentials available?
- Which integrations should stay mocked or blocked for now?

### Quality

- What testing is expected?
- Unit, integration, browser, or a subset?
- What must pass before a pull request is opened?
- Lint, formatting, or static analysis requirements?

### Security

- Is sensitive or regulated data involved?
- Any compliance constraints?
- Is audit logging required?
- Data retention rules?
- Access control expectations beyond roles?

### Product and business rules

- Each ambiguity raised during ingestion that blocks an area of work.
- Status workflows that are not precisely defined.
- Approval sequences and their reversals.
- Delete and edit rules, per role.
- Notification channels, triggers, and recipients.
- Edge cases the document does not address.

### Delivery

- MVP or full scope?
- Which modules come first?
- Deadlines or milestones?
- Incremental delivery, or one release?
- What counts as done?

## Recording Decisions

Every answer becomes a decision:

```text
DEC-001
Question:
Is Laravel mandatory?

Decision:
Yes. Laravel must be used.

Reason:
Customer technical specification.

Source:
User confirmation during project intake.

Date:
2026-09-15
```

Rules that keep the record honest:

- A decision supplements the specification. It never edits a requirement's
  recorded statement or its source coordinates.
- When a decision resolves an ambiguity, the requirement moves to `CLARIFIED`
  and names the decision in `resolved_by`. The original wording stays.
- When a later decision reverses an earlier one, record a new decision with
  `supersedes` set. Do not delete the old one.
- An unanswered question stays an unknown. Silence is not consent.

## The Gate

After the summary is presented:

- The user confirms, and the context becomes `confirmed`.
- The user corrects, and the corrections become decisions, then re-present.
- The user does not respond, and nothing proceeds.

No application code is written during any of this. Decomposition does not start
until the gate is passed, and implementation does not start until the backlog is
approved after that.

---
name: ingest-requirements
description: Extract requirements from a source specification into a traceable index, preserving the customer's meaning and exposing ambiguities instead of resolving them.
---

# Ingest Requirements

## Purpose

Transform a source specification into structured, traceable requirements without
changing what it says. This skill must not write code, propose architecture, or
invent anything the document does not contain.

## When to Use

Use this skill after `start-from-spec` has resolved a readable specification and
before the project intake interview. The interview needs to know what the
document already answers, which is what this skill produces.

Read `references/requirement-extraction.md` for classification rules, source
coordinates, and the difference between an ambiguity and an unknown.

## Preconditions

- The specification can be read in full, or the readable portion is known.
- A project identifier exists or can be proposed.

## Required Inputs

- `project_id`
- `specification_location`
- `specification_format`
- `optional_specification_version`

## Workflow

1. Register each source document with a `SPEC-` identifier, its location,
   format, and version.
2. Read the document in order. Do not skip sections because they look
   uninteresting.
3. Extract each requirement as a separate entry with a `REQ-<AREA>-<NNN>`
   identifier.
4. Record the statement in the source's own terminology.
5. Record source coordinates: document, section, subsection, page.
6. Classify category and state.
7. Raise an `UNKNOWN-<NNN>` for every question whose answer would change the
   implementation.
8. Raise a `CONFLICT-<NNN>` for every pair of requirements that cannot both
   hold.
9. Link related requirements to each other.
10. Return the index. Do not begin decomposition.

## Rules

- Treat the document as the authoritative business specification.
- Preserve the source's terminology, including domain words that sound wrong.
  Rename nothing.
- Do not silently improve, tighten, generalize, or modernize a requirement.
- Do not invent a requirement the document does not state, however obvious it
  seems.
- Do not resolve an ambiguity by choosing the likely reading. Raise it.
- Do not mark a requirement `CONFIRMED` while it depends on an unanswered
  question.
- Do not propose frameworks, schemas, endpoints, or file layouts. Architecture
  belongs to `inspect-repository` and `plan-change`.
- Do not copy the document into the artifacts. Reference its coordinates.
- Do not extract requirements from a section that could not be read.

## Classification

Category:

`functional`, `non-functional`, `security`, `authorization`, `data`,
`reporting`, `integration`, `ui-ux`, `operational`, `deployment`,
`documentation`, `unknown`.

State:

| State | Meaning |
| --- | --- |
| `CONFIRMED` | Stated clearly enough to implement, with nothing unresolved. |
| `CLARIFIED` | Was unclear; a recorded decision resolved it. |
| `AMBIGUOUS` | More than one reasonable reading. Needs a decision. |
| `BLOCKED` | Depends on something unavailable, such as an external API spec. |
| `OPTIONAL` | Stated as desirable rather than required. |
| `OUT_OF_SCOPE` | Explicitly excluded, or deferred by decision. |

Priority is `MUST`, `SHOULD`, `COULD`, `WONT`, or `UNSPECIFIED`. Use
`UNSPECIFIED` unless the document expresses priority. Do not assign priority by
intuition.

## Required Reasoning

For each candidate requirement, determine:

- Is this a requirement, or background narrative?
- What exactly does the source say, in its words?
- Where does it come from — section, subsection, page?
- Could it be read more than one way?
- Does it contradict another requirement?
- Does it depend on a system, credential, or specification that is unavailable?
- Is anything technically incomplete — a status without transitions, a role
  without permissions, an export without a format?

## Output Contract

Return a requirements index shaped like:

```json
{
  "project_id": "UZK",
  "sources": [
    {
      "source_id": "SPEC-1",
      "title": "Uz-Koram Technical Requirements",
      "location": "docs/Uz-Koram-Technical-Requirements.docx",
      "format": "docx",
      "version": "1.0",
      "received": "2026-09-15"
    }
  ],
  "requirements": [
    {
      "requirement_id": "REQ-AUTH-001",
      "title": "Username and password authentication",
      "statement": "The application must provide username/password authentication.",
      "category": "security",
      "state": "CONFIRMED",
      "priority": "MUST",
      "sources": [
        { "source_id": "SPEC-1", "section": "9.1", "subsection": null, "page": "4", "quote": null }
      ],
      "related_requirements": ["REQ-AUTH-002"],
      "open_questions": [],
      "conflicts": [],
      "notes": ""
    }
  ],
  "unknowns": [
    {
      "unknown_id": "UNKNOWN-014",
      "related_requirements": ["REQ-CONTRACT-007"],
      "question": "Can an approved contract still be edited?",
      "impact": "Affects authorization, audit logs and contract versioning.",
      "status": "NEEDS_USER_DECISION",
      "resolved_by": null
    }
  ],
  "conflicts": [
    {
      "conflict_id": "CONFLICT-003",
      "requirement_a": "REQ-APP-011",
      "requirement_b": "REQ-APP-019",
      "reason": "Section 4.2 lets a specialist close an application; section 7.1 reserves closing for a manager.",
      "decision_required": "Which role may close an application?",
      "status": "OPEN",
      "resolved_by": null
    }
  ],
  "generated_at": "2026-09-15T00:00:00Z"
}
```

Validate persisted outputs against `schemas/requirements-index.schema.json`.

## Failure Conditions

- The specification cannot be read, or only partially.
- The document contains no extractable requirements.
- Source coordinates cannot be determined for any requirement.
- The project identifier conflicts with an existing project.

## Escalation Conditions

Escalate when the document contradicts itself structurally, when whole sections
reference an attachment that was not supplied, when requirements describe
handling of regulated data, and when the specification mandates something the
factory is not permitted to do.

## Completion Criteria

- Every extracted requirement has an identifier, a statement, and at least one
  source coordinate.
- Categories and states use the allowed values.
- Ambiguities are `UNKNOWN` entries, not decisions.
- Contradictions are `CONFLICT` entries, not a chosen reading.
- No architecture, schema, or file layout was proposed.
- The index validates against its schema.

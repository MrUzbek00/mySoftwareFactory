# Specification Routing

This file covers the three decisions `start-from-spec` has to make before any
other skill runs: what kind of input this is, which mode applies, and whether
the document can actually be read.

## Project Input Versus Task Input

| Signal | Project input | Task input |
| --- | --- | --- |
| Length | sections, chapters, page numbers | a paragraph |
| Scope | a system, or a release of one | one behavior |
| Roles | multiple actors described | usually one |
| Unknowns | many, spread across topics | few, local |
| Repository | often not named | already known |

Document types that are project input: technical requirements, BRD, SRS,
functional specification, tender specification, statement of work, RFP response.

Document types that are task input: a ticket, an issue, a bug report, a review
comment, a one-line feature request. These go straight to `inspect-repository`.

When the input is genuinely ambiguous, ask. Do not start a full intake for a
one-paragraph request, and do not send a 40-page specification to `plan-change`.

## Mode Selection

```text
artifacts exist at artifact root?
  no  -> new
  yes -> same specification, no change requested?
           yes -> resume
           no  -> amendment
```

Compare specifications by location plus version or content digest, not by
filename alone. A file with the same name and different content is an amendment,
not a resume.

## Resume

1. Load `project.json`, `requirements.json`, and `backlog.json`.
2. Validate them. Corrupt or schema-invalid state is a stop, not a repair job.
3. Report: confirmed project context, counts by readiness, open unknowns, open
   conflicts, tasks in progress, tasks done.
4. Ask only questions that are newly relevant — an unknown that became blocking,
   a decision whose assumption expired, a dependency that changed.
5. Recommend the next READY task.

Never re-run the full interview on resume. The interview exists to establish
project context; the context already exists.

## Amendment

An amendment is a change to the source specification or to an earlier decision.
Typical prompts: "the customer changed requirement 4.8", "use this new version
of the requirements document", "section 6 has been rewritten".

Procedure:

1. Record an amendment entry in `project.json` with a new `AMD-` identifier, the
   date, the source, and a summary of what changed.
2. Re-ingest only the affected part of the specification with
   `ingest-requirements`. Keep requirement identifiers stable where the meaning
   is unchanged.
3. Determine impact and record it in the amendment entry:
   - affected requirements
   - affected decisions
   - affected backlog tasks
   - completed work that the change may have invalidated
4. Requirements whose meaning changed move out of `CONFIRMED`. Tasks that
   depended on them leave `READY`.
5. Where an amendment contradicts a recorded decision, do not edit the decision.
   Record a new decision that `supersedes` the old one.
6. Re-run `decompose-spec` for the affected epics only, then re-run
   `check_backlog.py`.
7. Present the impact summary and ask for approval before continuing.

Completed work is never silently rewritten. If merged code no longer satisfies
an amended requirement, that becomes a new backlog task with its own
traceability, not an edit to a closed one.

## Unreadable Documents

The factory ships no document parser. The agent reads the specification with the
tools it has.

- If a DOCX, PDF, or scan cannot be opened, say so and ask for a text, Markdown,
  or exported copy.
- If only part of a document can be read, state exactly which part, and do not
  extract requirements from the unread part.
- If a link requires authentication, ask for the content rather than guessing at
  it.

A specification the agent could not read produces no requirements. Summarizing
an unread document is fabrication, and everything downstream inherits it.

## Project Identifier

The project identifier is a short uppercase key, two to ten characters, chosen
with the user during intake — for example `UZK`. It prefixes every backlog task
as `TASK-<KEY>-<NNN>`, which keeps generated tasks compatible with the existing
task ID, branch, and commit conventions.

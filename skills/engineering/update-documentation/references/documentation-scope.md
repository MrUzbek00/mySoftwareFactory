# Documentation Scope

The failure mode here is not missing a document. It is turning a small task into
a documentation project because everything nearby looked slightly wrong.

## The Test

A document is in scope when the change made something it says **untrue**.

Not out of date in spirit. Not written before a convention settled. Untrue, as
of this change, because of this change.

Everything else is someone else's task, and belongs in
`documents_out_of_scope` where a reviewer can see you found it.

## In Scope

- A documented command, flag, option, or default that this change altered.
- An example whose output this change changed.
- An API reference for an endpoint, field, or error this change touched.
- A setup or configuration step this change made wrong.
- A docstring on a function whose behavior or signature this change changed.
- A stated limit, timeout, or constraint this change moved.

## Out of Scope

- Prose that is vague, dated, or awkward but still accurate.
- Documentation for code this change did not touch.
- A missing document the project never had.
- Formatting, heading structure, and link style.
- A typo you noticed in passing — unless you were editing that line anyway.
- Documentation that was already wrong before this change. Report it; it is
  evidence of a separate problem and a reviewer should hear about it.

## Where Staleness Hides

Prose describing behavior is usually fine, because it is vague enough to survive.
What breaks is anything that quotes a concrete value:

- a shell transcript showing output that has since changed
- a sample config with a key this change renamed
- a code snippet using a signature this change altered
- a table of flags, defaults, or error codes
- `.env.example` and sample fixtures
- badge URLs and version strings maintained by hand

Search for the concrete thing — the flag name, the config key, the error string
— rather than the concept. Grep finds `--reset-timeout`; it does not find "the
timeout behavior."

## Generated Documentation

If a document is generated — from docstrings, an OpenAPI spec, a schema, a
type definition — edit the source and regenerate. Editing the generated file
produces a change that the next build silently reverts.

When you cannot regenerate because the toolchain is unavailable, say so. Do not
hand-edit the output as a substitute.

## Recording "No Change"

The three lists exist to separate *checked and fine* from *never looked*. A
report with an empty `documents_reviewed_no_change` and no updates is
indistinguishable from not having run the stage.

Name the documents you opened, even when you changed nothing. That is the part a
reviewer cannot reconstruct.

## Conventions Come From the Repository

Match what is already there: the tense, the person, the heading depth, the way
code blocks are labeled, whether options appear in a table or a list.

Do not introduce a changelog, an ADR format, a docs framework, or a new section
convention as part of a task about something else. If the project would benefit
from one, that is a proposal, not an edit.

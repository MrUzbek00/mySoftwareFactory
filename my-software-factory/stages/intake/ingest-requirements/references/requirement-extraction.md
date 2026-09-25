# Requirement Extraction

Extraction is transcription with structure. The test for a good index is that a
reader who has the source document can check every entry against it, and a
reader who does not can tell exactly where to look.

## Identifiers

```text
REQ-<AREA>-<NNN>      REQ-AUTH-001, REQ-APP-021, REQ-EXPORT-004
UNKNOWN-<NNN>         UNKNOWN-014
CONFLICT-<NNN>        CONFLICT-003
```

`AREA` is a short uppercase token drawn from the document's own vocabulary, not
from an implementation guess. A specification that talks about "applications"
gives `REQ-APP-*`, not `REQ-ORDER-*`.

Identifiers are permanent. When an amendment changes a requirement's wording but
not its subject, keep the identifier and record the change. When a requirement
is genuinely replaced, issue a new identifier and mark the old one
`OUT_OF_SCOPE`.

## Source Coordinates

Record enough to find the text again:

```text
REQ-AUTH-001
Source:
Uz-Koram Technical Requirements
Section 9.1
Page 4

Requirement:
The application must provide username/password authentication.
```

Page numbers are strings, because real citations look like `10-11`. Section and
subsection may be `null` when the document has no numbering, but then the entry
needs a quote so the text can still be located.

## Preserving Meaning

Extraction records what the document says. It does not:

- rename a domain concept to a more familiar one
- merge two similar requirements into one tidier statement
- split one requirement into several without saying so
- add a limit, format, or default the document did not state
- resolve a vague word like "quickly" or "securely"

An imprecise requirement stays imprecise in the index, and the imprecision
becomes an `UNKNOWN`.

## Unknowns

Raise an unknown whenever the answer would change what gets built. The entry
names the impact, because that is what tells the user why it matters:

```text
UNKNOWN-014
Related requirement:
REQ-CONTRACT-007

Question:
Can an approved contract still be edited?

Impact:
Affects authorization, audit logs and contract versioning.

Status:
NEEDS_USER_DECISION
```

Common sources of unknowns:

- a status named but no transitions between statuses
- a role named but no permissions
- an approval step with no stated sequence or reversal
- delete and edit rules that are described for one actor and not others
- notifications with no channel, trigger, or recipient
- an export with no format, columns, or filters
- a limit implied but never stated

Never guess a critical business rule. An invented rule is indistinguishable from
a real one once it reaches the code, and the customer finds out last.

## Conflicts

```text
CONFLICT-003

Requirement A:
REQ-APP-011 - section 4.2 lets a specialist close an application.

Requirement B:
REQ-APP-019 - section 7.1 reserves closing for a manager.

Reason for conflict:
The same transition is assigned to two different roles.

Decision required:
Which role may close an application?
```

Both requirements stay in the index. Both move to `AMBIGUOUS`. Neither is
deleted, and neither is quietly preferred because it appears later in the
document.

## Blocked Requirements

Mark `BLOCKED` when implementation depends on something that does not exist yet:

- an external API with no specification supplied
- credentials that have not been issued
- a system that the customer has not granted access to
- a document section that references a missing attachment

A blocked requirement can still be decomposed into a task, but that task cannot
become `READY`. Do not unblock it by assuming an API shape, inventing a
credential, or writing a client against a guessed contract.

## Technically Incomplete Requirements

These read as complete but cannot be implemented as written:

- "The system stores documents" — no size limit, type restriction, or retention
- "Managers approve requests" — no rejection path, no reassignment, no timeout
- "The report shows monthly figures" — no columns, no currency, no timezone
- "Users are notified" — no channel, no timing, no failure behavior

Record the requirement as stated, then raise the specific gap as an unknown.
Do not fill the gap with a plausible default.

## What Belongs to Other Skills

| Question | Skill |
| --- | --- |
| What does the customer want? | `ingest-requirements` |
| What project-level decisions are missing? | `clarify-project` |
| What pieces of work are required? | `decompose-spec` |
| What exists in this codebase? | `inspect-repository` |
| How should this task be built here? | `plan-change` |

Extraction that proposes tables, endpoints, or a directory layout has crossed
into planning before anyone has looked at the repository.

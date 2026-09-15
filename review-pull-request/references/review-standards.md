# Review Standards

A review that lists twelve small things and misses the one real problem is worse
than useless, because it looks thorough.

## What Counts as a Finding

A finding names something that would cause a problem: wrong behavior, a broken
contract, a security hole, a missing test for a path the change introduced, or
scope the description does not account for.

If you cannot finish the sentence "this is a problem because…" with a
consequence, it is not a finding.

## What Does Not

- Style the repository's formatter already accepts.
- Naming you would have chosen differently.
- A refactor you would prefer, absent a defect.
- Test coverage for behavior this change did not touch.
- Anything phrased as "consider" with no stated consequence.

Preferences are not worthless, but they are not findings. Say them as
preferences, or leave them out.

## Backend Code Quality

`standards/backend-code-quality.md` is the criteria set for readability, typing,
and contract clarity. A review uses the same criteria `validate-change` used, so
the author does not get two different answers about the same code.

Map its severity onto this skill's scale: a `BLOCKING` quality finding is at
least `HIGH` here, because an unusable contract causes wrong behavior at the
next call site. An `ADVISORY` finding is a preference, and the section above
already says where preferences belong.

## Severity

| Severity | Meaning |
| --- | --- |
| `CRITICAL` | Data loss, security hole, or production break if merged. |
| `HIGH` | Wrong behavior in a realistic case, or a broken contract. |
| `MEDIUM` | Right today, fragile under a plausible future change. |
| `LOW` | Minor; the author may reasonably decline. |

Severity describes consequence, not confidence. When you are unsure whether the
problem is real, say so in the rationale and keep the severity honest.

## Reading Order Matters

Read the description first, then the checks, then the diff.

A diff read cold produces line-level nitpicks, because that is all a cold read
can see. A diff read against a stated intent produces the question that actually
matters: does this do what it says, and what does it do that it does not say?

## Questions That Find Real Problems

- What input makes this behave incorrectly?
- What happens on the second call — is it idempotent?
- What happens when this fails halfway?
- Who can reach this code path, and what may they see?
- Which test would fail if this change were reverted? If none, what is proven?
- Was a test weakened, skipped, or deleted in this diff?
- Does the diff contain anything the description does not mention?

The last two are the ones authors most often hope nobody checks.

## Verified Versus Inferred

Say which you did. "The test at line 40 covers the expired case" is verified.
"This probably handles the expired case" is inferred, and should be written that
way — or resolved by reading the code.

An inference stated as a fact is how a review launders a guess into an approval.

## Red Checks

A failing check is a finding until explained. "Probably flaky" is a hypothesis;
the check log is the evidence. If you did not read it, say you did not.

## The Boundary

This skill reviews. It does not approve, merge, request changes as a formal
GitHub review action, or comment on the pull request unless the user explicitly
asks.

That boundary is not a limitation of the tooling — `fetch_pull_request.py` is
read-only on purpose. A review is advice to a human who holds the decision. If
someone asks you to approve or merge, escalate rather than comply.

## Truncated Diffs

Large diffs are truncated at fetch. Review what you read and say what you did
not. A review that silently covers 40% of a change is a false signal, and the
author has no way to know.

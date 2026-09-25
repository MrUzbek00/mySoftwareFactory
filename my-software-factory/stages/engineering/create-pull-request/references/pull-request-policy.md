# Pull Request Policy

The pull request is where automated work stops and human judgment starts. Its
job is to make that judgment cheap: a reviewer should be able to tell what
changed, what proves it works, and where to look hard.

## The Boundary

This stage may:

- push one task branch with upstream tracking
- open one pull request
- add labels and request reviewers

This stage may not:

- merge, or enable auto-merge
- approve, or dismiss a review
- force push, or rewrite history
- bypass required status checks
- modify branch protection
- close or reopen other pull requests

The merge button belongs to a person. That is the whole point of stopping here.

## Why No Force Push

A force push can destroy review history and other people's commits, and it is
not recoverable from the remote alone. `open_pull_request.py` has no force path.
When a push is rejected, the script reports `PUSH_REJECTED` and stops, because
the correct resolution — rebase, merge, or abandon — is a judgment call about
someone else's work.

## Writing the Body

A reviewer reads the body before the diff. Include:

**Summary** — the task ID and what changed, in one paragraph, in terms of
behavior rather than files.

**What changed** — the specific behavioral differences, each one checkable
against the diff.

**Validation evidence** — every check from the validation report with its
command and exit code. Copy the recorded results; do not paraphrase them into
"all tests pass."

**Risk** — the plan's risk level, and what a reviewer should scrutinize.

**Unknowns and deviations** — what the plan assumed that turned out untrue, what
was deliberately left out, and what is still not understood.

Omit: restating the diff line by line, praising the change, and speculation
about future work.

## Draft or Ready

Open as a draft when any of these hold:

- the plan's risk level is `HIGH` or `CRITICAL`
- the change touches a public contract or a database schema
- any validation check was `not_run`
- unknowns remain that a reviewer would need to resolve

A draft signals that the change needs a conversation before it needs approval.
Otherwise open it ready, so it enters the normal review queue.

## One Task, One Pull Request

The script refuses when an open pull request already exists for the branch. A
second pull request for the same task splits the review and the history. If the
existing one needs changes, push more commits to the same branch — that is what
the upstream tracking is for.

## Secrets

The title and body are published to the remote and are effectively permanent,
including in notification emails, even if edited later. Nothing derived from a
`.env` file, a credential store, or a token belongs in either. When evidence
output would contain a secret, describe the check result rather than pasting the
output.

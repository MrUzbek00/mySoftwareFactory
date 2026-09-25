# Revision Discipline

Revision is the stage where a clean pull request turns into a mess: history gets
rewritten, unrelated changes ride along, and threads quietly go unanswered.

## Never Rewrite a Branch Under Review

`push_revision.py` has no force path, and refuses to push a diverged branch.
The reasons are concrete:

- **Comments detach.** Review threads anchor to commits. Rewrite them and threads
  go outdated or orphaned, and the conversation stops pointing at code.
- **Review state resets.** Approvals and resolved threads can be invalidated,
  and reviewers are asked to re-read work they already did.
- **Other people's commits vanish.** A reviewer or a bot may have pushed to the
  branch. A force push drops that silently and unrecoverably from the remote.
- **Nobody can see what you changed.** The point of a revision is that a reviewer
  can read the delta since their comment. A rewritten branch hides it.

Squashing is a merge-time decision. GitHub can squash on merge, and that choice
belongs to whoever presses the button.

## Diverged Means Stop

`DIVERGED_BRANCH` means the remote has commits you do not have, and you have
commits it does not. Resolving it means deciding what happens to someone else's
work — a rebase discards their commit objects, a merge preserves them and
changes your history's shape.

That is a human decision. Escalate with the counts the script reported; do not
pick one because it unblocks you.

`BRANCH_BEHIND` is simpler: pull first, re-validate, then push.

## Every Thread Gets an Answer

An unresolved thread with no response is the most common way review feedback
dies. Each one ends in `feedback_addressed` or `feedback_declined`. There is no
third list.

Addressing a thread means the code changed. Saying "good point" and changing
nothing is declining it, and should be recorded as such.

## Declining Well

Legitimate reasons to decline:

- the comment rests on a misreading of the code
- the request conflicts with the approved plan
- the work belongs to a different task
- the change would raise the risk level the plan was approved at

A decline names the thread and gives a reason the reviewer can evaluate and
push back on. What it must not be is silence, or a reply that restates the
implementation without engaging.

Not a legitimate reason: it is tedious, it is a large diff, or you disagree
about taste and would rather not discuss it.

## Scope Creep Is Worse Here

During revision, the branch already exists and the diff is already large. Adding
"one more small thing" is easy and nearly invisible to a reviewer who is
re-reading a change they thought they understood.

Only the accepted feedback gets implemented. Anything else you notice becomes a
separate task, including bugs — especially bugs, because a fix buried in a
revision commit gets far less scrutiny than one in its own pull request.

## Re-Validate Every Time

A validation report describes a specific commit. After new commits, it describes
history.

Re-run `validate-change` on every revision, no matter how small. A one-line
change that "cannot break anything" is the standard preamble to a broken build,
and the cost of re-running is a few seconds against a reviewer's time.

Re-run `security-review` too when the revision touched anything it covers.

## Resolving Threads

Do not mark a reviewer's thread resolved on their behalf unless the user asks.
Resolution signals that the reviewer is satisfied, which only the reviewer knows.

Push the commit, describe what changed in the revision result, and let them
close it.

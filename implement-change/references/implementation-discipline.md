# Implementation Discipline

Implementation is the stage where scope quietly expands. The plan is the
contract. Everything else is a separate task.

## In Scope

- Edits that correspond to a named implementation step.
- Tests named in the plan's test plan.
- Imports, wiring, and type updates required to make those edits compile and run.
- Documentation the plan explicitly asked for.

## Out of Scope

- Renaming things the plan did not name.
- Reformatting files you happened to open.
- Upgrading dependencies to fix an unrelated warning.
- Fixing a bug you noticed nearby. Report it; do not absorb it.
- Adding an abstraction because a future task might need it.
- Deleting code that looks unused without evidence that it is.

A good rule: if you cannot point at the implementation step that requires an
edit, the edit belongs to a different task.

## Tests Are Not Negotiable

The fastest way to make a suite green is to weaken it. That is prohibited, and
it is worth stating plainly why: a suite that was weakened to pass no longer
tells anyone whether the change works.

Prohibited:

- deleting or commenting out a failing assertion
- adding a skip marker to avoid a failure
- broadening an assertion until it cannot fail
- catching and swallowing an exception the test was written to surface
- changing expected values to match observed wrong output

If a test genuinely encodes obsolete behavior, that is a plan change, not an
implementation decision. Stop and say so.

## Commit Hygiene

- One logical change per commit.
- The task ID appears in every commit message.
- Commits build. Do not commit a known-broken intermediate state.
- Never amend or rebase commits already pushed to the remote.
- Never commit `.env` files, keys, tokens, or credential fixtures.

## When the Plan Is Wrong

Plans are written before the code is fully understood, so some plans are wrong.
That is expected and it is not a failure.

What is a failure is silently implementing something different from what was
approved. When the plan does not survive contact with the code:

1. Stop implementing.
2. Record what the plan assumed and what is actually true.
3. Return to `plan-change` with that evidence.

A recorded deviation covers a small difference in how a step was carried out.
It does not cover a different design, a different contract, or a different risk
level.

## Working Inside the Worktree

The isolated worktree is the only writable surface for this task. Before the
first edit, confirm:

- the current directory is the worktree from `workspace_result`
- the branch matches the task ID
- the working tree is clean

Editing the source checkout instead of the worktree is the most common way this
stage causes damage, and it is silent when it happens.

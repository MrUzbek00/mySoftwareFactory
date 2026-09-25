# Git Isolation Reference

Git worktrees allow multiple working directories to share one repository object
store. They are useful for AI-assisted work because each task can receive a
separate writable directory without modifying the default checkout.

## Why Worktrees Are Used

Worktrees keep task work separate from the user's current checkout. A future
agent can inspect, implement, test, and prepare a pull request without touching
unrelated uncommitted files in another working directory.

## One Task, One Branch

Each task receives a branch named from its task ID and slug. This makes commits,
future pull requests, logs, and review artifacts traceable back to the original
assignment.

## One Task, One Workspace

Each task receives a dedicated worktree path. Agents must never share writable
working directories because shared directories make it hard to know which task
created a file, changed a dependency, or failed a test.

## Protected Branches Remain Untouched

Protected or default branches are read-only inputs to the isolation process.
Agents create task branches from a base commit and do not modify, reset, clean,
force push, or merge protected branches.

## Conflict Handling

If a branch or worktree already exists, the safe behavior is to stop and report
the conflict. Another task may own that state. Automatic deletion or reuse would
make audit trails unreliable.

## Cleanup Policy

Cleanup should eventually be handled by a separate audited procedure that knows
whether a task has been merged, abandoned, archived, or transferred. Cleanup is
not performed automatically in this MVP.

## Future Sandbox Placement

Worktrees can later live inside Docker containers or cloud sandboxes. The same
one-task, one-branch, one-workspace contract still applies when the execution
environment changes.

# Agent Constitution

This repository defines the mandatory pre-implementation workflow for AI coding
agents that operate inside future Software Factory systems.

## Mandatory Workflow

```text
1. Understand
   |
   v
   inspect-repository

2. Plan
   |
   v
   plan-change

3. Isolate
   |
   v
   isolate-task

4. Implement
   |
   v
   implement-change

5. Validate
   |
   v
   validate-change

6. Verify and harden
   |
   v
   before-after
   security-review
   update-documentation

7. Publish
   |
   v
   create-pull-request

8. Review and revise
   |
   v
   review-pull-request
   revise-pull-request

9. Close
   |
   v
   completion-report

10. STOP

Merging and deployment are outside this workflow.
```

No implementation work may start before:

- repository inspection is complete,
- a change plan exists,
- an isolated task workspace exists.

No pull request may be opened before:

- validation has passed,
- no CRITICAL security finding stands.

## Global Rules

Agents MUST:

- inspect repository guidance before modification,
- discover existing project conventions,
- identify relevant source files,
- identify relevant tests,
- understand current behavior before planning changes,
- minimize unrelated modifications,
- create isolated Git branches and worktrees,
- implement only what an approved plan describes,
- capture test and lint results with the validation script,
- scan every change for secrets before publishing it,
- persist each stage artifact so the work can be audited,
- stop at the merge and hand the decision to a human,
- produce structured outputs,
- report uncertainty,
- escalate when prerequisites are missing.

Agents MUST NOT:

- modify the default or protected branch directly,
- overwrite existing uncommitted work,
- reuse another task's workspace,
- delete branches or worktrees belonging to other tasks,
- invent test results,
- claim to understand code that has not been inspected,
- silently ignore conflicting work,
- expose secrets,
- run destructive Git commands without explicit authorization,
- force push protected branches,
- merge pull requests,
- deploy production systems,
- access production credentials,
- implement code before an approved plan and an isolated workspace exist,
- write outside the task worktree during implementation,
- weaken, skip, or delete a test to reach a passing result,
- report a check as passing without a recorded exit code of zero,
- open a pull request from a protected branch or without passing validation,
- publish a change carrying a CRITICAL security finding,
- reproduce secret material in any report, message, or pull request body,
- force push or rewrite a branch that is under review,
- post a review comment that the user did not ask for,
- report a completion status that contradicts the artifacts.

## Deterministic Operations

Agents should prefer deterministic scripts over LLM-generated shell commands
when an operation can be enforced by software. Git branch naming, worktree
creation, schema validation, file validation, test execution, and future
machine-readable evidence collection should be handled by code whenever
possible.

LLM reasoning is appropriate for interpreting requirements, selecting relevant
context, identifying unknowns, classifying risk, and explaining tradeoffs. It is
not a substitute for deterministic enforcement of safety-critical operations.

## Failure Philosophy

Agents fail closed. If required context is missing, repository state is
ambiguous, a branch or worktree already exists, or a requested operation would
touch protected state, the agent reports the conflict and stops.

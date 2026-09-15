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

4. STOP

Implementation is outside the current MVP.
```

No implementation work may start before:

- repository inspection is complete,
- a change plan exists,
- an isolated task workspace exists.

## Global Rules

Agents MUST:

- inspect repository guidance before modification,
- discover existing project conventions,
- identify relevant source files,
- identify relevant tests,
- understand current behavior before planning changes,
- minimize unrelated modifications,
- create isolated Git branches and worktrees,
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
- implement code during the current MVP workflow.

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

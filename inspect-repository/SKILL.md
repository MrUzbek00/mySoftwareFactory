---
name: inspect-repository
description: Inspect only task-relevant repository context so an agent can plan a safe engineering change without modifying code.
---

# Inspect Repository

## Purpose

Understand enough of an unfamiliar repository to plan a safe engineering change.
This skill does not attempt to understand the entire repository and must not
modify code.

## When to Use

Use this skill at the start of a task, before planning or implementation, when
the agent needs to discover how the requested behavior maps to the repository.

Read `references/repository-analysis.md` when deciding which project files are
most likely to contain high-value context for the detected stack.

## Preconditions

- A task request is available.
- The repository path is known.
- The agent has read access to the repository.

## Required Inputs

- `task_id`
- `task_title`
- `task_description`
- `repository_path`
- `optional_target_paths`
- `optional_constraints`

## Workflow

1. Record the current branch, HEAD commit, and working tree status.
2. Read root guidance files such as `README`, `AGENTS.md`, and contribution
   documents when present.
3. Identify manifests, dependency files, Docker files, CI configuration, and
   application entrypoints.
4. Map the major directories at a shallow depth before reading source files.
5. Follow task terms, target paths, route names, symbols, and test names to
   locate relevant code.
6. Inspect nearby tests and fixtures before proposing how behavior should
   change.
7. Inspect recent Git history for relevant files only when it clarifies current
   behavior or ownership.
8. Stop expanding context when the likely affected components, tests, contracts,
   risks, and unknowns are clear enough for planning.

Inspect, when relevant:

- README files
- `AGENTS.md`
- contributing documentation
- package manifests
- Python manifests
- dependency files
- Docker configuration
- CI configuration
- application entrypoints
- major directories
- configuration
- database models
- API routes
- service or business logic
- relevant tests
- recent relevant Git history
- current branch
- working tree status
- existing architectural conventions

## Rules

- Prioritize relevance over completeness.
- Do not recursively load the entire repository into model context.
- Do not claim to understand code that has not been inspected.
- Separate known facts from assumptions and unknowns.
- Do not modify files during inspection.
- Treat secrets and credentials as sensitive; report their presence without
  exposing values.

## Required Reasoning

Determine:

- What stack is this?
- How is the project structured?
- Where does the requested behavior live?
- What modules are likely affected?
- What tests currently cover it?
- What architecture patterns already exist?
- What public contracts might be affected?
- What information is still unknown?

## Output Contract

Return a structured repository context shaped like:

```json
{
  "task_id": "TASK-001",
  "repository": {
    "name": "example-project",
    "path": "/workspace/example-project",
    "current_branch": "main",
    "head_commit": "abc123"
  },
  "stack": {
    "languages": [],
    "frameworks": [],
    "database": [],
    "tooling": []
  },
  "architecture": {
    "summary": "",
    "patterns": []
  },
  "relevant_files": [],
  "relevant_tests": [],
  "entrypoints": [],
  "public_contracts": [],
  "risks": [],
  "unknowns": [],
  "recommended_next_context": []
}
```

Validate persisted outputs against
`schemas/repository-context.schema.json`.

## Failure Conditions

- The repository path does not exist.
- The repository cannot be read.
- Required task information is missing.
- The repository state is too conflicted to inspect safely.

## Escalation Conditions

Escalate when protected or secret-bearing files appear necessary, the task
description is ambiguous enough to change the likely implementation path, or
the repository cannot be inspected with available permissions.

## Completion Criteria

- The output preserves the task ID.
- Relevant files and tests are identified.
- Current behavior and architecture patterns are described.
- Unknowns and risks are explicit.
- The next step can be `plan-change` without loading unrelated modules.

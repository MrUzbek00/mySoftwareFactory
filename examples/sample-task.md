# Sample Task

## Task

`TASK-123`

Add an optional description field to API tokens.

Requirements:

- maximum 200 characters
- nullable/optional
- exposed through the API
- existing clients must remain compatible
- database migration required
- tests required

## Flow

```text
inspect-repository
  |
  v
repository context
  |
  v
plan-change
  |
  v
change plan
  |
  v
isolate-task
  |
  v
workspace result
```

## Repository Context Example

```json
{
  "task_id": "TASK-123",
  "repository": {
    "name": "token-service",
    "path": "/workspace/token-service",
    "current_branch": "main",
    "head_commit": "abc123"
  },
  "stack": {
    "languages": ["Python"],
    "frameworks": ["Django REST Framework"],
    "database": ["PostgreSQL"],
    "tooling": ["pytest", "ruff"]
  },
  "architecture": {
    "summary": "API token behavior is implemented in a Django app with model, serializer, viewset, and API tests.",
    "patterns": ["model-backed serializers", "forward-only migrations", "API regression tests"]
  },
  "relevant_files": [
    "tokens/models.py",
    "tokens/serializers.py",
    "tokens/views.py"
  ],
  "relevant_tests": [
    "tests/tokens/test_api_tokens.py",
    "tests/tokens/test_serializers.py"
  ],
  "entrypoints": ["config/urls.py"],
  "public_contracts": ["API token create and detail responses"],
  "risks": ["Database schema changes require migration review."],
  "unknowns": ["Exact serializer validation style must be confirmed."],
  "recommended_next_context": ["Inspect ApiTokenSerializer tests before implementation."]
}
```

## Change Plan Example

```json
{
  "task_id": "TASK-123",
  "goal": "Add an optional API token description while preserving existing clients.",
  "current_behavior": "API tokens do not expose or store a description field.",
  "desired_behavior": "Clients may omit description or provide a nullable value up to 200 characters.",
  "affected_components": ["ApiToken model", "ApiToken serializer", "API token tests"],
  "affected_files": [
    "tokens/models.py",
    "tokens/serializers.py",
    "tests/tokens/test_api_tokens.py"
  ],
  "public_contract_changes": ["API responses include description."],
  "database_changes": ["Add nullable description column with max length 200."],
  "configuration_changes": [],
  "implementation_steps": [
    "Add nullable description field to ApiToken.",
    "Generate a forward-only migration.",
    "Expose description through ApiTokenSerializer.",
    "Preserve create behavior when description is omitted."
  ],
  "test_plan": [
    "Serializer accepts omitted description.",
    "Serializer accepts null description.",
    "Serializer rejects descriptions longer than 200 characters.",
    "Existing create request without description remains valid."
  ],
  "risks": ["Migration must not require backfilling existing tokens."],
  "dependencies": [],
  "unknowns": [],
  "risk_level": "MEDIUM",
  "requires_human_approval": false,
  "approval_reason": null,
  "ready_for_isolation": true
}
```

## Workspace Result Example

```json
{
  "status": "created",
  "task_id": "TASK-123",
  "branch": "feature/TASK-123-api-token-description",
  "worktree_path": "/workspace/worktrees/TASK-123-api-token-description",
  "base_branch": "origin/main",
  "base_commit": "abc123",
  "head_commit": "abc123",
  "created_at": "2026-09-15T00:00:00Z"
}
```

The feature itself is not implemented in this repository.

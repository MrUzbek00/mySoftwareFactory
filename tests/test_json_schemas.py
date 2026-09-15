import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "schemas"


def load_schema(name: str) -> dict:
    with (SCHEMA_ROOT / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def test_repository_context_schema_accepts_example_payload() -> None:
    schema = load_schema("repository-context.schema.json")
    Draft202012Validator.check_schema(schema)
    payload = {
        "task_id": "TASK-001",
        "repository": {
            "name": "example-project",
            "path": "/workspace/example-project",
            "current_branch": "main",
            "head_commit": "abc123",
        },
        "stack": {
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
            "database": [],
            "tooling": ["pytest"],
        },
        "architecture": {
            "summary": "HTTP API with service modules.",
            "patterns": ["router-service split"],
        },
        "relevant_files": ["app/routes.py"],
        "relevant_tests": ["tests/test_routes.py"],
        "entrypoints": ["app/main.py"],
        "public_contracts": ["GET /health"],
        "risks": ["Public response shape may change."],
        "unknowns": ["Deployment target is unknown."],
        "recommended_next_context": ["Inspect route tests."],
    }

    Draft202012Validator(schema).validate(payload)


def test_change_plan_schema_accepts_example_payload() -> None:
    schema = load_schema("change-plan.schema.json")
    Draft202012Validator.check_schema(schema)
    payload = {
        "task_id": "TASK-001",
        "goal": "Add an optional field.",
        "current_behavior": "The field is not stored.",
        "desired_behavior": "The field is optional and exposed through the API.",
        "affected_components": ["serializer"],
        "affected_files": ["app/serializers.py"],
        "public_contract_changes": ["Response includes a nullable field."],
        "database_changes": ["Add nullable column."],
        "configuration_changes": [],
        "implementation_steps": ["Add model field.", "Add serializer field."],
        "test_plan": ["Validate omitted value.", "Validate max length."],
        "risks": ["Migration required."],
        "dependencies": [],
        "unknowns": [],
        "risk_level": "MEDIUM",
        "requires_human_approval": False,
        "approval_reason": None,
        "ready_for_isolation": True,
    }

    Draft202012Validator(schema).validate(payload)


def test_workspace_result_schema_accepts_example_payload() -> None:
    schema = load_schema("workspace-result.schema.json")
    Draft202012Validator.check_schema(schema)
    payload = {
        "status": "created",
        "task_id": "TASK-001",
        "branch": "feature/TASK-001-add-field",
        "worktree_path": "/workspace/worktrees/TASK-001-add-field",
        "base_branch": "origin/main",
        "base_commit": "abc123",
        "head_commit": "abc123",
        "created_at": "2026-09-15T00:00:00Z",
    }

    Draft202012Validator(schema).validate(payload)


def test_change_plan_schema_rejects_unknown_risk_level() -> None:
    schema = load_schema("change-plan.schema.json")
    payload = {
        "task_id": "TASK-001",
        "goal": "",
        "current_behavior": "",
        "desired_behavior": "",
        "affected_components": [],
        "affected_files": [],
        "public_contract_changes": [],
        "database_changes": [],
        "configuration_changes": [],
        "implementation_steps": [],
        "test_plan": [],
        "risks": [],
        "dependencies": [],
        "unknowns": [],
        "risk_level": "UNKNOWN",
        "requires_human_approval": False,
        "approval_reason": None,
        "ready_for_isolation": True,
    }

    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    assert errors

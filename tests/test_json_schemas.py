import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "my-software-factory" / "schemas"


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


def test_requirements_index_schema_accepts_example_payload(spec_artifacts: dict) -> None:
    schema = load_schema("requirements-index.schema.json")
    Draft202012Validator.check_schema(schema)
    payload = spec_artifacts["requirements"]
    payload["unknowns"] = [
        {
            "unknown_id": "UNKNOWN-014",
            "related_requirements": ["REQ-AUTH-001"],
            "question": "Can an approved contract still be edited?",
            "impact": "Affects authorization, audit logs and contract versioning.",
            "status": "NEEDS_USER_DECISION",
            "resolved_by": None,
        }
    ]
    payload["conflicts"] = [
        {
            "conflict_id": "CONFLICT-003",
            "requirement_a": "REQ-AUTH-001",
            "requirement_b": "REQ-APP-021",
            "reason": "Two sections assign the same transition to different roles.",
            "decision_required": "Which role may close a record?",
            "status": "OPEN",
            "resolved_by": None,
        }
    ]

    Draft202012Validator(schema).validate(payload)


def test_requirements_index_schema_rejects_unknown_state(spec_artifacts: dict) -> None:
    schema = load_schema("requirements-index.schema.json")
    payload = spec_artifacts["requirements"]
    payload["requirements"][0]["state"] = "PROBABLY_FINE"

    assert list(Draft202012Validator(schema).iter_errors(payload))


def test_project_context_schema_accepts_example_payload(spec_artifacts: dict) -> None:
    schema = load_schema("project-context.schema.json")
    Draft202012Validator.check_schema(schema)
    payload = spec_artifacts["project"]
    payload["decisions"] = [
        {
            "decision_id": "DEC-001",
            "question": "Is Laravel mandatory?",
            "decision": "Yes. Laravel must be used.",
            "reason": "Customer technical specification.",
            "source": "User confirmation during project intake.",
            "date": "2026-09-15",
            "related_requirements": ["REQ-AUTH-001"],
            "supersedes": None,
        }
    ]
    payload["amendments"] = [
        {
            "amendment_id": "AMD-001",
            "received": "2026-09-20",
            "source": "Customer email",
            "summary": "Section 4.8 now allows reassignment.",
            "affected_requirements": ["REQ-APP-021"],
            "affected_decisions": ["DEC-001"],
            "affected_tasks": ["TASK-DEMO-011"],
            "completed_work_impact": [],
            "status": "OPEN",
        }
    ]

    Draft202012Validator(schema).validate(payload)


def test_project_context_schema_rejects_unknown_status(spec_artifacts: dict) -> None:
    schema = load_schema("project-context.schema.json")
    payload = spec_artifacts["project"]
    payload["status"] = "mostly-confirmed"

    assert list(Draft202012Validator(schema).iter_errors(payload))


def test_project_backlog_schema_accepts_example_payload(spec_artifacts: dict) -> None:
    schema = load_schema("project-backlog.schema.json")
    Draft202012Validator.check_schema(schema)

    Draft202012Validator(schema).validate(spec_artifacts["backlog"])


def test_project_backlog_schema_rejects_unknown_readiness(spec_artifacts: dict) -> None:
    schema = load_schema("project-backlog.schema.json")
    payload = spec_artifacts["backlog"]
    payload["tasks"][0]["readiness"] = "ALMOST_READY"

    assert list(Draft202012Validator(schema).iter_errors(payload))


def test_project_backlog_schema_rejects_a_task_id_the_workflow_cannot_use(
    spec_artifacts: dict,
) -> None:
    schema = load_schema("project-backlog.schema.json")
    payload = spec_artifacts["backlog"]
    payload["tasks"][0]["task_id"] = "DEMO-010"

    assert list(Draft202012Validator(schema).iter_errors(payload))


def test_task_handoff_schema_rejects_a_task_that_is_not_ready() -> None:
    schema = load_schema("task-handoff.schema.json")
    Draft202012Validator.check_schema(schema)
    payload = {
        "task_id": "TASK-DEMO-010",
        "backlog_ref": "DEMO-010",
        "project_id": "DEMO",
        "task_title": "Implement login and logout",
        "task_description": "Provide username and password authentication.",
        "task_type": "feature",
        "task_slug": "login-logout",
        "repository": {
            "url": "https://github.com/owner/demo",
            "path": "/workspace/demo",
            "base_branch": "main",
            "project_type": "existing",
        },
        "acceptance_criteria": ["Valid credentials start an authenticated session."],
        "constraints": [],
        "dependencies": [],
        "out_of_scope": [],
        "test_requirements": [],
        "source_requirements": [
            {
                "requirement_id": "REQ-AUTH-001",
                "statement": "The application must provide username/password authentication.",
                "state": "CONFIRMED",
                "sources": [
                    {"source_id": "SPEC-1", "section": "9.1", "subsection": None, "page": "4"}
                ],
            }
        ],
        "source_specifications": [
            {
                "source_id": "SPEC-1",
                "title": "Demo Technical Requirements",
                "location": "docs/demo-requirements.docx",
            }
        ],
        "optional_target_paths": [],
        "risk_level": "HIGH",
        "readiness": "BLOCKED",
        "open_dependencies": [],
        "generated_at": "2026-09-15T00:00:00Z",
    }

    assert list(Draft202012Validator(schema).iter_errors(payload))

    payload["readiness"] = "READY"
    Draft202012Validator(schema).validate(payload)


def validation_report() -> dict:
    return {
        "status": "pass",
        "task_id": "TASK-123",
        "branch": "feature/TASK-123-password-reset",
        "worktree_path": "/workspace/worktrees/TASK-123-password-reset",
        "base_branch": "origin/main",
        "head_commit": "abc123",
        "checks": [
            {
                "name": "tests",
                "command": "pytest -q",
                "status": "pass",
                "exit_code": 0,
                "duration_seconds": 1.0,
                "output_tail": "",
            }
        ],
        "diff_summary": {"files_changed": 1, "insertions": 1, "deletions": 0},
        "ready_for_pull_request": True,
        "generated_at": "2026-09-15T00:00:00Z",
    }


def test_validation_report_without_code_quality_remains_valid() -> None:
    """Reports produced before the quality review existed must still validate."""
    schema = load_schema("validation-report.schema.json")
    Draft202012Validator.check_schema(schema)

    Draft202012Validator(schema).validate(validation_report())


def test_validation_report_accepts_a_code_quality_review() -> None:
    schema = load_schema("validation-report.schema.json")
    payload = validation_report()
    payload["status"] = "fail"
    payload["ready_for_pull_request"] = False
    payload["code_quality"] = {
        "status": "findings",
        "reviewed_files": ["app/Services/ContractService.php"],
        "skipped_files": [],
        "findings": [
            {
                "criterion": "return-types",
                "severity": "BLOCKING",
                "file": "app/Services/ContractService.php",
                "symbol": "ContractService::createContract",
                "detail": "Returns Contract or false with no declared return type.",
                "suggestion": "Declare : Contract and throw on validation failure.",
            }
        ],
        "counts": {"BLOCKING": 1, "ADVISORY": 0},
    }

    Draft202012Validator(schema).validate(payload)


def test_validation_report_rejects_an_unknown_quality_criterion() -> None:
    schema = load_schema("validation-report.schema.json")
    payload = validation_report()
    payload["code_quality"] = {
        "status": "findings",
        "reviewed_files": [],
        "findings": [
            {
                "criterion": "vibes",
                "severity": "BLOCKING",
                "file": "app.php",
                "detail": "Feels wrong.",
            }
        ],
        "counts": {"BLOCKING": 1, "ADVISORY": 0},
    }

    assert list(Draft202012Validator(schema).iter_errors(payload))


def test_validation_report_rejects_an_invented_severity() -> None:
    schema = load_schema("validation-report.schema.json")
    payload = validation_report()
    payload["code_quality"] = {
        "status": "findings",
        "reviewed_files": [],
        "findings": [
            {
                "criterion": "naming",
                "severity": "NITPICK",
                "file": "app.php",
                "detail": "Name could be better.",
            }
        ],
        "counts": {"BLOCKING": 0, "ADVISORY": 1},
    }

    assert list(Draft202012Validator(schema).iter_errors(payload))


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

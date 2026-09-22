"""Shared schema-valid artifacts for the intake scripts and the pipeline map.

These fixtures build a minimal but schema-valid project: one confirmed project
context, two requirements with source coordinates, and two READY tasks where the
second depends on the first. Individual tests mutate one field to prove one rule.

`factory_run` assembles the same artifacts into a `.factory` directory on disk,
which is what factory-map reads to derive run state.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


def _project_context() -> dict[str, Any]:
    return {
        "project_id": "DEMO",
        "project_name": "Demo Project",
        "status": "confirmed",
        "confirmed_at": "2026-09-15T00:00:00Z",
        "source_specifications": [
            {
                "source_id": "SPEC-1",
                "title": "Demo Technical Requirements",
                "location": "docs/demo-requirements.docx",
                "format": "docx",
                "version": "1.0",
            }
        ],
        "repository": {
            "url": "https://github.com/owner/demo",
            "path": "/workspace/demo",
            "exists": True,
            "project_type": "existing",
            "base_branch": "main",
            "may_create_branches": True,
            "may_open_pull_requests": True,
            "create_issues": False,
        },
        "stack": {"mandatory": ["Laravel 11"], "preferred": [], "prohibited": []},
        "architecture_constraints": [],
        "database": ["MySQL 8"],
        "frontend": [],
        "authentication": {"mechanism": "session", "identity_provider": None, "notes": []},
        "roles": [],
        "integrations": [],
        "environment": [],
        "deployment": {"targets": [], "environments": [], "ci_cd": [], "notes": []},
        "testing": {"levels": ["unit"], "minimum_before_pull_request": [], "quality_gates": []},
        "security": {
            "constraints": [],
            "compliance": [],
            "audit_logging": [],
            "data_retention": [],
        },
        "business_rules": [],
        "delivery": {
            "scope": "mvp",
            "priorities": [],
            "milestones": [],
            "incremental": True,
            "definition_of_done": [],
        },
        "decisions": [],
        "open_questions": [],
        "blocked_requirements": [],
        "amendments": [],
        "generated_at": "2026-09-15T00:00:00Z",
    }


def _requirement(requirement_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "requirement_id": requirement_id,
        "title": "Requirement",
        "statement": "The application must do the thing the document says.",
        "category": "functional",
        "state": "CONFIRMED",
        "priority": "MUST",
        "sources": [
            {
                "source_id": "SPEC-1",
                "section": "4.2",
                "subsection": None,
                "page": "10-11",
                "quote": None,
            }
        ],
        "related_requirements": [],
        "open_questions": [],
        "conflicts": [],
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _requirements_index() -> dict[str, Any]:
    return {
        "project_id": "DEMO",
        "sources": [
            {
                "source_id": "SPEC-1",
                "title": "Demo Technical Requirements",
                "location": "docs/demo-requirements.docx",
                "format": "docx",
                "version": "1.0",
                "received": "2026-09-15",
            }
        ],
        "requirements": [_requirement("REQ-AUTH-001"), _requirement("REQ-APP-021")],
        "unknowns": [],
        "conflicts": [],
        "generated_at": "2026-09-15T00:00:00Z",
    }


def _task(task_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "task_id": task_id,
        "backlog_ref": task_id.replace("TASK-", ""),
        "feature_id": "FEATURE-02.1",
        "title": "Do the thing",
        "description": "Implement the behavior the requirement describes.",
        "business_objective": "The customer asked for it.",
        "actor": "Manager",
        "functional_requirements": [],
        "acceptance_criteria": ["The behavior happens when it should."],
        "source_requirements": ["REQ-AUTH-001"],
        "dependencies": [],
        "constraints": [],
        "out_of_scope": [],
        "test_requirements": [],
        "risk_level": None,
        "open_questions": [],
        "blocked_by": [],
        "readiness": "READY",
        "task_type": "feature",
        "slug": "do-the-thing",
    }
    payload.update(overrides)
    return payload


def _backlog() -> dict[str, Any]:
    return {
        "project_id": "DEMO",
        "status": "approved",
        "approved_at": "2026-09-15T00:00:00Z",
        "epics": [
            {
                "epic_id": "EPIC-02",
                "title": "Authentication",
                "objective": "Users authenticate.",
                "source_requirements": ["REQ-AUTH-001"],
                "features": [
                    {
                        "feature_id": "FEATURE-02.1",
                        "title": "Authentication",
                        "source_requirements": ["REQ-AUTH-001"],
                    }
                ],
            }
        ],
        "tasks": [
            _task("TASK-DEMO-010"),
            _task(
                "TASK-DEMO-011",
                source_requirements=["REQ-APP-021"],
                dependencies=["TASK-DEMO-010"],
                slug="second-thing",
            ),
        ],
        "generated_at": "2026-09-15T00:00:00Z",
    }


@pytest.fixture
def spec_artifacts() -> dict[str, dict[str, Any]]:
    """A consistent project context, requirements index, and approved backlog."""
    return {
        "project": _project_context(),
        "requirements": _requirements_index(),
        "backlog": _backlog(),
    }


@pytest.fixture
def make_requirement() -> Callable[..., dict[str, Any]]:
    return _requirement


@pytest.fixture
def make_task() -> Callable[..., dict[str, Any]]:
    return _task


@pytest.fixture
def unresolved_unknown() -> dict[str, Any]:
    return {
        "unknown_id": "UNKNOWN-014",
        "related_requirements": ["REQ-AUTH-001"],
        "question": "Can an approved record still be edited?",
        "impact": "Affects authorization, audit logs and versioning.",
        "status": "NEEDS_USER_DECISION",
        "resolved_by": None,
    }


def _repository_context(task_id: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "repository": {
            "name": "demo",
            "path": "/workspace/demo",
            "current_branch": "main",
            "head_commit": "abc123",
        },
        "stack": {"languages": ["Python"], "frameworks": [], "database": [], "tooling": []},
        "architecture": {"summary": "One service.", "patterns": []},
        "relevant_files": ["app/main.py"],
        "relevant_tests": [],
        "entrypoints": [],
        "public_contracts": [],
        "risks": [],
        "unknowns": [],
        "recommended_next_context": [],
    }


def _change_plan(task_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "task_id": task_id,
        "goal": "Do the thing.",
        "current_behavior": "It does not happen.",
        "desired_behavior": "It happens.",
        "affected_components": [],
        "affected_files": [],
        "public_contract_changes": [],
        "database_changes": [],
        "configuration_changes": [],
        "implementation_steps": ["Write it."],
        "test_plan": ["Test it."],
        "risks": [],
        "dependencies": [],
        "unknowns": [],
        "risk_level": "LOW",
        "requires_human_approval": False,
        "approval_reason": None,
        "ready_for_isolation": True,
    }
    payload.update(overrides)
    return payload


def _workspace_result(task_id: str) -> dict[str, Any]:
    return {
        "status": "created",
        "task_id": task_id,
        "branch": f"feature/{task_id}-demo",
        "worktree_path": "/workspace/worktrees/demo",
        "base_branch": "origin/main",
        "base_commit": "abc123",
        "head_commit": "abc123",
        "created_at": "2026-09-15T00:00:00Z",
    }


def _implementation_result(task_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "status": "implemented",
        "task_id": task_id,
        "branch": f"feature/{task_id}-demo",
        "worktree_path": "/workspace/worktrees/demo",
        "steps_completed": ["Write it."],
        "steps_skipped": [],
        "files_added": [],
        "files_modified": ["app/main.py"],
        "files_deleted": [],
        "tests_added": [],
        "commits": [{"sha": "abc1240", "message": "feat: do the thing"}],
        "plan_deviations": [],
        "unknowns": [],
        "blocked_reason": None,
        "ready_for_validation": True,
    }
    payload.update(overrides)
    return payload


def _validation_report(task_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "status": "pass",
        "task_id": task_id,
        "branch": f"feature/{task_id}-demo",
        "worktree_path": "/workspace/worktrees/demo",
        "base_branch": "origin/main",
        "head_commit": "abc124",
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
    payload.update(overrides)
    return payload


def _security_review(task_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "status": "clean",
        "task_id": task_id,
        "branch": f"feature/{task_id}-demo",
        "base_commit": "abc123",
        "head_commit": "abc124",
        "findings": [],
        "dependency_changes": [],
        "counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
        "requires_human_review": False,
        "generated_at": "2026-09-15T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def _task_handoff(task_id: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "backlog_ref": task_id.replace("TASK-", ""),
        "project_id": "DEMO",
        "task_title": "Do the thing",
        "task_description": "Implement the behavior the requirement describes.",
        "task_type": "feature",
        "task_slug": "do-the-thing",
        "repository": {
            "url": "https://github.com/owner/demo",
            "path": "/workspace/demo",
            "base_branch": "main",
            "project_type": "existing",
        },
        "acceptance_criteria": ["The behavior happens when it should."],
        "constraints": [],
        "dependencies": [],
        "out_of_scope": [],
        "test_requirements": [],
        "source_requirements": [
            {
                "requirement_id": "REQ-AUTH-001",
                "statement": "The application must provide authentication.",
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
        "risk_level": "LOW",
        "readiness": "READY",
        "open_dependencies": [],
        "generated_at": "2026-09-15T00:00:00Z",
    }


def _factory_artifacts(task_id: str) -> dict[str, dict[str, Any]]:
    """Every per-task artifact the map looks for, each schema-valid."""
    return {
        "task-handoff.json": _task_handoff(task_id),
        "context.json": _repository_context(task_id),
        "plan.json": _change_plan(task_id),
        "workspace.json": _workspace_result(task_id),
        "implementation.json": _implementation_result(task_id),
        "validation.json": _validation_report(task_id),
        "security.json": _security_review(task_id),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture
def factory_run(tmp_path: Path) -> Callable[..., Path]:
    """Build a .factory directory on disk and return its path.

    Callers pass `stages` to choose which per-task artifacts exist, and
    `overrides` to replace one artifact with a mutated copy, so a test can
    change one field and assert one consequence.
    """

    def build(
        task_id: str = "TASK-DEMO-010",
        stages: tuple[str, ...] | None = None,
        overrides: dict[str, Any] | None = None,
        intake: bool = True,
    ) -> Path:
        factory = tmp_path / ".factory"
        if intake:
            _write_json(factory / "project.json", _project_context())
            _write_json(factory / "requirements.json", _requirements_index())
            _write_json(factory / "backlog.json", _backlog())

        task_dir = factory / "tasks" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        artifacts = _factory_artifacts(task_id)
        chosen = artifacts if stages is None else {
            name: payload for name, payload in artifacts.items() if name in stages
        }
        for name, payload in chosen.items():
            _write_json(task_dir / name, payload)

        for name, payload in (overrides or {}).items():
            if payload is None:
                (task_dir / name).unlink(missing_ok=True)
            elif isinstance(payload, str):
                (task_dir / name).write_text(payload, encoding="utf-8")
            else:
                _write_json(task_dir / name, payload)

        return factory

    return build


@pytest.fixture
def make_change_plan() -> Callable[..., dict[str, Any]]:
    return _change_plan


@pytest.fixture
def make_validation_report() -> Callable[..., dict[str, Any]]:
    return _validation_report


@pytest.fixture
def make_security_review() -> Callable[..., dict[str, Any]]:
    return _security_review

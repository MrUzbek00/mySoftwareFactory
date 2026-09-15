"""Shared specification-intake artifacts for the intake script tests.

These fixtures build a minimal but schema-valid project: one confirmed project
context, two requirements with source coordinates, and two READY tasks where the
second depends on the first. Individual tests mutate one field to prove one rule.
"""

from collections.abc import Callable
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

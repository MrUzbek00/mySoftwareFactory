"""Check a generated backlog against its requirements index and project context.

This script is the consistency step for specification intake. It validates each
artifact against its schema, resolves every identifier the backlog references,
proves the dependency graph is acyclic, and refuses to call a task READY unless
the readiness rules actually hold. It reads artifacts only; it never writes to a
repository and never modifies the artifacts it checks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
IMPLEMENTABLE_STATES = ("CONFIRMED", "CLARIFIED", "OPTIONAL")
OVERSIZED_REQUIREMENT_COUNT = 6

SCHEMAS = {
    "project_context": "project-context.schema.json",
    "requirements": "requirements-index.schema.json",
    "backlog": "project-backlog.schema.json",
}


class ScriptError(Exception):
    """Structured error that can be returned as JSON."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def load_json(path: Path, label: str) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise ScriptError("MISSING_ARTIFACT", f"{label} file does not exist: {resolved}")
    try:
        with resolved.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ScriptError("INVALID_ARTIFACT_JSON", f"{resolved} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ScriptError("INVALID_ARTIFACT_JSON", f"{resolved} must contain a JSON object.")
    return data


def validate_against_schema(payload: dict[str, Any], schema_path: Path) -> list[str]:
    """Validate with jsonschema when available, else fall back to a required-key check."""
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"schema unreadable: {exc}"]

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        required = schema.get("required", [])
        return [f"missing required key: {key}" for key in required if key not in payload]

    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.path))
    return [f"{list(e.path) or '<root>'}: {e.message}" for e in errors[:10]]


def duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return sorted(repeated)


def find_cycle(edges: dict[str, list[str]]) -> list[str] | None:
    """Return one dependency cycle as an ordered path, or None when acyclic."""
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def walk(node: str) -> list[str] | None:
        if node in visited:
            return None
        if node in visiting:
            start = stack.index(node)
            return [*stack[start:], node]
        visiting.add(node)
        stack.append(node)
        for neighbour in edges.get(node, []):
            if neighbour not in edges:
                continue
            cycle = walk(neighbour)
            if cycle is not None:
                return cycle
        stack.pop()
        visiting.discard(node)
        visited.add(node)
        return None

    for node in sorted(edges):
        cycle = walk(node)
        if cycle is not None:
            return cycle
    return None


def check_identifiers(
    context: dict[str, Any],
    requirements: dict[str, Any],
    backlog: dict[str, Any],
) -> list[str]:
    problems: list[str] = []

    project_ids = {
        "project context": context.get("project_id"),
        "requirements index": requirements.get("project_id"),
        "backlog": backlog.get("project_id"),
    }
    distinct = {value for value in project_ids.values() if value is not None}
    if len(distinct) > 1:
        detail = ", ".join(f"{name}={value}" for name, value in sorted(project_ids.items()))
        problems.append(f"artifacts disagree on project_id: {detail}")

    project_id = backlog.get("project_id")
    if isinstance(project_id, str) and not PROJECT_ID_PATTERN.fullmatch(project_id):
        problems.append(f"project_id {project_id} is not an uppercase key of 2-10 characters")

    id_groups = (
        ("requirement_id", requirements.get("requirements", [])),
        ("unknown_id", requirements.get("unknowns", [])),
        ("conflict_id", requirements.get("conflicts", [])),
        ("task_id", backlog.get("tasks", [])),
        ("epic_id", backlog.get("epics", [])),
    )
    for key, items in id_groups:
        values = [item.get(key) for item in items]
        repeated = duplicates([value for value in values if isinstance(value, str)])
        problems.extend(f"duplicate {key}: {value}" for value in repeated)

    feature_ids = [
        feature.get("feature_id")
        for epic in backlog.get("epics", [])
        for feature in epic.get("features", [])
    ]
    problems.extend(
        f"duplicate feature_id: {value}"
        for value in duplicates([value for value in feature_ids if isinstance(value, str)])
    )

    if isinstance(project_id, str):
        prefix = f"TASK-{project_id}-"
        problems.extend(
            f"{task.get('task_id')} does not start with {prefix}"
            for task in backlog.get("tasks", [])
            if isinstance(task.get("task_id"), str) and not task["task_id"].startswith(prefix)
        )

    return problems


def check_references(requirements: dict[str, Any], backlog: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    requirement_ids = {
        item["requirement_id"]
        for item in requirements.get("requirements", [])
        if isinstance(item.get("requirement_id"), str)
    }
    unknown_ids = {
        item["unknown_id"]
        for item in requirements.get("unknowns", [])
        if isinstance(item.get("unknown_id"), str)
    }
    conflict_ids = {
        item["conflict_id"]
        for item in requirements.get("conflicts", [])
        if isinstance(item.get("conflict_id"), str)
    }
    task_ids = {
        task["task_id"] for task in backlog.get("tasks", []) if isinstance(task.get("task_id"), str)
    }
    feature_ids = {
        feature.get("feature_id")
        for epic in backlog.get("epics", [])
        for feature in epic.get("features", [])
    }
    known_blockers = requirement_ids | unknown_ids | conflict_ids | task_ids

    for item in requirements.get("requirements", []):
        origin = item.get("requirement_id", "<unknown requirement>")
        problems.extend(
            f"{origin} references unknown requirement {value}"
            for value in item.get("related_requirements", [])
            if value not in requirement_ids
        )
        problems.extend(
            f"{origin} references unknown open question {value}"
            for value in item.get("open_questions", [])
            if value not in unknown_ids
        )
        problems.extend(
            f"{origin} references unknown conflict {value}"
            for value in item.get("conflicts", [])
            if value not in conflict_ids
        )

    for item in requirements.get("unknowns", []):
        origin = item.get("unknown_id", "<unknown question>")
        problems.extend(
            f"{origin} references unknown requirement {value}"
            for value in item.get("related_requirements", [])
            if value not in requirement_ids
        )

    for item in requirements.get("conflicts", []):
        origin = item.get("conflict_id", "<unknown conflict>")
        problems.extend(
            f"{origin} references unknown requirement {value}"
            for value in (item.get("requirement_a"), item.get("requirement_b"))
            if value is not None and value not in requirement_ids
        )

    for task in backlog.get("tasks", []):
        origin = task.get("task_id", "<unknown task>")
        if task.get("feature_id") not in feature_ids:
            problems.append(f"{origin} belongs to unknown feature {task.get('feature_id')}")
        if not task.get("source_requirements"):
            problems.append(f"{origin} has no source requirement and cannot be traced")
        problems.extend(
            f"{origin} references unknown requirement {value}"
            for value in task.get("source_requirements", [])
            if value not in requirement_ids
        )
        problems.extend(
            f"{origin} depends on unknown task {value}"
            for value in task.get("dependencies", [])
            if value not in task_ids
        )
        if origin in task.get("dependencies", []):
            problems.append(f"{origin} depends on itself")
        problems.extend(
            f"{origin} references unknown open question {value}"
            for value in task.get("open_questions", [])
            if value not in unknown_ids and value not in conflict_ids
        )
        problems.extend(
            f"{origin} is blocked by unknown identifier {value}"
            for value in task.get("blocked_by", [])
            if value not in known_blockers
        )

    return problems


def check_readiness(
    context: dict[str, Any],
    requirements: dict[str, Any],
    backlog: dict[str, Any],
) -> list[str]:
    problems: list[str] = []

    states = {
        item["requirement_id"]: item.get("state")
        for item in requirements.get("requirements", [])
        if isinstance(item.get("requirement_id"), str)
    }
    unresolved = {
        item["unknown_id"]
        for item in requirements.get("unknowns", [])
        if isinstance(item.get("unknown_id"), str) and item.get("status") != "ANSWERED"
    }
    unresolved |= {
        item["conflict_id"]
        for item in requirements.get("conflicts", [])
        if isinstance(item.get("conflict_id"), str) and item.get("status") != "RESOLVED"
    }

    repository = context.get("repository") or {}
    repository_known = bool(repository.get("url") or repository.get("path"))
    context_confirmed = context.get("status") == "confirmed"

    for task in backlog.get("tasks", []):
        if task.get("readiness") != "READY":
            continue
        origin = task.get("task_id", "<unknown task>")

        if not context_confirmed:
            problems.append(f"{origin} is READY but the project context is not confirmed")
        if not repository_known:
            problems.append(f"{origin} is READY but the target repository is unknown")
        if not task.get("acceptance_criteria"):
            problems.append(f"{origin} is READY but has no acceptance criteria")
        problems.extend(
            f"{origin} is READY but open question {value} is unresolved"
            for value in task.get("open_questions", [])
            if value in unresolved
        )
        if task.get("blocked_by"):
            blockers = ", ".join(task["blocked_by"])
            problems.append(f"{origin} is READY but is blocked by {blockers}")
        for value in task.get("source_requirements", []):
            state = states.get(value)
            if state is not None and state not in IMPLEMENTABLE_STATES:
                problems.append(f"{origin} is READY but source requirement {value} is {state}")

    return problems


def build_traceability(
    requirements: dict[str, Any], backlog: dict[str, Any]
) -> list[dict[str, Any]]:
    by_id = {
        item["requirement_id"]: item
        for item in requirements.get("requirements", [])
        if isinstance(item.get("requirement_id"), str)
    }

    traceability: list[dict[str, Any]] = []
    for task in backlog.get("tasks", []):
        entries = []
        for value in task.get("source_requirements", []):
            requirement = by_id.get(value)
            entries.append(
                {
                    "requirement_id": value,
                    "state": requirement.get("state") if requirement else None,
                    "sources": requirement.get("sources", []) if requirement else [],
                }
            )
        traceability.append(
            {
                "task_id": task.get("task_id"),
                "backlog_ref": task.get("backlog_ref"),
                "readiness": task.get("readiness"),
                "requirements": entries,
            }
        )
    return traceability


def build_warnings(requirements: dict[str, Any], backlog: dict[str, Any]) -> list[str]:
    warnings: list[str] = []

    covered = {
        value for task in backlog.get("tasks", []) for value in task.get("source_requirements", [])
    }
    for item in requirements.get("requirements", []):
        requirement_id = item.get("requirement_id")
        if item.get("state") in ("CONFIRMED", "CLARIFIED") and requirement_id not in covered:
            warnings.append(f"{requirement_id} is implementable but no task covers it")

    for task in backlog.get("tasks", []):
        count = len(task.get("source_requirements", []))
        if count > OVERSIZED_REQUIREMENT_COUNT:
            warnings.append(
                f"{task.get('task_id')} covers {count} requirements and may be too large "
                "for one change"
            )
        if not task.get("acceptance_criteria"):
            warnings.append(f"{task.get('task_id')} has no acceptance criteria yet")

    return warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check a project backlog against its requirements index and project context.",
    )
    parser.add_argument("--project-context", required=True, help="Path to project.json.")
    parser.add_argument("--requirements", required=True, help="Path to requirements.json.")
    parser.add_argument("--backlog", required=True, help="Path to backlog.json.")
    parser.add_argument(
        "--schemas-dir",
        default=None,
        help="Path to the schemas directory. Schema validation is skipped when omitted.",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    context = load_json(Path(args.project_context), "Project context")
    requirements = load_json(Path(args.requirements), "Requirements index")
    backlog = load_json(Path(args.backlog), "Backlog")

    violations: list[str] = []

    if args.schemas_dir is not None:
        schemas_dir = Path(args.schemas_dir).expanduser().resolve()
        if not schemas_dir.is_dir():
            raise ScriptError("INVALID_SCHEMAS_DIR", f"Not a directory: {schemas_dir}")
        for label, payload in (
            ("project_context", context),
            ("requirements", requirements),
            ("backlog", backlog),
        ):
            violations.extend(
                f"{label}: {error}"
                for error in validate_against_schema(payload, schemas_dir / SCHEMAS[label])
            )

    violations.extend(check_identifiers(context, requirements, backlog))
    violations.extend(check_references(requirements, backlog))
    violations.extend(check_readiness(context, requirements, backlog))

    edges = {
        task["task_id"]: list(task.get("dependencies", []))
        for task in backlog.get("tasks", [])
        if isinstance(task.get("task_id"), str)
    }
    cycle = find_cycle(edges)
    if cycle is not None:
        violations.append(f"dependency cycle: {' -> '.join(cycle)}")

    readiness_counts: dict[str, int] = {}
    for task in backlog.get("tasks", []):
        state = task.get("readiness", "DRAFT")
        readiness_counts[state] = readiness_counts.get(state, 0) + 1

    return {
        "status": "consistent" if not violations else "inconsistent",
        "project_id": backlog.get("project_id"),
        "backlog_status": backlog.get("status"),
        "project_context_status": context.get("status"),
        "counts": {
            "requirements": len(requirements.get("requirements", [])),
            "unknowns": len(requirements.get("unknowns", [])),
            "conflicts": len(requirements.get("conflicts", [])),
            "epics": len(backlog.get("epics", [])),
            "tasks": len(backlog.get("tasks", [])),
            "readiness": readiness_counts,
        },
        "violations": violations,
        "warnings": build_warnings(requirements, backlog),
        "traceability": build_traceability(requirements, backlog),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = run(args)
        emit(report)
        return 0 if report["status"] == "consistent" else 1
    except ScriptError as exc:
        emit({"status": "error", "error_code": exc.error_code, "message": exc.message})
        return 1
    except Exception as exc:  # pragma: no cover - last-resort CLI guard
        emit({"status": "error", "error_code": "INTERNAL_ERROR", "message": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())

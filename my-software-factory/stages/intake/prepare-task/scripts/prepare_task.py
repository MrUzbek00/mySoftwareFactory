"""Convert one READY backlog task into the contract the engineering workflow expects.

This script is the handoff gate between specification intake and implementation.
It refuses to emit a handoff for a task that is not READY, whose project context
is unconfirmed, whose backlog is unapproved, whose requirements are unresolved,
or whose target repository is unknown. It reads artifacts only; it never writes
to the target repository and never starts implementation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

IMPLEMENTABLE_STATES = ("CONFIRMED", "CLARIFIED", "OPTIONAL")


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


def require_confirmed_context(context: dict[str, Any]) -> dict[str, Any]:
    if context.get("status") != "confirmed":
        raise ScriptError(
            "PROJECT_NOT_CONFIRMED",
            "The project context is not confirmed. Run clarify-project and get the "
            "project intake summary approved before preparing a task.",
        )
    repository = context.get("repository") or {}
    if not (repository.get("url") or repository.get("path")):
        raise ScriptError(
            "REPOSITORY_UNKNOWN",
            "The project context names no target repository. Resolve the repository "
            "during project intake before preparing a task.",
        )
    return repository


def require_approved_backlog(backlog: dict[str, Any]) -> None:
    if backlog.get("status") != "approved":
        raise ScriptError(
            "BACKLOG_NOT_APPROVED",
            "The backlog is not approved. Present the backlog and obtain approval "
            "before preparing a task.",
        )


def find_task(backlog: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in backlog.get("tasks", []):
        if task.get("task_id") == task_id or task.get("backlog_ref") == task_id:
            return task
    known = ", ".join(
        str(task.get("task_id")) for task in backlog.get("tasks", []) if task.get("task_id")
    )
    raise ScriptError("UNKNOWN_TASK", f"No task {task_id} in the backlog. Known tasks: {known}.")


def require_ready(task: dict[str, Any]) -> None:
    readiness = task.get("readiness")
    if readiness != "READY":
        detail = f"{task.get('task_id')} is {readiness}, not READY."
        if task.get("blocked_by"):
            detail += f" Blocked by: {', '.join(task['blocked_by'])}."
        if task.get("open_questions"):
            detail += f" Open questions: {', '.join(task['open_questions'])}."
        raise ScriptError("TASK_NOT_READY", detail)

    if not task.get("acceptance_criteria"):
        raise ScriptError(
            "TASK_NOT_READY",
            f"{task.get('task_id')} is marked READY but has no acceptance criteria.",
        )
    if task.get("blocked_by"):
        raise ScriptError(
            "TASK_NOT_READY",
            f"{task.get('task_id')} is marked READY but is blocked by "
            f"{', '.join(task['blocked_by'])}.",
        )


def require_resolved_questions(task: dict[str, Any], requirements: dict[str, Any]) -> None:
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

    open_for_task = [value for value in task.get("open_questions", []) if value in unresolved]
    if open_for_task:
        raise ScriptError(
            "TASK_HAS_OPEN_QUESTIONS",
            f"{task.get('task_id')} depends on unresolved items: {', '.join(open_for_task)}. "
            "Resolve them with the user and record the decision before implementing.",
        )


def collect_source_requirements(
    task: dict[str, Any], requirements: dict[str, Any]
) -> list[dict[str, Any]]:
    by_id = {
        item["requirement_id"]: item
        for item in requirements.get("requirements", [])
        if isinstance(item.get("requirement_id"), str)
    }

    if not task.get("source_requirements"):
        raise ScriptError(
            "REQUIREMENT_NOT_CONFIRMED",
            f"{task.get('task_id')} names no source requirement and cannot be traced.",
        )

    collected: list[dict[str, Any]] = []
    for requirement_id in task["source_requirements"]:
        requirement = by_id.get(requirement_id)
        if requirement is None:
            raise ScriptError(
                "REQUIREMENT_NOT_CONFIRMED",
                f"{task.get('task_id')} references {requirement_id}, "
                "which is not in the requirements index.",
            )
        state = requirement.get("state")
        if state not in IMPLEMENTABLE_STATES:
            raise ScriptError(
                "REQUIREMENT_NOT_CONFIRMED",
                f"{task.get('task_id')} references {requirement_id}, which is {state}. "
                "Only CONFIRMED, CLARIFIED, or OPTIONAL requirements may be implemented.",
            )
        collected.append(
            {
                "requirement_id": requirement_id,
                "statement": requirement.get("statement", ""),
                "state": state,
                "sources": [
                    {
                        "source_id": source.get("source_id"),
                        "section": source.get("section"),
                        "subsection": source.get("subsection"),
                        "page": source.get("page"),
                    }
                    for source in requirement.get("sources", [])
                ],
            }
        )
    return collected


def check_dependencies(
    task: dict[str, Any], backlog: dict[str, Any], allow_open: bool
) -> list[str]:
    by_id = {
        item["task_id"]: item
        for item in backlog.get("tasks", [])
        if isinstance(item.get("task_id"), str)
    }

    open_dependencies: list[str] = []
    for dependency_id in task.get("dependencies", []):
        dependency = by_id.get(dependency_id)
        if dependency is None:
            raise ScriptError(
                "UNKNOWN_DEPENDENCY",
                f"{task.get('task_id')} depends on {dependency_id}, which is not in the backlog.",
            )
        if dependency.get("readiness") != "DONE":
            open_dependencies.append(dependency_id)

    if open_dependencies and not allow_open:
        raise ScriptError(
            "DEPENDENCY_NOT_DONE",
            f"{task.get('task_id')} depends on work that is not DONE: "
            f"{', '.join(open_dependencies)}. Implement those first, or pass "
            "--allow-open-dependencies to record an explicit human override.",
        )
    return open_dependencies


def build_handoff(
    context: dict[str, Any],
    requirements: dict[str, Any],
    backlog: dict[str, Any],
    task: dict[str, Any],
    repository: dict[str, Any],
    source_requirements: list[dict[str, Any]],
    open_dependencies: list[str],
) -> dict[str, Any]:
    constraints = list(task.get("constraints", []))
    constraints.extend(
        f"Mandatory stack: {value}" for value in context.get("stack", {}).get("mandatory", [])
    )
    constraints.extend(context.get("architecture_constraints", []))

    return {
        "task_id": task["task_id"],
        "backlog_ref": task.get("backlog_ref", task["task_id"]),
        "project_id": backlog.get("project_id"),
        "task_title": task.get("title", ""),
        "task_description": task.get("description", ""),
        "task_type": task.get("task_type", "feature"),
        "task_slug": task.get("slug", ""),
        "repository": {
            "url": repository.get("url"),
            "path": repository.get("path"),
            "base_branch": repository.get("base_branch"),
            "project_type": repository.get("project_type", "unknown"),
        },
        "acceptance_criteria": list(task.get("acceptance_criteria", [])),
        "constraints": constraints,
        "dependencies": list(task.get("dependencies", [])),
        "out_of_scope": list(task.get("out_of_scope", [])),
        "test_requirements": list(task.get("test_requirements", [])),
        "source_requirements": source_requirements,
        "source_specifications": [
            {
                "source_id": source.get("source_id"),
                "title": source.get("title"),
                "location": source.get("location"),
            }
            for source in requirements.get("sources", [])
        ],
        "optional_target_paths": [],
        "risk_level": task.get("risk_level"),
        "readiness": "READY",
        "open_dependencies": open_dependencies,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert one READY backlog task into an engineering workflow handoff.",
    )
    parser.add_argument("--project-context", required=True, help="Path to project.json.")
    parser.add_argument("--requirements", required=True, help="Path to requirements.json.")
    parser.add_argument("--backlog", required=True, help="Path to backlog.json.")
    parser.add_argument(
        "--task-id",
        required=True,
        help="Task to prepare, by task_id or backlog_ref.",
    )
    parser.add_argument("--out", default=None, help="Optional path to write the handoff JSON.")
    parser.add_argument(
        "--allow-open-dependencies",
        action="store_true",
        help="Human override: prepare the task even though a dependency is not DONE.",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    context = load_json(Path(args.project_context), "Project context")
    requirements = load_json(Path(args.requirements), "Requirements index")
    backlog = load_json(Path(args.backlog), "Backlog")

    repository = require_confirmed_context(context)
    require_approved_backlog(backlog)

    task = find_task(backlog, args.task_id.strip())
    require_ready(task)
    require_resolved_questions(task, requirements)
    source_requirements = collect_source_requirements(task, requirements)
    open_dependencies = check_dependencies(task, backlog, args.allow_open_dependencies)

    handoff = build_handoff(
        context,
        requirements,
        backlog,
        task,
        repository,
        source_requirements,
        open_dependencies,
    )

    if args.out is not None:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return handoff


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        emit(run(args))
        return 0
    except ScriptError as exc:
        emit({"status": "error", "error_code": exc.error_code, "message": exc.message})
        return 1
    except Exception as exc:  # pragma: no cover - last-resort CLI guard
        emit({"status": "error", "error_code": "INTERNAL_ERROR", "message": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())

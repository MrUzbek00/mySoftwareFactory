"""Assemble a completion report from the artifacts each stage produced.

This script is the audit step. It validates every artifact against its schema,
cross-checks that they describe the same task, branch, and commits, and reports
contradictions instead of smoothing them over. It reads artifacts only; it never
writes to the repository.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TASK_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9]+(?:-[A-Z0-9]+)*$")

STAGE_SCHEMAS = {
    "inspect-repository": "repository-context.schema.json",
    "plan-change": "change-plan.schema.json",
    "isolate-task": "workspace-result.schema.json",
    "implement-change": "implementation-result.schema.json",
    "validate-change": "validation-report.schema.json",
    "before-after": "before-after-report.schema.json",
    "security-review": "security-review.schema.json",
    "update-documentation": "documentation-update.schema.json",
    "create-pull-request": "pull-request-result.schema.json",
    "review-pull-request": "pull-request-review.schema.json",
    "revise-pull-request": "revision-result.schema.json",
}
REQUIRED_STAGES = (
    "inspect-repository",
    "plan-change",
    "isolate-task",
    "implement-change",
    "validate-change",
    "create-pull-request",
)


class ScriptError(Exception):
    """Structured error that can be returned as JSON."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def validate_task_id(task_id: str) -> str:
    value = task_id.strip()
    if not TASK_ID_PATTERN.fullmatch(value):
        raise ScriptError(
            "INVALID_TASK_ID",
            "Task ID must match TASK-* using uppercase safe parts.",
        )
    return value


def parse_artifact_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise ScriptError("INVALID_ARTIFACT", f"Artifact must be stage=path: {spec}")
    stage, raw_path = spec.split("=", 1)
    stage = stage.strip()
    if stage not in STAGE_SCHEMAS:
        known = ", ".join(sorted(STAGE_SCHEMAS))
        raise ScriptError("UNKNOWN_STAGE", f"Unknown stage {stage}. Known stages: {known}.")
    path = Path(raw_path.strip()).expanduser().resolve()
    if not path.is_file():
        raise ScriptError("MISSING_ARTIFACT", f"Artifact file does not exist: {path}")
    return stage, path


def load_artifact(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ScriptError("INVALID_ARTIFACT_JSON", f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ScriptError("INVALID_ARTIFACT_JSON", f"{path} must contain a JSON object.")
    return data


def validate_against_schema(
    payload: dict[str, Any], schema_path: Path
) -> tuple[bool | None, list[str]]:
    """Validate with jsonschema when available, else fall back to a required-key check."""
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"schema unreadable: {exc}"]

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        missing = [key for key in schema.get("required", []) if key not in payload]
        if missing:
            return False, [f"missing required key: {key}" for key in missing]
        return None, ["jsonschema not installed; only required keys were checked"]

    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.path))
    if not errors:
        return True, []
    return False, [f"{list(e.path) or '<root>'}: {e.message}" for e in errors[:10]]


def cross_check(artifacts: dict[str, dict[str, Any]], task_id: str) -> list[str]:
    problems: list[str] = []

    for stage, payload in artifacts.items():
        found = payload.get("task_id")
        if found is not None and found != task_id:
            problems.append(f"{stage}: task_id is {found}, expected {task_id}")

    branches = {
        stage: payload["branch"]
        for stage, payload in artifacts.items()
        if isinstance(payload.get("branch"), str)
    }
    distinct = set(branches.values())
    if len(distinct) > 1:
        detail = ", ".join(f"{stage}={branch}" for stage, branch in sorted(branches.items()))
        problems.append(f"stages disagree on branch: {detail}")

    validation = artifacts.get("validate-change")
    pull_request = artifacts.get("create-pull-request")
    if validation and validation.get("status") != "pass" and pull_request:
        problems.append(
            "a pull request exists but validation did not pass; "
            f"validation status is {validation.get('status')}"
        )

    if validation and pull_request:
        v_head = validation.get("head_commit")
        p_head = pull_request.get("head_commit")
        if v_head and p_head and v_head != p_head:
            problems.append(
                f"pull request head {p_head} does not match the validated commit {v_head}"
            )

    implementation = artifacts.get("implement-change")
    if implementation and implementation.get("status") == "blocked" and pull_request:
        problems.append("implementation is marked blocked but a pull request was opened")

    security = artifacts.get("security-review")
    if security and security.get("counts", {}).get("CRITICAL", 0) and pull_request:
        problems.append(
            "security review recorded CRITICAL findings and a pull request was still opened"
        )

    return problems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble and audit a completion report from stage artifacts.",
    )
    parser.add_argument(
        "--task-id",
        required=True,
        help="Traceable task ID, for example TASK-123.",
    )
    parser.add_argument("--schemas-dir", required=True, help="Path to the schemas directory.")
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        dest="artifacts",
        metavar="STAGE=PATH",
        help="Stage artifact to include. Repeatable.",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    task_id = validate_task_id(args.task_id)
    schemas_dir = Path(args.schemas_dir).expanduser().resolve()
    if not schemas_dir.is_dir():
        raise ScriptError("INVALID_SCHEMAS_DIR", f"Not a directory: {schemas_dir}")

    if not args.artifacts:
        raise ScriptError("NO_ARTIFACTS", "No artifacts provided. Pass --artifact stage=path.")

    provided: dict[str, Path] = {}
    for spec in args.artifacts:
        stage, path = parse_artifact_spec(spec)
        provided[stage] = path

    loaded: dict[str, dict[str, Any]] = {}
    stages: list[dict[str, Any]] = []
    for stage in STAGE_SCHEMAS:
        path = provided.get(stage)
        if path is None:
            stages.append({"stage": stage, "present": False, "valid": None, "errors": []})
            continue
        payload = load_artifact(path)
        loaded[stage] = payload
        valid, errors = validate_against_schema(payload, schemas_dir / STAGE_SCHEMAS[stage])
        stages.append({"stage": stage, "present": True, "valid": valid, "errors": errors})

    inconsistencies = cross_check(loaded, task_id)
    inconsistencies.extend(
        f"{entry['stage']}: artifact does not satisfy its schema"
        for entry in stages
        if entry["valid"] is False
    )

    missing_required = [stage for stage in REQUIRED_STAGES if stage not in loaded]
    inconsistencies.extend(
        f"required stage artifact missing: {stage}" for stage in missing_required
    )

    validation = loaded.get("validate-change")
    security = loaded.get("security-review")
    pull_request = loaded.get("create-pull-request")
    revision = loaded.get("revise-pull-request")
    workspace = loaded.get("isolate-task")

    branch = None
    for candidate in (workspace, pull_request, validation):
        if candidate and isinstance(candidate.get("branch"), str):
            branch = candidate["branch"]
            break

    pr_url = None
    for candidate in (revision, pull_request):
        if candidate and candidate.get("pull_request_url"):
            pr_url = candidate["pull_request_url"]
            break

    if missing_required or inconsistencies:
        awaiting = "correction of the reported inconsistencies"
    elif pr_url:
        awaiting = "human review and merge"
    else:
        awaiting = "a pull request"

    return {
        "status": "complete" if not missing_required and not inconsistencies else "incomplete",
        "task_id": task_id,
        "stages": stages,
        "artifacts": {stage: str(path) for stage, path in sorted(provided.items())},
        "inconsistencies": inconsistencies,
        "outcome": {
            "branch": branch,
            "validation_status": validation.get("status") if validation else None,
            "security_status": security.get("status") if security else None,
            "pull_request_url": pr_url,
            "awaiting": awaiting,
        },
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = run(args)
        emit(report)
        return 0 if report["status"] == "complete" else 1
    except ScriptError as exc:
        emit({"status": "error", "error_code": exc.error_code, "message": exc.message})
        return 1
    except Exception as exc:  # pragma: no cover - last-resort CLI guard
        emit({"status": "error", "error_code": "INTERNAL_ERROR", "message": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())

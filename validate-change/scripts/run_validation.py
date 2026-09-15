"""Run validation checks for one software-factory task and emit structured evidence.

This script exists so that test and lint results are captured by software rather
than asserted by an agent. Every check records the real command, the real exit
code, and a tail of the real output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TASK_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
SHORTSTAT_PATTERN = re.compile(
    r"(?:(\d+) files? changed)?"
    r"(?:, (\d+) insertions?\(\+\))?"
    r"(?:, (\d+) deletions?\(-\))?"
)
TAIL_LINES = 40
TAIL_LINE_CHARS = 500
DEFAULT_TIMEOUT = 900

QUALITY_CRITERIA = frozenset(
    {
        "naming",
        "function-names",
        "class-names",
        "parameter-names",
        "input-types",
        "return-types",
        "nullability",
        "collection-types",
        "structured-inputs",
        "documentation",
        "variadic-contract",
        "boolean-names",
        "constants-enums",
        "comments",
        "cohesion",
        "side-effects",
        "error-behavior",
        "domain-language",
        "framework-conventions",
    }
)
QUALITY_SEVERITIES = ("BLOCKING", "ADVISORY")


class ScriptError(Exception):
    """Structured error that can be returned as JSON."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def run_git(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ScriptError("GIT_COMMAND_FAILED", detail or f"git {' '.join(args)} failed")
    return result


def validate_task_id(task_id: str) -> str:
    value = task_id.strip()
    if not TASK_ID_PATTERN.fullmatch(value):
        raise ScriptError(
            "INVALID_TASK_ID",
            "Task ID must match TASK-* using uppercase safe parts.",
        )
    return value


def resolve_worktree(worktree_arg: str) -> Path:
    worktree = Path(worktree_arg).expanduser().resolve()
    if not worktree.exists() or not worktree.is_dir():
        raise ScriptError("INVALID_WORKTREE", "Worktree path must be an existing directory.")

    result = run_git(worktree, ["rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        raise ScriptError("INVALID_WORKTREE", "Worktree path must be inside a Git repository.")
    return worktree


def tail_output(text: str) -> str:
    lines = text.splitlines()[-TAIL_LINES:]
    clipped = [line[:TAIL_LINE_CHARS] for line in lines]
    return "\n".join(clipped).strip()


def split_command(command: str) -> list[str]:
    """Split a command line into argv.

    POSIX splitting treats a backslash as an escape, which destroys any
    Windows path that contains one. On Windows, split without POSIX rules and
    strip the quotes that mode leaves attached to each token.
    """
    if os.name == "nt":
        parts = shlex.split(command, posix=False)
        return [
            part[1:-1] if len(part) > 1 and part[0] == part[-1] and part[0] in "\"'" else part
            for part in parts
        ]
    return shlex.split(command)


def parse_check_spec(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise ScriptError("INVALID_CHECK", f"Check must be formatted as name=command: {spec}")
    name, command = spec.split("=", 1)
    name = name.strip()
    command = command.strip()
    if not name or not command:
        raise ScriptError("INVALID_CHECK", f"Check name and command are both required: {spec}")
    return name, command


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_quality_review(path_arg: str) -> dict[str, Any]:
    """Load an agent-authored backend code quality review and check its shape.

    The review is judgment, so a model produces it. Whether a blocking finding
    stops the change is not judgment, so this script decides that. A malformed
    review is an error rather than an empty result, because silently dropping it
    would report a change as validated that nobody reviewed.
    """
    path = Path(path_arg).expanduser().resolve()
    if not path.is_file():
        raise ScriptError("INVALID_QUALITY_REVIEW", f"Quality review file does not exist: {path}")

    try:
        with path.open(encoding="utf-8") as handle:
            review = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ScriptError(
            "INVALID_QUALITY_REVIEW", f"{path} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(review, dict):
        raise ScriptError("INVALID_QUALITY_REVIEW", f"{path} must contain a JSON object.")

    status = review.get("status")
    if status not in ("pass", "findings", "not_reviewed"):
        raise ScriptError(
            "INVALID_QUALITY_REVIEW",
            "Quality review status must be pass, findings, or not_reviewed.",
        )

    findings = review.get("findings", [])
    if not isinstance(findings, list):
        raise ScriptError("INVALID_QUALITY_REVIEW", "Quality review findings must be a list.")

    counts = dict.fromkeys(QUALITY_SEVERITIES, 0)
    for finding in findings:
        if not isinstance(finding, dict):
            raise ScriptError("INVALID_QUALITY_REVIEW", "Each finding must be a JSON object.")
        required_keys = ("criterion", "severity", "file", "detail")
        missing = [key for key in required_keys if not finding.get(key)]
        if missing:
            raise ScriptError(
                "INVALID_QUALITY_REVIEW",
                f"Finding is missing required fields: {', '.join(missing)}.",
            )
        if finding["criterion"] not in QUALITY_CRITERIA:
            known = ", ".join(sorted(QUALITY_CRITERIA))
            raise ScriptError(
                "INVALID_QUALITY_REVIEW",
                f"Unknown criterion {finding['criterion']}. Known criteria: {known}.",
            )
        if finding["severity"] not in QUALITY_SEVERITIES:
            raise ScriptError(
                "INVALID_QUALITY_REVIEW",
                f"Severity must be one of {', '.join(QUALITY_SEVERITIES)}.",
            )
        counts[finding["severity"]] += 1

    if status == "findings" and not findings:
        raise ScriptError(
            "INVALID_QUALITY_REVIEW",
            "Quality review status is findings but no finding was recorded.",
        )
    if status == "pass" and findings:
        raise ScriptError(
            "INVALID_QUALITY_REVIEW",
            "Quality review status is pass but findings were recorded.",
        )

    resolved: dict[str, Any] = {
        "status": status,
        "reviewed_files": list(review.get("reviewed_files", [])),
        "findings": findings,
        "counts": counts,
    }
    if "skipped_files" in review:
        resolved["skipped_files"] = list(review["skipped_files"])
    if status == "not_reviewed":
        resolved["not_reviewed_reason"] = review.get("not_reviewed_reason")
    return resolved


def detect_checks(worktree: Path) -> list[tuple[str, str]]:
    """Detect checks from files that actually exist. Never guess a missing tool."""
    detected: list[tuple[str, str]] = []

    pyproject = worktree / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8", errors="replace")
        if "ruff" in content:
            detected.append(("lint", "ruff check ."))
        if "pytest" in content:
            detected.append(("tests", "pytest -q"))
    elif (worktree / "setup.cfg").exists() and (worktree / "tests").is_dir():
        detected.append(("tests", "pytest -q"))

    package_json = worktree / "package.json"
    if package_json.exists():
        scripts = read_json(package_json).get("scripts", {})
        if isinstance(scripts, dict):
            if "lint" in scripts:
                detected.append(("lint", "npm run lint --silent"))
            if "typecheck" in scripts:
                detected.append(("typecheck", "npm run typecheck --silent"))
            if "test" in scripts:
                detected.append(("tests", "npm test --silent"))

    if (worktree / "go.mod").exists():
        detected.append(("vet", "go vet ./..."))
        detected.append(("tests", "go test ./..."))

    if (worktree / "Cargo.toml").exists():
        detected.append(("tests", "cargo test"))

    return detected


def run_check(worktree: Path, name: str, command: str, timeout: int) -> dict[str, Any]:
    try:
        argv = split_command(command)
    except ValueError as exc:
        raise ScriptError("INVALID_CHECK", f"Cannot parse command for {name}: {exc}") from exc
    if not argv:
        raise ScriptError("INVALID_CHECK", f"Empty command for check {name}.")

    executable = shutil.which(argv[0])
    if executable is None:
        return {
            "name": name,
            "command": command,
            "status": "not_run",
            "exit_code": None,
            "duration_seconds": 0.0,
            "output_tail": f"Executable not found on PATH: {argv[0]}",
        }

    started = time.monotonic()
    try:
        result = subprocess.run(
            [executable, *argv[1:]],
            cwd=str(worktree),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "name": name,
            "command": command,
            "status": "timeout",
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "output_tail": f"Check exceeded {timeout}s timeout.",
        }

    duration = round(time.monotonic() - started, 3)
    combined = f"{result.stdout}\n{result.stderr}".strip()
    return {
        "name": name,
        "command": command,
        "status": "pass" if result.returncode == 0 else "fail",
        "exit_code": result.returncode,
        "duration_seconds": duration,
        "output_tail": tail_output(combined),
    }


def working_tree_check(worktree: Path) -> dict[str, Any]:
    started = time.monotonic()
    result = run_git(worktree, ["status", "--porcelain"], check=False)
    dirty = result.stdout.strip()
    return {
        "name": "working-tree-clean",
        "command": "git status --porcelain",
        "status": "pass" if not dirty else "fail",
        "exit_code": result.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "output_tail": tail_output(dirty) if dirty else "",
    }


def diff_summary(worktree: Path, base_ref: str) -> dict[str, int]:
    empty = {"files_changed": 0, "insertions": 0, "deletions": 0}
    result = run_git(worktree, ["diff", "--shortstat", f"{base_ref}...HEAD"], check=False)
    if result.returncode != 0:
        return empty

    match = SHORTSTAT_PATTERN.search(result.stdout.strip())
    if match is None:
        return empty
    files, insertions, deletions = match.groups()
    return {
        "files_changed": int(files or 0),
        "insertions": int(insertions or 0),
        "deletions": int(deletions or 0),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run validation checks for one task and emit a structured report.",
    )
    parser.add_argument("--worktree", required=True, help="Path to the task worktree.")
    parser.add_argument("--task-id", required=True, help="Traceable task ID, for example TASK-123.")
    parser.add_argument(
        "--base",
        required=True,
        help="Base branch or ref, for example origin/main.",
    )
    parser.add_argument(
        "--check",
        action="append",
        default=[],
        dest="checks",
        metavar="NAME=COMMAND",
        help="Explicit check to run. Repeatable.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Detect checks from manifests that exist in the worktree.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-check timeout in seconds (default {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--quality-review",
        default=None,
        metavar="PATH",
        help=(
            "Path to the backend code quality review JSON. A BLOCKING finding "
            "fails validation."
        ),
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    task_id = validate_task_id(args.task_id)
    worktree = resolve_worktree(args.worktree)

    if args.timeout <= 0:
        raise ScriptError("INVALID_TIMEOUT", "Timeout must be a positive number of seconds.")

    specs = [parse_check_spec(spec) for spec in args.checks]
    if args.auto:
        seen = {name for name, _ in specs}
        specs.extend((name, cmd) for name, cmd in detect_checks(worktree) if name not in seen)

    if not specs:
        raise ScriptError(
            "NO_CHECKS",
            "No checks were provided or detected. Pass --check name=command or --auto.",
        )

    checks = [working_tree_check(worktree)]
    checks.extend(run_check(worktree, name, command, args.timeout) for name, command in specs)

    branch = run_git(worktree, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    head_commit = run_git(worktree, ["rev-parse", "HEAD"]).stdout.strip()
    passed = all(check["status"] == "pass" for check in checks)

    quality_review = None
    if args.quality_review is not None:
        quality_review = load_quality_review(args.quality_review)
        if quality_review["counts"]["BLOCKING"]:
            passed = False

    report = {
        "status": "pass" if passed else "fail",
        "task_id": task_id,
        "branch": branch,
        "worktree_path": str(worktree),
        "base_branch": args.base,
        "head_commit": head_commit,
        "checks": checks,
        "diff_summary": diff_summary(worktree, args.base),
        "ready_for_pull_request": passed,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    if quality_review is not None:
        report["code_quality"] = quality_review
    return report


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = run(args)
        emit(report)
        return 0 if report["status"] == "pass" else 1
    except ScriptError as exc:
        emit({"status": "error", "error_code": exc.error_code, "message": exc.message})
        return 1
    except Exception as exc:  # pragma: no cover - last-resort CLI guard
        emit({"status": "error", "error_code": "INTERNAL_ERROR", "message": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Capture observable behavior before and after a task change.

The script builds a throwaway detached worktree at the base commit, runs the
same probe commands there and in the task worktree, and records both results.
It never judges which side is correct; it records what differed.
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
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TASK_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
TAIL_LINES = 40
TAIL_LINE_CHARS = 500
DEFAULT_TIMEOUT = 300


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

    POSIX splitting treats a backslash as an escape, which destroys Windows
    paths such as C:\Python\python.exe. On Windows, split without POSIX
    rules and strip the quotes that mode leaves attached to each token.
    """
    if os.name == "nt":
        parts = shlex.split(command, posix=False)
        return [
            part[1:-1] if len(part) > 1 and part[0] == part[-1] and part[0] in "\"'" else part
            for part in parts
        ]
    return shlex.split(command)


def parse_probe_spec(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise ScriptError("INVALID_PROBE", f"Probe must be formatted as name=command: {spec}")
    name, command = spec.split("=", 1)
    name = name.strip()
    command = command.strip()
    if not name or not command:
        raise ScriptError("INVALID_PROBE", f"Probe name and command are both required: {spec}")
    return name, command


def observe(cwd: Path, command: str, timeout: int) -> dict[str, Any]:
    try:
        argv = split_command(command)
    except ValueError as exc:
        raise ScriptError("INVALID_PROBE", f"Cannot parse probe command: {exc}") from exc
    if not argv:
        raise ScriptError("INVALID_PROBE", "Probe command is empty.")

    executable = shutil.which(argv[0])
    if executable is None:
        return {
            "status": "not_run",
            "exit_code": None,
            "output_tail": f"Executable not found on PATH: {argv[0]}",
        }

    try:
        result = subprocess.run(
            [executable, *argv[1:]],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "exit_code": None,
            "output_tail": f"Probe exceeded {timeout}s timeout.",
        }

    combined = f"{result.stdout}\n{result.stderr}".strip()
    return {
        "status": "ran",
        "exit_code": result.returncode,
        "output_tail": tail_output(combined),
    }


def resolve_base_commit(worktree: Path, base_ref: str) -> str:
    result = run_git(worktree, ["merge-base", base_ref, "HEAD"], check=False)
    if result.returncode != 0:
        result = run_git(
            worktree,
            ["rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"],
            check=False,
        )
        if result.returncode != 0:
            raise ScriptError("MISSING_BASE_BRANCH", f"Cannot resolve base ref: {base_ref}.")
    return result.stdout.strip()


def add_base_worktree(worktree: Path, base_commit: str, scratch: Path) -> None:
    result = run_git(
        worktree,
        ["worktree", "add", "--detach", str(scratch), base_commit],
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ScriptError("BASE_WORKTREE_FAILED", detail or "Could not create base worktree.")


def remove_base_worktree(worktree: Path, scratch: Path) -> None:
    """Remove only the detached scratch worktree this script created."""
    head = run_git(scratch, ["symbolic-ref", "--quiet", "HEAD"], check=False)
    if head.returncode == 0:
        # Attached to a branch: not ours, leave it alone.
        return
    run_git(worktree, ["worktree", "remove", "--force", str(scratch)], check=False)
    run_git(worktree, ["worktree", "prune"], check=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture before and after behavior for one task.",
    )
    parser.add_argument("--worktree", required=True, help="Path to the task worktree.")
    parser.add_argument("--task-id", required=True, help="Traceable task ID, for example TASK-123.")
    parser.add_argument(
        "--base",
        required=True,
        help="Base branch or ref, for example origin/main.",
    )
    parser.add_argument(
        "--probe",
        action="append",
        default=[],
        dest="probes",
        metavar="NAME=COMMAND",
        help="Observation to run on both sides. Repeatable.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-probe timeout in seconds (default {DEFAULT_TIMEOUT}).",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    task_id = validate_task_id(args.task_id)
    worktree = resolve_worktree(args.worktree)

    if args.timeout <= 0:
        raise ScriptError("INVALID_TIMEOUT", "Timeout must be a positive number of seconds.")

    specs = [parse_probe_spec(spec) for spec in args.probes]
    if not specs:
        raise ScriptError("NO_PROBES", "No probes were provided. Pass --probe name=command.")

    if run_git(worktree, ["status", "--porcelain"]).stdout.strip():
        raise ScriptError(
            "WORKTREE_NOT_CLEAN",
            "Commit all task work before capturing before and after behavior.",
        )

    branch = run_git(worktree, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    head_commit = run_git(worktree, ["rev-parse", "HEAD"]).stdout.strip()
    base_commit = resolve_base_commit(worktree, args.base)

    scratch_parent = Path(tempfile.mkdtemp(prefix=f"sfg-before-{task_id}-"))
    scratch = scratch_parent / "base"
    probes: list[dict[str, Any]] = []
    try:
        add_base_worktree(worktree, base_commit, scratch)
        for name, command in specs:
            before = observe(scratch, command, args.timeout)
            after = observe(worktree, command, args.timeout)
            changed = (
                before["exit_code"] != after["exit_code"]
                or before["output_tail"] != after["output_tail"]
            )
            probes.append(
                {
                    "name": name,
                    "command": command,
                    "before": before,
                    "after": after,
                    "changed": changed,
                }
            )
    finally:
        if scratch.exists():
            remove_base_worktree(worktree, scratch)
        shutil.rmtree(scratch_parent, ignore_errors=True)

    incomplete = any(
        probe["before"]["status"] != "ran" or probe["after"]["status"] != "ran" for probe in probes
    )
    return {
        "status": "partial" if incomplete else "captured",
        "task_id": task_id,
        "branch": branch,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "probes": probes,
        "differences_detected": any(probe["changed"] for probe in probes),
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


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

"""Push revision commits to an existing pull request branch.

Safety posture: fast-forward pushes only. If the local branch and the remote
branch have diverged, this script stops rather than choosing between someone
else's commits and yours. It never force pushes and never merges.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TASK_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
BRANCH_PATTERN = re.compile(
    r"^(feature|fix|refactor|chore|docs|test)/"
    r"TASK-[A-Z0-9]+(?:-[A-Z0-9]+)*-[a-z0-9]+(?:-[a-z0-9]+)*$"
)
PROTECTED_BRANCHES = {"main", "master", "develop", "development", "trunk", "production", "release"}


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
        errors="replace",
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ScriptError("GIT_COMMAND_FAILED", detail or f"git {' '.join(args)} failed")
    return result


def run_gh(cwd: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("gh")
    if executable is None:
        raise ScriptError("GH_NOT_FOUND", "GitHub CLI (gh) is not installed or not on PATH.")

    result = subprocess.run(
        [executable, *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ScriptError("GH_COMMAND_FAILED", detail or f"gh {' '.join(args)} failed")
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


def resolve_head_branch(worktree: Path, task_id: str) -> str:
    branch = run_git(worktree, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    if branch == "HEAD":
        raise ScriptError("DETACHED_HEAD", "Worktree is in detached HEAD state.")
    if branch.lower() in PROTECTED_BRANCHES or branch.startswith("release/"):
        raise ScriptError(
            "PROTECTED_HEAD_BRANCH",
            f"Refusing to push revisions from a protected branch: {branch}.",
        )
    if not BRANCH_PATTERN.fullmatch(branch):
        raise ScriptError(
            "INVALID_HEAD_BRANCH",
            f"Head branch is not an isolated task branch: {branch}.",
        )
    if task_id not in branch:
        raise ScriptError(
            "TASK_BRANCH_MISMATCH",
            f"Branch {branch} does not carry task ID {task_id}.",
        )
    return branch


def ensure_clean_worktree(worktree: Path) -> None:
    if run_git(worktree, ["status", "--porcelain"]).stdout.strip():
        raise ScriptError(
            "WORKTREE_NOT_CLEAN",
            "Commit all revision work before pushing.",
        )


def load_pull_request(worktree: Path, selector: str, branch: str) -> dict[str, Any]:
    result = run_gh(
        worktree,
        ["pr", "view", selector, "--json", "number,url,state,headRefName,isDraft"],
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ScriptError("PR_PARSE_FAILED", "Could not parse pull request metadata.") from exc

    if data.get("state") != "OPEN":
        raise ScriptError(
            "PULL_REQUEST_NOT_OPEN",
            f"Pull request is {data.get('state')}, not OPEN. Revisions cannot be pushed.",
        )
    if data.get("headRefName") != branch:
        raise ScriptError(
            "PR_BRANCH_MISMATCH",
            f"Pull request head is {data.get('headRefName')}, not {branch}.",
        )
    return data


def ensure_fast_forward(worktree: Path, branch: str) -> list[dict[str, str]]:
    """Confirm the push can fast-forward, and return the commits it would add."""
    run_git(worktree, ["fetch", "--prune", "origin"], check=False)

    remote_ref = f"origin/{branch}"
    exists = run_git(
        worktree,
        ["rev-parse", "--verify", "--quiet", f"{remote_ref}^{{commit}}"],
        check=False,
    )
    if exists.returncode != 0:
        raise ScriptError(
            "REMOTE_BRANCH_MISSING",
            f"{remote_ref} does not exist. Open the pull request first.",
        )

    counts = run_git(worktree, ["rev-list", "--left-right", "--count", f"{remote_ref}...HEAD"])
    behind_text, ahead_text = counts.stdout.split()
    behind, ahead = int(behind_text), int(ahead_text)

    if behind and ahead:
        raise ScriptError(
            "DIVERGED_BRANCH",
            f"Local branch is {ahead} ahead and {behind} behind {remote_ref}. "
            "Resolve this manually; this script never force pushes.",
        )
    if behind:
        raise ScriptError(
            "BRANCH_BEHIND",
            f"Local branch is {behind} behind {remote_ref}. Pull before revising.",
        )
    if not ahead:
        raise ScriptError("NO_NEW_COMMITS", f"No new commits to push to {remote_ref}.")

    log = run_git(
        worktree,
        ["log", "--format=%h%x00%s", f"{remote_ref}..HEAD"],
    ).stdout.strip()
    commits = []
    for line in log.splitlines():
        sha, _, message = line.partition("\x00")
        commits.append({"sha": sha, "message": message})
    return commits


def push_branch(worktree: Path, branch: str) -> None:
    result = run_git(worktree, ["push", "origin", branch], check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ScriptError("PUSH_FAILED", detail or "Failed to push revision commits.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Push revision commits to an existing pull request. Never force pushes.",
    )
    parser.add_argument("--worktree", required=True, help="Path to the task worktree.")
    parser.add_argument("--task-id", required=True, help="Traceable task ID, for example TASK-123.")
    parser.add_argument("--pr", required=True, help="Pull request number.")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    task_id = validate_task_id(args.task_id)
    worktree = resolve_worktree(args.worktree)
    branch = resolve_head_branch(worktree, task_id)

    ensure_clean_worktree(worktree)
    pull_request = load_pull_request(worktree, str(args.pr).strip(), branch)
    commits = ensure_fast_forward(worktree, branch)
    push_branch(worktree, branch)

    head_commit = run_git(worktree, ["rev-parse", "HEAD"]).stdout.strip()
    return {
        "status": "revised",
        "task_id": task_id,
        "branch": branch,
        "pull_request_number": pull_request["number"],
        "pull_request_url": pull_request["url"],
        "head_commit": head_commit,
        "feedback_addressed": [],
        "feedback_declined": [],
        "commits": commits,
        "pushed": True,
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

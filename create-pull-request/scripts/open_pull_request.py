"""Push one task branch and open a pull request through the GitHub CLI.

Safety posture: this script pushes exactly one non-protected task branch and
opens exactly one pull request. It never force pushes, never rewrites history,
never merges, and never targets a protected branch as the head.
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
BASE_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
PROTECTED_BRANCHES = {"main", "master", "develop", "development", "trunk", "production", "release"}
MAX_BODY_BYTES = 60000


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


def run_gh(
    worktree: Path, args: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("gh")
    if executable is None:
        raise ScriptError("GH_NOT_FOUND", "GitHub CLI (gh) is not installed or not on PATH.")

    result = subprocess.run(
        [executable, *args],
        cwd=str(worktree),
        check=False,
        capture_output=True,
        text=True,
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


def validate_base_ref(base_ref: str) -> str:
    value = base_ref.strip()
    if value.startswith("origin/"):
        value = value.split("/", 1)[1]
    if not value:
        raise ScriptError("INVALID_BASE_BRANCH", "Base branch cannot be empty.")
    if (
        not BASE_REF_PATTERN.fullmatch(value)
        or ".." in value
        or value.startswith(("-", "/", "."))
        or value.endswith(("/", ".", ".lock"))
        or "@{" in value
    ):
        raise ScriptError("INVALID_BASE_BRANCH", "Base branch contains unsafe characters.")
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
            f"Refusing to open a pull request from a protected branch: {branch}.",
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
    result = run_git(worktree, ["status", "--porcelain"])
    if result.stdout.strip():
        raise ScriptError(
            "WORKTREE_NOT_CLEAN",
            "All task work must be committed before opening a pull request.",
        )


def ensure_commits_ahead(worktree: Path, base_ref: str, branch: str) -> None:
    result = run_git(
        worktree,
        ["rev-list", "--count", f"origin/{base_ref}..{branch}"],
        check=False,
    )
    if result.returncode != 0:
        raise ScriptError(
            "MISSING_BASE_BRANCH",
            f"Cannot compare against origin/{base_ref}. Fetch the base branch first.",
        )
    if result.stdout.strip() == "0":
        raise ScriptError(
            "NO_COMMITS",
            f"Branch {branch} has no commits ahead of origin/{base_ref}.",
        )


def ensure_gh_authenticated(worktree: Path) -> None:
    result = run_gh(worktree, ["auth", "status"], check=False)
    if result.returncode != 0:
        raise ScriptError(
            "GH_NOT_AUTHENTICATED",
            "GitHub CLI is not authenticated. Run: gh auth login",
        )


def ensure_no_existing_pr(worktree: Path, branch: str) -> None:
    result = run_gh(
        worktree,
        ["pr", "list", "--head", branch, "--state", "open", "--json", "number"],
        check=False,
    )
    if result.returncode != 0:
        return
    try:
        existing = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return
    if existing:
        number = existing[0].get("number")
        raise ScriptError(
            "PULL_REQUEST_EXISTS",
            f"An open pull request already exists for {branch}: #{number}.",
        )


def read_body(body_file_arg: str) -> str:
    body_path = Path(body_file_arg).expanduser().resolve()
    if not body_path.exists() or not body_path.is_file():
        raise ScriptError("INVALID_BODY_FILE", "Pull request body file does not exist.")

    body = body_path.read_text(encoding="utf-8", errors="replace")
    if not body.strip():
        raise ScriptError("EMPTY_BODY", "Pull request body file is empty.")
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise ScriptError("BODY_TOO_LARGE", f"Body exceeds {MAX_BODY_BYTES} bytes.")
    return body


def push_branch(worktree: Path, branch: str) -> None:
    result = run_git(worktree, ["push", "--set-upstream", "origin", branch], check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        if "non-fast-forward" in detail or "rejected" in detail:
            raise ScriptError(
                "PUSH_REJECTED",
                "Push was rejected. Resolve it manually; this script never force pushes.",
            )
        raise ScriptError("PUSH_FAILED", detail or "Failed to push the task branch.")


def create_pull_request(
    worktree: Path,
    branch: str,
    base_ref: str,
    title: str,
    body: str,
    *,
    draft: bool,
    labels: list[str],
    reviewers: list[str],
) -> dict[str, Any]:
    args = [
        "pr",
        "create",
        "--base",
        base_ref,
        "--head",
        branch,
        "--title",
        title,
        "--body",
        body,
    ]
    if draft:
        args.append("--draft")
    for label in labels:
        args.extend(["--label", label])
    for reviewer in reviewers:
        args.extend(["--reviewer", reviewer])

    run_gh(worktree, args)

    view = run_gh(
        worktree,
        ["pr", "view", branch, "--json", "number,url,isDraft"],
    )
    try:
        data = json.loads(view.stdout)
    except json.JSONDecodeError as exc:
        raise ScriptError(
            "PR_VERIFY_FAILED", "Could not read back the created pull request."
        ) from exc

    number = data.get("number")
    url = data.get("url")
    if not isinstance(number, int) or not url:
        raise ScriptError("PR_VERIFY_FAILED", "Created pull request is missing a number or URL.")
    return {"number": number, "url": url, "draft": bool(data.get("isDraft", draft))}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Push one task branch and open a pull request. Never merges.",
    )
    parser.add_argument("--worktree", required=True, help="Path to the task worktree.")
    parser.add_argument("--task-id", required=True, help="Traceable task ID, for example TASK-123.")
    parser.add_argument("--base", required=True, help="Base branch, for example main.")
    parser.add_argument("--title", required=True, help="Pull request title.")
    parser.add_argument("--body-file", required=True, help="Path to a file holding the PR body.")
    parser.add_argument("--draft", action="store_true", help="Open the pull request as a draft.")
    parser.add_argument("--label", action="append", default=[], dest="labels", help="Repeatable.")
    parser.add_argument(
        "--reviewer",
        action="append",
        default=[],
        dest="reviewers",
        help="Repeatable.",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    task_id = validate_task_id(args.task_id)
    base_ref = validate_base_ref(args.base)
    title = args.title.strip()
    if not title:
        raise ScriptError("INVALID_TITLE", "Pull request title cannot be empty.")

    worktree = resolve_worktree(args.worktree)
    branch = resolve_head_branch(worktree, task_id)
    body = read_body(args.body_file)

    ensure_clean_worktree(worktree)
    ensure_gh_authenticated(worktree)
    run_git(worktree, ["fetch", "--prune", "origin"], check=False)
    ensure_commits_ahead(worktree, base_ref, branch)
    ensure_no_existing_pr(worktree, branch)

    head_commit = run_git(worktree, ["rev-parse", "HEAD"]).stdout.strip()
    push_branch(worktree, branch)
    pull_request = create_pull_request(
        worktree,
        branch,
        base_ref,
        title,
        body,
        draft=args.draft,
        labels=args.labels,
        reviewers=args.reviewers,
    )

    return {
        "status": "created",
        "task_id": task_id,
        "branch": branch,
        "base_branch": base_ref,
        "head_commit": head_commit,
        "pull_request_number": pull_request["number"],
        "pull_request_url": pull_request["url"],
        "draft": pull_request["draft"],
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
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

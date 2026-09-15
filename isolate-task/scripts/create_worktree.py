"""Create a safe Git worktree for one software-factory task."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TASK_TYPES = {"feature", "fix", "refactor", "chore", "docs", "test"}
TASK_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
BASE_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


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


def validate_task_type(task_type: str) -> str:
    value = task_type.strip().lower()
    if value not in TASK_TYPES:
        allowed = ", ".join(sorted(TASK_TYPES))
        raise ScriptError("INVALID_TASK_TYPE", f"Task type must be one of: {allowed}.")
    return value


def normalize_slug(raw_slug: str) -> str:
    value = raw_slug.strip().lower()
    if not value:
        raise ScriptError("INVALID_SLUG", "Slug cannot be empty.")
    if "/" in value or "\\" in value or ".." in value:
        raise ScriptError("INVALID_SLUG", "Slug must not contain path traversal or separators.")
    if any(ord(character) < 32 for character in value):
        raise ScriptError("INVALID_SLUG", "Slug must not contain control characters.")
    if not re.fullmatch(r"[a-z0-9 _-]+", value):
        raise ScriptError(
            "INVALID_SLUG",
            "Slug may contain only letters, digits, spaces, hyphens, and underscores.",
        )

    slug = re.sub(r"[\s_]+", "-", value)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not SLUG_PATTERN.fullmatch(slug):
        raise ScriptError("INVALID_SLUG", "Slug must normalize to lowercase hyphenated words.")
    return slug


def validate_base_ref(base_ref: str) -> str:
    value = base_ref.strip()
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


def resolve_repository(repo_arg: str) -> Path:
    repo = Path(repo_arg).expanduser().resolve()
    if not repo.exists() or not repo.is_dir():
        raise ScriptError("INVALID_REPOSITORY", "Repository path must be an existing directory.")

    result = run_git(repo, ["rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        raise ScriptError("INVALID_REPOSITORY", "Repository path must be inside a Git repository.")

    return Path(result.stdout.strip()).resolve()


def ensure_clean_worktree(repo: Path) -> None:
    result = run_git(repo, ["status", "--porcelain"])
    if result.stdout.strip():
        raise ScriptError(
            "WORKTREE_NOT_CLEAN",
            "Repository working tree must be clean before isolation.",
        )


def maybe_fetch(repo: Path, base_ref: str) -> None:
    remotes = set(run_git(repo, ["remote"]).stdout.splitlines())
    if not remotes:
        return

    remote_name = base_ref.split("/", 1)[0] if "/" in base_ref else "origin"
    if remote_name not in remotes:
        return

    result = run_git(repo, ["fetch", "--prune", remote_name], check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ScriptError("FETCH_FAILED", detail or f"Failed to fetch remote {remote_name}.")


def resolve_base_commit(repo: Path, base_ref: str) -> str:
    result = run_git(
        repo,
        ["rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"],
        check=False,
    )
    if result.returncode != 0:
        raise ScriptError("MISSING_BASE_BRANCH", f"Base branch or ref does not exist: {base_ref}.")
    return result.stdout.strip()


def ensure_branch_absent(repo: Path, branch: str) -> None:
    result = run_git(repo, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], check=False)
    if result.returncode == 0:
        raise ScriptError("BRANCH_ALREADY_EXISTS", f"Branch already exists: {branch}.")
    if result.returncode not in {0, 1}:
        raise ScriptError("GIT_COMMAND_FAILED", "Unable to check whether target branch exists.")


def resolve_worktree_path(worktree_root_arg: str, task_id: str, slug: str) -> Path:
    root = Path(worktree_root_arg).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise ScriptError("INVALID_WORKTREE_ROOT", "Worktree root must be a directory.")

    root.mkdir(parents=True, exist_ok=True)
    worktree_path = (root / f"{task_id}-{slug}").resolve()
    try:
        worktree_path.relative_to(root)
    except ValueError as exc:
        raise ScriptError(
            "INVALID_WORKTREE_PATH",
            "Worktree path must stay inside worktree root.",
        ) from exc

    if worktree_path.exists():
        raise ScriptError(
            "WORKTREE_ALREADY_EXISTS",
            f"Worktree path already exists: {worktree_path}.",
        )
    return worktree_path


def create_worktree(repo: Path, branch: str, worktree_path: Path, base_commit: str) -> None:
    result = run_git(
        repo,
        ["worktree", "add", "-b", branch, str(worktree_path), base_commit],
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ScriptError("WORKTREE_CREATE_FAILED", detail or "Git failed to create the worktree.")


def verify_worktree(worktree_path: Path, branch: str, base_commit: str) -> str:
    if not worktree_path.exists() or not worktree_path.is_dir():
        raise ScriptError("WORKTREE_VERIFY_FAILED", "Worktree directory was not created.")

    current_branch = run_git(worktree_path, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    if current_branch != branch:
        raise ScriptError("WORKTREE_VERIFY_FAILED", "Worktree is not on the expected branch.")

    head_commit = run_git(worktree_path, ["rev-parse", "HEAD"]).stdout.strip()
    if head_commit != base_commit:
        raise ScriptError("WORKTREE_VERIFY_FAILED", "Worktree HEAD does not match base commit.")
    return head_commit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an isolated Git worktree for one task.")
    parser.add_argument("--repo", required=True, help="Path to the source Git repository.")
    parser.add_argument("--task-id", required=True, help="Traceable task ID, for example TASK-123.")
    parser.add_argument(
        "--type",
        required=True,
        dest="task_type",
        help="Task type for branch prefix.",
    )
    parser.add_argument("--slug", required=True, help="Short task slug.")
    parser.add_argument(
        "--base",
        required=True,
        help="Base branch or ref, for example origin/main.",
    )
    parser.add_argument(
        "--worktree-root",
        required=True,
        help="Directory that will contain task worktrees.",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    task_id = validate_task_id(args.task_id)
    task_type = validate_task_type(args.task_type)
    slug = normalize_slug(args.slug)
    base_ref = validate_base_ref(args.base)
    branch = f"{task_type}/{task_id}-{slug}"

    repo = resolve_repository(args.repo)
    ensure_clean_worktree(repo)
    maybe_fetch(repo, base_ref)
    base_commit = resolve_base_commit(repo, base_ref)
    ensure_branch_absent(repo, branch)
    worktree_path = resolve_worktree_path(args.worktree_root, task_id, slug)

    create_worktree(repo, branch, worktree_path, base_commit)
    head_commit = verify_worktree(worktree_path, branch, base_commit)

    return {
        "status": "created",
        "task_id": task_id,
        "branch": branch,
        "worktree_path": str(worktree_path),
        "base_branch": base_ref,
        "base_commit": base_commit,
        "head_commit": head_commit,
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

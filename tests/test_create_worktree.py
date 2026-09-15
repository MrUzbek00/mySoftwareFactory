import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "isolate-task" / "scripts" / "create_worktree.py"
GIT_AVAILABLE = shutil.which("git") is not None


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = "Test User"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test User"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    return env


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=git_env(),
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    if not GIT_AVAILABLE:
        pytest.skip("git is required for worktree tests")

    repository = tmp_path / "repo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.name", "Test User")
    git(repository, "config", "user.email", "test@example.com")
    (repository / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    git(repository, "add", "README.md")
    git(repository, "commit", "-m", "Initial commit")
    git(repository, "branch", "-M", "main")
    return repository


def run_script(repo: Path, worktree_root: Path, *extra_args: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--task-id",
            "TASK-123",
            "--type",
            "feature",
            "--slug",
            "password-reset",
            "--base",
            "main",
            "--worktree-root",
            str(worktree_root),
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=git_env(),
    )
    assert completed.stderr == ""
    return completed.returncode, json.loads(completed.stdout)


def test_successful_branch_and_worktree_creation(repo: Path, tmp_path: Path) -> None:
    return_code, payload = run_script(repo, tmp_path / "worktrees")

    assert return_code == 0
    assert payload["status"] == "created"
    assert payload["task_id"] == "TASK-123"
    assert payload["branch"] == "feature/TASK-123-password-reset"
    assert Path(payload["worktree_path"]).exists()
    assert payload["base_commit"] == payload["head_commit"]
    branch = git(Path(payload["worktree_path"]), "rev-parse", "--abbrev-ref", "HEAD")
    assert branch.stdout.strip() == "feature/TASK-123-password-reset"


def test_invalid_repository_fails(tmp_path: Path) -> None:
    if not GIT_AVAILABLE:
        pytest.skip("git is required for worktree tests")

    return_code, payload = run_script(tmp_path / "missing", tmp_path / "worktrees")

    assert return_code == 1
    assert payload["status"] == "error"
    assert payload["error_code"] == "INVALID_REPOSITORY"


def test_invalid_task_type_fails(repo: Path, tmp_path: Path) -> None:
    return_code, payload = run_script(
        repo,
        tmp_path / "worktrees",
        "--type",
        "unsafe",
    )

    assert return_code == 1
    assert payload["error_code"] == "INVALID_TASK_TYPE"


def test_invalid_task_id_fails(repo: Path, tmp_path: Path) -> None:
    return_code, payload = run_script(
        repo,
        tmp_path / "worktrees",
        "--task-id",
        "task-123",
    )

    assert return_code == 1
    assert payload["error_code"] == "INVALID_TASK_ID"


def test_invalid_slug_fails(repo: Path, tmp_path: Path) -> None:
    return_code, payload = run_script(
        repo,
        tmp_path / "worktrees",
        "--slug",
        "../escape",
    )

    assert return_code == 1
    assert payload["error_code"] == "INVALID_SLUG"


def test_existing_branch_fails(repo: Path, tmp_path: Path) -> None:
    git(repo, "branch", "feature/TASK-123-password-reset", "main")

    return_code, payload = run_script(repo, tmp_path / "worktrees")

    assert return_code == 1
    assert payload["error_code"] == "BRANCH_ALREADY_EXISTS"


def test_existing_worktree_path_fails_without_creating_branch(repo: Path, tmp_path: Path) -> None:
    worktree_root = tmp_path / "worktrees"
    existing = worktree_root / "TASK-123-password-reset"
    existing.mkdir(parents=True)

    return_code, payload = run_script(repo, worktree_root)

    assert return_code == 1
    assert payload["error_code"] == "WORKTREE_ALREADY_EXISTS"
    branches = git(repo, "branch", "--list", "feature/TASK-123-password-reset").stdout.strip()
    assert branches == ""


def test_missing_base_branch_fails(repo: Path, tmp_path: Path) -> None:
    return_code, payload = run_script(
        repo,
        tmp_path / "worktrees",
        "--base",
        "missing-branch",
    )

    assert return_code == 1
    assert payload["error_code"] == "MISSING_BASE_BRANCH"


def test_dirty_repository_fails_safely(repo: Path, tmp_path: Path) -> None:
    (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    return_code, payload = run_script(repo, tmp_path / "worktrees")

    assert return_code == 1
    assert payload["error_code"] == "WORKTREE_NOT_CLEAN"
    branches = git(repo, "branch", "--list", "feature/TASK-123-password-reset").stdout.strip()
    assert branches == ""

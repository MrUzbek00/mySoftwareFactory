"""Guard tests for the two scripts that can write to a remote.

These assert that unsafe conditions are refused BEFORE any push or API call is
attempted. They run entirely offline: every case here must fail at a local
precondition, never by reaching the network.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGES = ROOT / "my-software-factory" / "stages"
ENGINEERING = STAGES / "engineering"
OPEN_PR = ENGINEERING / "create-pull-request" / "scripts" / "open_pull_request.py"
PUSH_REVISION = ENGINEERING / "revise-pull-request" / "scripts" / "push_revision.py"
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
        pytest.skip("git is required for publish guard tests")

    repository = tmp_path / "repo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.name", "Test User")
    git(repository, "config", "user.email", "test@example.com")
    (repository / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(repository, "add", "app.py")
    git(repository, "commit", "-m", "Initial commit")
    git(repository, "branch", "-M", "main")
    return repository


@pytest.fixture
def body_file(tmp_path: Path) -> Path:
    path = tmp_path / "body.md"
    path.write_text("## TASK-123\n\nSummary.\n", encoding="utf-8")
    return path


def run_open_pr(repo: Path, body: Path, *extra_args: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [
            sys.executable,
            str(OPEN_PR),
            "--worktree",
            str(repo),
            "--task-id",
            "TASK-123",
            "--base",
            "main",
            "--title",
            "feat(TASK-123): example",
            "--body-file",
            str(body),
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=git_env(),
    )
    return completed.returncode, json.loads(completed.stdout)


def run_push_revision(repo: Path, *extra_args: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [
            sys.executable,
            str(PUSH_REVISION),
            "--worktree",
            str(repo),
            "--task-id",
            "TASK-123",
            "--pr",
            "42",
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=git_env(),
    )
    return completed.returncode, json.loads(completed.stdout)


def test_open_pr_refuses_protected_head_branch(repo: Path, body_file: Path) -> None:
    return_code, payload = run_open_pr(repo, body_file)

    assert return_code == 1
    assert payload["error_code"] == "PROTECTED_HEAD_BRANCH"


def test_open_pr_refuses_non_task_branch(repo: Path, body_file: Path) -> None:
    git(repo, "checkout", "-b", "random-branch")

    return_code, payload = run_open_pr(repo, body_file)

    assert return_code == 1
    assert payload["error_code"] == "INVALID_HEAD_BRANCH"


def test_open_pr_refuses_branch_for_another_task(repo: Path, body_file: Path) -> None:
    git(repo, "checkout", "-b", "feature/TASK-123-example")

    return_code, payload = run_open_pr(repo, body_file, "--task-id", "TASK-999")

    assert return_code == 1
    assert payload["error_code"] == "TASK_BRANCH_MISMATCH"


def test_open_pr_refuses_missing_body_file(repo: Path, tmp_path: Path) -> None:
    git(repo, "checkout", "-b", "feature/TASK-123-example")

    return_code, payload = run_open_pr(repo, tmp_path / "absent.md")

    assert return_code == 1
    assert payload["error_code"] == "INVALID_BODY_FILE"


def test_open_pr_refuses_empty_body_file(repo: Path, tmp_path: Path) -> None:
    git(repo, "checkout", "-b", "feature/TASK-123-example")
    empty = tmp_path / "empty.md"
    empty.write_text("   \n", encoding="utf-8")

    return_code, payload = run_open_pr(repo, empty)

    assert return_code == 1
    assert payload["error_code"] == "EMPTY_BODY"


def test_open_pr_refuses_detached_head(repo: Path, body_file: Path) -> None:
    commit = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "checkout", "--detach", commit)

    return_code, payload = run_open_pr(repo, body_file)

    assert return_code == 1
    assert payload["error_code"] == "DETACHED_HEAD"


def test_push_revision_refuses_protected_head_branch(repo: Path) -> None:
    return_code, payload = run_push_revision(repo)

    assert return_code == 1
    assert payload["error_code"] == "PROTECTED_HEAD_BRANCH"


def test_push_revision_refuses_non_task_branch(repo: Path) -> None:
    git(repo, "checkout", "-b", "random-branch")

    return_code, payload = run_push_revision(repo)

    assert return_code == 1
    assert payload["error_code"] == "INVALID_HEAD_BRANCH"


def test_push_revision_refuses_branch_for_another_task(repo: Path) -> None:
    git(repo, "checkout", "-b", "feature/TASK-123-example")

    return_code, payload = run_push_revision(repo, "--task-id", "TASK-999")

    assert return_code == 1
    assert payload["error_code"] == "TASK_BRANCH_MISMATCH"


def test_push_revision_refuses_dirty_worktree(repo: Path) -> None:
    git(repo, "checkout", "-b", "feature/TASK-123-example")
    (repo / "scratch.txt").write_text("dirty\n", encoding="utf-8")

    return_code, payload = run_push_revision(repo)

    assert return_code == 1
    assert payload["error_code"] == "WORKTREE_NOT_CLEAN"


def test_neither_script_contains_a_force_push_path() -> None:
    for script in (OPEN_PR, PUSH_REVISION):
        source = script.read_text(encoding="utf-8")
        assert "--force" not in source
        assert "force-with-lease" not in source


def test_publishing_scripts_never_merge() -> None:
    for script in (OPEN_PR, PUSH_REVISION):
        source = script.read_text(encoding="utf-8")
        assert '"merge"' not in source
        assert "pr merge" not in source
        assert "auto-merge" not in source

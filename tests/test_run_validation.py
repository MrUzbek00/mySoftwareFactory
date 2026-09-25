import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "validate-change" / "scripts" / "run_validation.py"
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
        pytest.skip("git is required for validation tests")

    repository = tmp_path / "repo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.name", "Test User")
    git(repository, "config", "user.email", "test@example.com")
    (repository / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(repository, "add", "app.py")
    git(repository, "commit", "-m", "Initial commit")
    git(repository, "branch", "-M", "main")
    git(repository, "checkout", "-b", "feature/TASK-123-validate")
    (repository / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    git(repository, "add", "app.py")
    git(repository, "commit", "-m", "Change value")
    return repository


def run_script(repo: Path, *extra_args: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--worktree",
            str(repo),
            "--task-id",
            "TASK-123",
            "--base",
            "main",
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=git_env(),
    )
    return completed.returncode, json.loads(completed.stdout)


def passing_check() -> str:
    return f'ok="{sys.executable}" -c "pass"'


def failing_check() -> str:
    return f'boom="{sys.executable}" -c "import sys; sys.exit(3)"'


def test_passing_check_reports_pass(repo: Path) -> None:
    return_code, payload = run_script(repo, "--check", passing_check())

    assert return_code == 0
    assert payload["status"] == "pass"
    assert payload["ready_for_pull_request"] is True
    assert [check["name"] for check in payload["checks"]] == ["working-tree-clean", "ok"]


def test_failing_check_records_real_exit_code(repo: Path) -> None:
    return_code, payload = run_script(repo, "--check", failing_check())

    assert return_code == 1
    assert payload["status"] == "fail"
    assert payload["ready_for_pull_request"] is False
    boom = next(check for check in payload["checks"] if check["name"] == "boom")
    assert boom["status"] == "fail"
    assert boom["exit_code"] == 3


def test_dirty_worktree_fails_validation(repo: Path) -> None:
    (repo / "scratch.txt").write_text("dirty\n", encoding="utf-8")

    return_code, payload = run_script(repo, "--check", passing_check())

    assert return_code == 1
    assert payload["status"] == "fail"
    clean = next(check for check in payload["checks"] if check["name"] == "working-tree-clean")
    assert clean["status"] == "fail"


def test_missing_executable_is_not_run_rather_than_passing(repo: Path) -> None:
    return_code, payload = run_script(repo, "--check", "ghost=definitely-not-a-real-binary-xyz")

    assert return_code == 1
    assert payload["status"] == "fail"
    ghost = next(check for check in payload["checks"] if check["name"] == "ghost")
    assert ghost["status"] == "not_run"
    assert ghost["exit_code"] is None


def test_diff_summary_reflects_the_change(repo: Path) -> None:
    _, payload = run_script(repo, "--check", passing_check())

    assert payload["diff_summary"]["files_changed"] == 1
    assert payload["diff_summary"]["insertions"] == 1
    assert payload["diff_summary"]["deletions"] == 1


def test_no_checks_fails_explicitly(repo: Path) -> None:
    return_code, payload = run_script(repo)

    assert return_code == 1
    assert payload["error_code"] == "NO_CHECKS"


def test_invalid_check_specification_fails(repo: Path) -> None:
    return_code, payload = run_script(repo, "--check", "missing-equals-sign")

    assert return_code == 1
    assert payload["error_code"] == "INVALID_CHECK"


def test_invalid_task_id_fails(repo: Path) -> None:
    return_code, payload = run_script(repo, "--task-id", "task-123", "--check", passing_check())

    assert return_code == 1
    assert payload["error_code"] == "INVALID_TASK_ID"

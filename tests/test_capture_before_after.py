import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "before-after" / "scripts" / "capture_before_after.py"
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
        pytest.skip("git is required for before-after tests")

    repository = tmp_path / "repo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.name", "Test User")
    git(repository, "config", "user.email", "test@example.com")
    (repository / "demo.py").write_text("print('before')\n", encoding="utf-8")
    git(repository, "add", "demo.py")
    git(repository, "commit", "-m", "Initial commit")
    git(repository, "branch", "-M", "main")
    git(repository, "checkout", "-b", "feature/TASK-123-probe")
    return repository


def change_demo(repo: Path, content: str) -> None:
    (repo / "demo.py").write_text(content, encoding="utf-8")
    git(repo, "add", "demo.py")
    git(repo, "commit", "-m", "Change demo output")


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


def probe() -> str:
    return f'demo="{sys.executable}" demo.py'


def test_behavior_change_is_captured_on_both_sides(repo: Path) -> None:
    change_demo(repo, "print('after')\n")

    return_code, payload = run_script(repo, "--probe", probe())
    observation = payload["probes"][0]

    assert return_code == 0
    assert payload["status"] == "captured"
    assert payload["differences_detected"] is True
    assert observation["changed"] is True
    assert observation["before"]["output_tail"] == "before"
    assert observation["after"]["output_tail"] == "after"


def test_unchanged_behavior_reports_no_difference(repo: Path) -> None:
    (repo / "unrelated.txt").write_text("note\n", encoding="utf-8")
    git(repo, "add", "unrelated.txt")
    git(repo, "commit", "-m", "Add unrelated file")

    _, payload = run_script(repo, "--probe", probe())

    assert payload["differences_detected"] is False
    assert payload["probes"][0]["changed"] is False


def test_scratch_worktree_is_removed(repo: Path) -> None:
    change_demo(repo, "print('after')\n")

    run_script(repo, "--probe", probe())
    worktrees = git(repo, "worktree", "list").stdout

    assert "sfg-before-" not in worktrees


def test_missing_executable_marks_probe_not_run(repo: Path) -> None:
    change_demo(repo, "print('after')\n")

    _, payload = run_script(repo, "--probe", "ghost=definitely-not-a-real-binary-xyz")

    assert payload["status"] == "partial"
    assert payload["probes"][0]["before"]["status"] == "not_run"
    assert payload["probes"][0]["after"]["status"] == "not_run"


def test_dirty_worktree_fails(repo: Path) -> None:
    (repo / "scratch.txt").write_text("dirty\n", encoding="utf-8")

    return_code, payload = run_script(repo, "--probe", probe())

    assert return_code == 1
    assert payload["error_code"] == "WORKTREE_NOT_CLEAN"


def test_no_probes_fails_explicitly(repo: Path) -> None:
    return_code, payload = run_script(repo)

    assert return_code == 1
    assert payload["error_code"] == "NO_PROBES"

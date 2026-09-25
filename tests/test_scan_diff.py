import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "engineering" / "security-review" / "scripts" / "scan_diff.py"
GIT_AVAILABLE = shutil.which("git") is not None

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
GITHUB_TOKEN = "ghp_" + "a" * 36
PASSWORD = "hunter2-super-secret"


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
        pytest.skip("git is required for scan tests")

    repository = tmp_path / "repo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.name", "Test User")
    git(repository, "config", "user.email", "test@example.com")
    (repository / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    git(repository, "add", "app.py")
    git(repository, "commit", "-m", "Initial commit")
    git(repository, "branch", "-M", "main")
    git(repository, "checkout", "-b", "feature/TASK-123-scan")
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


def commit_file(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-m", f"Add {name}")


def test_clean_diff_reports_no_findings(repo: Path) -> None:
    commit_file(repo, "safe.py", "def greet(name):\n    return f'hello {name}'\n")

    return_code, payload = run_script(repo)

    assert return_code == 0
    assert payload["status"] == "clean"
    assert payload["findings"] == []
    assert payload["counts"] == {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}


def test_detects_secrets_and_dangerous_sinks(repo: Path) -> None:
    commit_file(
        repo,
        "danger.py",
        "import yaml\n"
        f'AWS_KEY = "{AWS_KEY}"\n'
        f'GH_TOKEN = "{GITHUB_TOKEN}"\n'
        "def load(raw):\n"
        "    return yaml.load(raw)\n"
        "def boom(src):\n"
        "    return eval(src)\n",
    )

    return_code, payload = run_script(repo)
    rules = {finding["rule"] for finding in payload["findings"]}

    assert return_code == 1
    assert payload["status"] == "findings"
    assert {"aws-access-key-id", "github-token", "yaml-unsafe-load", "python-eval-exec"} <= rules
    assert payload["counts"]["CRITICAL"] == 2
    assert payload["requires_human_review"] is True


def test_secret_values_are_redacted_from_the_report(repo: Path) -> None:
    commit_file(
        repo,
        "leak.py",
        f'AWS_KEY = "{AWS_KEY}"\n'
        f'GH_TOKEN = "{GITHUB_TOKEN}"\n'
        f'password = "{PASSWORD}"\n',
    )

    _, payload = run_script(repo)
    serialized = json.dumps(payload)

    assert AWS_KEY not in serialized
    assert GITHUB_TOKEN not in serialized
    assert PASSWORD not in serialized
    assert "<redacted:" in serialized


def test_reports_line_numbers_from_the_new_file(repo: Path) -> None:
    commit_file(repo, "sink.py", "x = 1\ny = 2\nimport os\nos.system('ls')\n")

    _, payload = run_script(repo)
    finding = next(f for f in payload["findings"] if f["rule"] == "os-system-call")

    assert finding["file"] == "sink.py"
    assert finding["line"] == 4


def test_dependency_changes_are_reported(repo: Path) -> None:
    commit_file(repo, "requirements.txt", "requests==2.32.0\nPyYAML==6.0.1\n")

    _, payload = run_script(repo)

    assert payload["dependency_changes"] == [
        {"file": "requirements.txt", "added_lines": ["requests==2.32.0", "PyYAML==6.0.1"]}
    ]
    assert payload["requires_human_review"] is True


def test_removed_lines_are_not_scanned(repo: Path) -> None:
    commit_file(repo, "old.py", "import os\nos.system('ls')\n")
    git(repo, "rm", "-q", "old.py")
    git(repo, "commit", "-m", "Remove old.py")

    _, payload = run_script(repo)

    assert all(finding["file"] != "old.py" for finding in payload["findings"])


def test_invalid_task_id_fails(repo: Path) -> None:
    return_code, payload = run_script(repo, "--task-id", "task-123")

    assert return_code == 1
    assert payload["error_code"] == "INVALID_TASK_ID"


def test_missing_base_branch_fails(repo: Path) -> None:
    return_code, payload = run_script(repo, "--base", "missing-branch")

    assert return_code == 1
    assert payload["error_code"] == "MISSING_BASE_BRANCH"

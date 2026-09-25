"""Gate tests for the backend code quality review.

The review itself is judgment, so these do not test whether a name is good. They
test the part that must not be judgment: that a BLOCKING finding stops the change,
that an ADVISORY one does not, and that a malformed review is refused rather than
silently dropped.

Checks here use `git --version` because it resolves on PATH without the script
having to parse a path that may contain spaces.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "engineering" / "validate-change" / "scripts" / "run_validation.py"
SCHEMAS = ROOT / "schemas"
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
        pytest.skip("git is required for quality review tests")

    repository = tmp_path / "repo"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.name", "Test User")
    git(repository, "config", "user.email", "test@example.com")
    (repository / "service.php").write_text("<?php\n", encoding="utf-8")
    git(repository, "add", "service.php")
    git(repository, "commit", "-m", "Initial commit")
    git(repository, "branch", "-M", "main")
    git(repository, "checkout", "-b", "feature/TASK-123-quality")
    (repository / "service.php").write_text("<?php\n// changed\n", encoding="utf-8")
    git(repository, "add", "service.php")
    git(repository, "commit", "-m", "Change service")
    return repository


def finding(severity: str = "BLOCKING", **overrides: Any) -> dict[str, Any]:
    payload = {
        "criterion": "return-types",
        "severity": severity,
        "file": "service.php",
        "symbol": "ContractService::createContract",
        "detail": "Returns Contract or false with no declared return type.",
        "suggestion": "Declare : Contract and throw on validation failure.",
    }
    payload.update(overrides)
    return payload


def write_review(directory: Path, review: dict[str, Any]) -> Path:
    path = directory / "quality-review.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    return path


def run_script(repo: Path, *extra_args: str) -> tuple[int, dict[str, Any]]:
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
            "--check",
            "ok=git --version",
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=git_env(),
    )
    return completed.returncode, json.loads(completed.stdout)


def test_validation_without_a_review_is_unchanged(repo: Path) -> None:
    return_code, payload = run_script(repo)

    assert return_code == 0
    assert payload["status"] == "pass"
    assert "code_quality" not in payload


def test_clean_review_passes(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {"status": "pass", "reviewed_files": ["service.php"], "findings": []},
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 0
    assert payload["status"] == "pass"
    assert payload["ready_for_pull_request"] is True
    assert payload["code_quality"]["status"] == "pass"
    assert payload["code_quality"]["counts"] == {"BLOCKING": 0, "ADVISORY": 0}


def test_blocking_finding_fails_validation(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {"status": "findings", "reviewed_files": ["service.php"], "findings": [finding()]},
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 1
    assert payload["status"] == "fail"
    assert payload["ready_for_pull_request"] is False
    assert payload["code_quality"]["counts"]["BLOCKING"] == 1


def test_advisory_finding_does_not_fail_validation(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {
            "status": "findings",
            "reviewed_files": ["service.php"],
            "findings": [finding("ADVISORY", criterion="naming")],
        },
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 0
    assert payload["status"] == "pass"
    assert payload["ready_for_pull_request"] is True
    assert payload["code_quality"]["counts"] == {"BLOCKING": 0, "ADVISORY": 1}


def test_advisory_findings_do_not_hide_a_blocking_one(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {
            "status": "findings",
            "reviewed_files": ["service.php"],
            "findings": [
                finding("ADVISORY", criterion="naming"),
                finding("ADVISORY", criterion="comments"),
                finding("BLOCKING", criterion="nullability"),
            ],
        },
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 1
    assert payload["code_quality"]["counts"] == {"BLOCKING": 1, "ADVISORY": 2}


def test_not_reviewed_is_recorded_and_does_not_block(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {
            "status": "not_reviewed",
            "reviewed_files": [],
            "findings": [],
            "not_reviewed_reason": "No backend files changed.",
        },
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 0
    assert payload["code_quality"]["status"] == "not_reviewed"
    assert payload["code_quality"]["not_reviewed_reason"] == "No backend files changed."


def test_skipped_files_are_preserved(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {
            "status": "pass",
            "reviewed_files": ["service.php"],
            "skipped_files": ["resources/views/show.blade.php"],
            "findings": [],
        },
    )

    _, payload = run_script(repo, "--quality-review", str(review))

    assert payload["code_quality"]["skipped_files"] == ["resources/views/show.blade.php"]


def test_report_with_quality_review_validates_against_its_schema(
    repo: Path, tmp_path: Path
) -> None:
    from jsonschema import Draft202012Validator

    review = write_review(
        tmp_path,
        {
            "status": "findings",
            "reviewed_files": ["service.php"],
            "skipped_files": [],
            "findings": [finding()],
        },
    )
    _, payload = run_script(repo, "--quality-review", str(review))
    schema = json.loads((SCHEMAS / "validation-report.schema.json").read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(payload)


def test_missing_review_file_is_refused(repo: Path, tmp_path: Path) -> None:
    return_code, payload = run_script(repo, "--quality-review", str(tmp_path / "absent.json"))

    assert return_code == 1
    assert payload["error_code"] == "INVALID_QUALITY_REVIEW"


def test_unknown_criterion_is_refused(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {
            "status": "findings",
            "reviewed_files": ["service.php"],
            "findings": [finding(criterion="vibes")],
        },
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 1
    assert payload["error_code"] == "INVALID_QUALITY_REVIEW"
    assert "vibes" in payload["message"]


def test_unknown_severity_is_refused(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {
            "status": "findings",
            "reviewed_files": ["service.php"],
            "findings": [finding(severity="NITPICK")],
        },
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 1
    assert payload["error_code"] == "INVALID_QUALITY_REVIEW"


def test_finding_without_detail_is_refused(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {
            "status": "findings",
            "reviewed_files": ["service.php"],
            "findings": [finding(detail="")],
        },
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 1
    assert payload["error_code"] == "INVALID_QUALITY_REVIEW"
    assert "detail" in payload["message"]


def test_pass_status_with_findings_is_refused(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {"status": "pass", "reviewed_files": ["service.php"], "findings": [finding()]},
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 1
    assert payload["error_code"] == "INVALID_QUALITY_REVIEW"


def test_findings_status_without_findings_is_refused(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {"status": "findings", "reviewed_files": ["service.php"], "findings": []},
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 1
    assert payload["error_code"] == "INVALID_QUALITY_REVIEW"


def test_invalid_review_status_is_refused(repo: Path, tmp_path: Path) -> None:
    review = write_review(
        tmp_path,
        {"status": "probably-fine", "reviewed_files": [], "findings": []},
    )

    return_code, payload = run_script(repo, "--quality-review", str(review))

    assert return_code == 1
    assert payload["error_code"] == "INVALID_QUALITY_REVIEW"


def test_malformed_review_json_is_refused(repo: Path, tmp_path: Path) -> None:
    path = tmp_path / "quality-review.json"
    path.write_text("{not json", encoding="utf-8")

    return_code, payload = run_script(repo, "--quality-review", str(path))

    assert return_code == 1
    assert payload["error_code"] == "INVALID_QUALITY_REVIEW"


def test_standard_covers_every_criterion_the_script_accepts() -> None:
    """The slug vocabulary is the contract between the standard and the gate."""
    standard = (ROOT / "standards" / "backend-code-quality.md").read_text(encoding="utf-8")
    schema = json.loads((SCHEMAS / "validation-report.schema.json").read_text(encoding="utf-8"))
    criteria = schema["properties"]["code_quality"]["properties"]["findings"]["items"][
        "properties"
    ]["criterion"]["enum"]

    missing = [slug for slug in criteria if f"### `{slug}`" not in standard]
    assert missing == []

    source = SCRIPT.read_text(encoding="utf-8")
    assert all(f'"{slug}"' in source for slug in criteria)

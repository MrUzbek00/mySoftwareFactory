import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "engineering" / "completion-report" / "scripts" / "build_report.py"
SCHEMAS = ROOT / "schemas"

BRANCH = "feature/TASK-123-password-reset"
HEAD = "a" * 40


def artifact(name: str, payload: dict, directory: Path) -> str:
    path = directory / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return f"{name}={path}"


@pytest.fixture
def artifacts(tmp_path: Path) -> dict[str, dict]:
    return {
        "inspect-repository": {
            "task_id": "TASK-123",
            "repository": {
                "name": "demo",
                "path": "/workspace/demo",
                "current_branch": "main",
                "head_commit": "abc123",
            },
            "stack": {"languages": [], "frameworks": [], "database": [], "tooling": []},
            "architecture": {"summary": "", "patterns": []},
            "relevant_files": [],
            "relevant_tests": [],
            "entrypoints": [],
            "public_contracts": [],
            "risks": [],
            "unknowns": [],
            "recommended_next_context": [],
        },
        "plan-change": {
            "task_id": "TASK-123",
            "goal": "",
            "current_behavior": "",
            "desired_behavior": "",
            "affected_components": [],
            "affected_files": [],
            "public_contract_changes": [],
            "database_changes": [],
            "configuration_changes": [],
            "implementation_steps": [],
            "test_plan": [],
            "risks": [],
            "dependencies": [],
            "unknowns": [],
            "risk_level": "LOW",
            "requires_human_approval": False,
            "approval_reason": None,
            "ready_for_isolation": True,
        },
        "isolate-task": {
            "status": "created",
            "task_id": "TASK-123",
            "branch": BRANCH,
            "worktree_path": "/workspace/worktrees/TASK-123-password-reset",
            "base_branch": "origin/main",
            "base_commit": "abc123",
            "head_commit": "abc123",
            "created_at": "2026-09-15T00:00:00Z",
        },
        "implement-change": {
            "status": "implemented",
            "task_id": "TASK-123",
            "branch": BRANCH,
            "worktree_path": "/workspace/worktrees/TASK-123-password-reset",
            "steps_completed": [],
            "steps_skipped": [],
            "files_added": [],
            "files_modified": [],
            "files_deleted": [],
            "tests_added": [],
            "commits": [],
            "plan_deviations": [],
            "unknowns": [],
            "blocked_reason": None,
            "ready_for_validation": True,
        },
        "validate-change": {
            "status": "pass",
            "task_id": "TASK-123",
            "branch": BRANCH,
            "worktree_path": "/workspace/worktrees/TASK-123-password-reset",
            "base_branch": "origin/main",
            "head_commit": HEAD,
            "checks": [
                {
                    "name": "tests",
                    "command": "pytest -q",
                    "status": "pass",
                    "exit_code": 0,
                    "duration_seconds": 1.0,
                    "output_tail": "",
                }
            ],
            "diff_summary": {"files_changed": 1, "insertions": 1, "deletions": 0},
            "ready_for_pull_request": True,
            "generated_at": "2026-09-15T00:00:00Z",
        },
        "create-pull-request": {
            "status": "created",
            "task_id": "TASK-123",
            "branch": BRANCH,
            "base_branch": "main",
            "head_commit": HEAD,
            "pull_request_number": 42,
            "pull_request_url": "https://github.com/owner/repo/pull/42",
            "draft": False,
            "created_at": "2026-09-15T00:00:00Z",
        },
    }


def run_script(payloads: dict[str, dict], directory: Path, task_id: str = "TASK-123"):
    args = [
        sys.executable,
        str(SCRIPT),
        "--task-id",
        task_id,
        "--schemas-dir",
        str(SCHEMAS),
    ]
    for name, payload in payloads.items():
        args.extend(["--artifact", artifact(name, payload, directory)])

    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    return completed.returncode, json.loads(completed.stdout)


def test_consistent_artifacts_report_complete(artifacts: dict, tmp_path: Path) -> None:
    return_code, payload = run_script(artifacts, tmp_path)

    assert return_code == 0
    assert payload["status"] == "complete"
    assert payload["inconsistencies"] == []
    assert payload["outcome"]["branch"] == BRANCH
    assert payload["outcome"]["validation_status"] == "pass"
    assert payload["outcome"]["awaiting"] == "human review and merge"


def test_optional_stages_are_reported_absent(artifacts: dict, tmp_path: Path) -> None:
    _, payload = run_script(artifacts, tmp_path)
    stages = {entry["stage"]: entry for entry in payload["stages"]}

    assert stages["before-after"]["present"] is False
    assert stages["before-after"]["valid"] is None
    assert stages["validate-change"]["present"] is True


def test_pull_request_without_passing_validation_is_flagged(
    artifacts: dict, tmp_path: Path
) -> None:
    artifacts["validate-change"]["status"] = "fail"
    artifacts["validate-change"]["ready_for_pull_request"] = False

    return_code, payload = run_script(artifacts, tmp_path)

    assert return_code == 1
    assert payload["status"] == "incomplete"
    assert any("validation did not pass" in item for item in payload["inconsistencies"])


def test_head_commit_mismatch_is_flagged(artifacts: dict, tmp_path: Path) -> None:
    artifacts["create-pull-request"]["head_commit"] = "b" * 40

    _, payload = run_script(artifacts, tmp_path)

    assert any("does not match the validated commit" in i for i in payload["inconsistencies"])


def test_branch_disagreement_is_flagged(artifacts: dict, tmp_path: Path) -> None:
    artifacts["create-pull-request"]["branch"] = "feature/TASK-123-other-slug"

    _, payload = run_script(artifacts, tmp_path)

    assert any("disagree on branch" in item for item in payload["inconsistencies"])


def test_critical_security_finding_with_pull_request_is_flagged(
    artifacts: dict, tmp_path: Path
) -> None:
    artifacts["security-review"] = {
        "status": "findings",
        "task_id": "TASK-123",
        "branch": BRANCH,
        "base_commit": "abc123",
        "head_commit": HEAD,
        "findings": [
            {
                "rule": "aws-access-key-id",
                "severity": "CRITICAL",
                "file": "app.py",
                "line": 1,
                "evidence": "<redacted:20chars>",
            }
        ],
        "dependency_changes": [],
        "counts": {"CRITICAL": 1, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
        "requires_human_review": True,
        "generated_at": "2026-09-15T00:00:00Z",
    }

    _, payload = run_script(artifacts, tmp_path)

    assert any("CRITICAL findings" in item for item in payload["inconsistencies"])


def test_blocking_quality_finding_with_pull_request_is_flagged(
    artifacts: dict, tmp_path: Path
) -> None:
    artifacts["validate-change"]["code_quality"] = {
        "status": "findings",
        "reviewed_files": ["app/Services/ContractService.php"],
        "findings": [
            {
                "criterion": "return-types",
                "severity": "BLOCKING",
                "file": "app/Services/ContractService.php",
                "detail": "Returns Contract or false with no declared return type.",
            }
        ],
        "counts": {"BLOCKING": 1, "ADVISORY": 0},
    }

    _, payload = run_script(artifacts, tmp_path)

    assert any("BLOCKING code quality findings" in item for item in payload["inconsistencies"])


def test_advisory_quality_finding_does_not_flag_the_report(
    artifacts: dict, tmp_path: Path
) -> None:
    artifacts["validate-change"]["code_quality"] = {
        "status": "findings",
        "reviewed_files": ["app/Services/ContractService.php"],
        "findings": [
            {
                "criterion": "naming",
                "severity": "ADVISORY",
                "file": "app/Services/ContractService.php",
                "detail": "A local variable name could be clearer.",
            }
        ],
        "counts": {"BLOCKING": 0, "ADVISORY": 1},
    }

    return_code, payload = run_script(artifacts, tmp_path)

    assert return_code == 0
    assert payload["status"] == "complete"


def test_blocked_implementation_with_pull_request_is_flagged(
    artifacts: dict, tmp_path: Path
) -> None:
    artifacts["implement-change"]["status"] = "blocked"
    artifacts["implement-change"]["ready_for_validation"] = False
    artifacts["implement-change"]["blocked_reason"] = "plan was wrong"

    _, payload = run_script(artifacts, tmp_path)

    assert any("blocked" in item for item in payload["inconsistencies"])


def test_mismatched_task_id_is_flagged(artifacts: dict, tmp_path: Path) -> None:
    _, payload = run_script(artifacts, tmp_path, task_id="TASK-999")

    assert payload["status"] == "incomplete"
    assert any("expected TASK-999" in item for item in payload["inconsistencies"])


def test_missing_required_stage_is_flagged(artifacts: dict, tmp_path: Path) -> None:
    del artifacts["validate-change"]

    _, payload = run_script(artifacts, tmp_path)

    assert any("required stage artifact missing" in i for i in payload["inconsistencies"])


def test_schema_violation_is_flagged(artifacts: dict, tmp_path: Path) -> None:
    artifacts["plan-change"]["risk_level"] = "UNKNOWN"

    _, payload = run_script(artifacts, tmp_path)
    stage = next(entry for entry in payload["stages"] if entry["stage"] == "plan-change")

    assert stage["valid"] is False
    assert stage["errors"]


def test_unknown_stage_name_fails(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    path.write_text("{}", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--task-id",
            "TASK-123",
            "--schemas-dir",
            str(SCHEMAS),
            "--artifact",
            f"not-a-stage={path}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 1
    assert payload["error_code"] == "UNKNOWN_STAGE"

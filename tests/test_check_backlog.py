"""Consistency tests for the backlog checker.

These run the script as a subprocess against artifacts written to a temporary
directory, the same way an agent would invoke it. Shared artifacts come from
`conftest.py`; each test mutates one field to prove one rule.
"""

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGES = ROOT / "my-software-factory" / "stages"
SCRIPT = STAGES / "intake" / "decompose-spec" / "scripts" / "check_backlog.py"
SCHEMAS = ROOT / "my-software-factory" / "schemas"


def run_script(payloads: dict[str, Any], directory: Path) -> tuple[int, dict[str, Any]]:
    paths = {}
    for name, payload in payloads.items():
        path = directory / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-context",
            str(paths["project"]),
            "--requirements",
            str(paths["requirements"]),
            "--backlog",
            str(paths["backlog"]),
            "--schemas-dir",
            str(SCHEMAS),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_consistent_backlog_passes(spec_artifacts: dict, tmp_path: Path) -> None:
    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 0
    assert payload["status"] == "consistent"
    assert payload["violations"] == []
    assert payload["counts"]["tasks"] == 2
    assert payload["counts"]["readiness"]["READY"] == 2


def test_traceability_resolves_source_coordinates(spec_artifacts: dict, tmp_path: Path) -> None:
    _, payload = run_script(spec_artifacts, tmp_path)
    entry = next(item for item in payload["traceability"] if item["task_id"] == "TASK-DEMO-010")

    assert entry["requirements"][0]["requirement_id"] == "REQ-AUTH-001"
    assert entry["requirements"][0]["sources"][0]["page"] == "10-11"


def test_dependency_cycle_is_a_violation(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["dependencies"] = ["TASK-DEMO-011"]

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("dependency cycle" in item for item in payload["violations"])


def test_self_dependency_is_a_violation(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["dependencies"] = ["TASK-DEMO-010"]

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("depends on itself" in item for item in payload["violations"])


def test_unknown_source_requirement_is_a_violation(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["source_requirements"] = ["REQ-GHOST-999"]

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("references unknown requirement REQ-GHOST-999" in i for i in payload["violations"])


def test_task_without_any_source_requirement_is_a_violation(
    spec_artifacts: dict, tmp_path: Path
) -> None:
    spec_artifacts["backlog"]["tasks"][0]["source_requirements"] = []

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("cannot be traced" in item for item in payload["violations"])


def test_ready_task_with_unresolved_question_is_a_violation(
    spec_artifacts: dict, unresolved_unknown: dict, tmp_path: Path
) -> None:
    spec_artifacts["requirements"]["unknowns"] = [unresolved_unknown]
    spec_artifacts["backlog"]["tasks"][0]["open_questions"] = ["UNKNOWN-014"]

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("open question UNKNOWN-014 is unresolved" in i for i in payload["violations"])


def test_ready_task_with_ambiguous_requirement_is_a_violation(
    spec_artifacts: dict, tmp_path: Path
) -> None:
    spec_artifacts["requirements"]["requirements"][0]["state"] = "AMBIGUOUS"

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("source requirement REQ-AUTH-001 is AMBIGUOUS" in i for i in payload["violations"])


def test_ready_task_without_acceptance_criteria_is_a_violation(
    spec_artifacts: dict, tmp_path: Path
) -> None:
    spec_artifacts["backlog"]["tasks"][0]["acceptance_criteria"] = []

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("has no acceptance criteria" in item for item in payload["violations"])


def test_ready_task_with_unconfirmed_project_context_is_a_violation(
    spec_artifacts: dict, tmp_path: Path
) -> None:
    spec_artifacts["project"]["status"] = "draft"
    spec_artifacts["project"]["confirmed_at"] = None

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("project context is not confirmed" in item for item in payload["violations"])


def test_ready_task_without_a_known_repository_is_a_violation(
    spec_artifacts: dict, tmp_path: Path
) -> None:
    spec_artifacts["project"]["repository"]["url"] = None
    spec_artifacts["project"]["repository"]["path"] = None

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("target repository is unknown" in item for item in payload["violations"])


def test_blocked_task_is_not_a_violation(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["readiness"] = "BLOCKED"
    spec_artifacts["backlog"]["tasks"][0]["blocked_by"] = ["REQ-APP-021"]

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 0
    assert payload["counts"]["readiness"]["BLOCKED"] == 1


def test_duplicate_task_id_is_a_violation(
    spec_artifacts: dict, make_task: Callable[..., dict], tmp_path: Path
) -> None:
    spec_artifacts["backlog"]["tasks"].append(make_task("TASK-DEMO-010"))

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("duplicate task_id: TASK-DEMO-010" in item for item in payload["violations"])


def test_task_id_must_carry_the_project_key(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["task_id"] = "TASK-OTHER-010"

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("does not start with TASK-DEMO-" in item for item in payload["violations"])


def test_project_id_disagreement_is_a_violation(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["requirements"]["project_id"] = "OTHER"

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("disagree on project_id" in item for item in payload["violations"])


def test_unknown_feature_is_a_violation(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["feature_id"] = "FEATURE-09.9"

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any("belongs to unknown feature" in item for item in payload["violations"])


def test_uncovered_requirement_is_a_warning_not_a_violation(
    spec_artifacts: dict, make_requirement: Callable[..., dict], tmp_path: Path
) -> None:
    spec_artifacts["requirements"]["requirements"].append(make_requirement("REQ-EXPORT-004"))

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 0
    assert any("REQ-EXPORT-004" in item for item in payload["warnings"])


def test_oversized_task_is_a_warning(
    spec_artifacts: dict, make_requirement: Callable[..., dict], tmp_path: Path
) -> None:
    extra = [f"REQ-BULK-{index:03d}" for index in range(1, 8)]
    spec_artifacts["requirements"]["requirements"].extend(
        make_requirement(requirement_id) for requirement_id in extra
    )
    spec_artifacts["backlog"]["tasks"][0]["source_requirements"] = extra

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 0
    assert any("may be too large" in item for item in payload["warnings"])


def test_schema_violation_is_reported(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["readiness"] = "ALMOST_READY"

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert any(item.startswith("backlog:") for item in payload["violations"])


def test_missing_artifact_is_an_error(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-context",
            str(tmp_path / "absent.json"),
            "--requirements",
            str(tmp_path / "absent.json"),
            "--backlog",
            str(tmp_path / "absent.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 1
    assert payload["error_code"] == "MISSING_ARTIFACT"


@pytest.mark.parametrize("artifact", ["project", "requirements", "backlog"])
def test_invalid_json_is_an_error(spec_artifacts: dict, tmp_path: Path, artifact: str) -> None:
    for name, payload in spec_artifacts.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / f"{artifact}.json").write_text("{not json", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-context",
            str(tmp_path / "project.json"),
            "--requirements",
            str(tmp_path / "requirements.json"),
            "--backlog",
            str(tmp_path / "backlog.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 1
    assert payload["error_code"] == "INVALID_ARTIFACT_JSON"

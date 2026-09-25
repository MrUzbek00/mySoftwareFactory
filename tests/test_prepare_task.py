"""Gate tests for the specification-intake handoff.

Every case here is decided by a local precondition. The script reads artifacts
only, so these run entirely offline and never touch a repository.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "intake" / "prepare-task" / "scripts" / "prepare_task.py"
SCHEMAS = ROOT / "schemas"


def run_script(
    payloads: dict[str, Any],
    directory: Path,
    task_id: str = "TASK-DEMO-010",
    *extra_args: str,
) -> tuple[int, dict[str, Any]]:
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
            "--task-id",
            task_id,
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_ready_task_produces_a_handoff(spec_artifacts: dict, tmp_path: Path) -> None:
    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 0
    assert payload["task_id"] == "TASK-DEMO-010"
    assert payload["readiness"] == "READY"
    assert payload["repository"]["path"] == "/workspace/demo"
    assert payload["acceptance_criteria"]


def test_handoff_validates_against_its_schema(spec_artifacts: dict, tmp_path: Path) -> None:
    from jsonschema import Draft202012Validator

    _, payload = run_script(spec_artifacts, tmp_path)
    schema = json.loads((SCHEMAS / "task-handoff.schema.json").read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(payload)


def test_handoff_carries_source_traceability(spec_artifacts: dict, tmp_path: Path) -> None:
    _, payload = run_script(spec_artifacts, tmp_path)
    source = payload["source_requirements"][0]

    assert source["requirement_id"] == "REQ-AUTH-001"
    assert source["sources"][0]["section"] == "4.2"
    assert source["sources"][0]["page"] == "10-11"
    assert payload["source_specifications"][0]["location"] == "docs/demo-requirements.docx"


def test_handoff_carries_project_constraints(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["project"]["architecture_constraints"] = ["Server-rendered views; no SPA."]

    _, payload = run_script(spec_artifacts, tmp_path)

    assert "Mandatory stack: Laravel 11" in payload["constraints"]
    assert "Server-rendered views; no SPA." in payload["constraints"]


def test_handoff_does_not_decide_risk_or_approval(spec_artifacts: dict, tmp_path: Path) -> None:
    _, payload = run_script(spec_artifacts, tmp_path)

    assert payload["risk_level"] is None
    assert "requires_human_approval" not in payload


def test_handoff_fields_match_the_downstream_inputs(spec_artifacts: dict, tmp_path: Path) -> None:
    _, payload = run_script(spec_artifacts, tmp_path)

    assert {"task_id", "task_title", "task_description", "optional_target_paths"} <= set(payload)
    assert {"acceptance_criteria", "constraints"} <= set(payload)
    assert payload["task_type"] in ("feature", "fix", "refactor", "chore", "docs", "test")
    assert payload["task_slug"]


def test_backlog_ref_also_resolves_a_task(spec_artifacts: dict, tmp_path: Path) -> None:
    return_code, payload = run_script(spec_artifacts, tmp_path, "DEMO-010")

    assert return_code == 0
    assert payload["task_id"] == "TASK-DEMO-010"


def test_out_file_is_written(spec_artifacts: dict, tmp_path: Path) -> None:
    out = tmp_path / "tasks" / "TASK-DEMO-010" / "task-handoff.json"

    return_code, _ = run_script(spec_artifacts, tmp_path, "TASK-DEMO-010", "--out", str(out))

    assert return_code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["task_id"] == "TASK-DEMO-010"


def test_unconfirmed_project_context_is_refused(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["project"]["status"] = "draft"

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "PROJECT_NOT_CONFIRMED"


def test_unapproved_backlog_is_refused(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["status"] = "draft"

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "BACKLOG_NOT_APPROVED"


def test_unknown_repository_is_refused(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["project"]["repository"]["url"] = None
    spec_artifacts["project"]["repository"]["path"] = None

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "REPOSITORY_UNKNOWN"


def test_unknown_task_is_refused(spec_artifacts: dict, tmp_path: Path) -> None:
    return_code, payload = run_script(spec_artifacts, tmp_path, "TASK-DEMO-999")

    assert return_code == 1
    assert payload["error_code"] == "UNKNOWN_TASK"


@pytest.mark.parametrize("readiness", ["DRAFT", "NEEDS_CLARIFICATION", "BLOCKED", "IN_PROGRESS"])
def test_task_that_is_not_ready_is_refused(
    spec_artifacts: dict, tmp_path: Path, readiness: str
) -> None:
    spec_artifacts["backlog"]["tasks"][0]["readiness"] = readiness

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "TASK_NOT_READY"


def test_blocked_task_names_its_blocker_in_the_refusal(
    spec_artifacts: dict, tmp_path: Path
) -> None:
    spec_artifacts["backlog"]["tasks"][0]["readiness"] = "BLOCKED"
    spec_artifacts["backlog"]["tasks"][0]["blocked_by"] = ["UNKNOWN-014"]

    _, payload = run_script(spec_artifacts, tmp_path)

    assert "UNKNOWN-014" in payload["message"]


def test_ready_task_without_acceptance_criteria_is_refused(
    spec_artifacts: dict, tmp_path: Path
) -> None:
    spec_artifacts["backlog"]["tasks"][0]["acceptance_criteria"] = []

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "TASK_NOT_READY"


def test_ready_task_that_is_still_blocked_is_refused(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["blocked_by"] = ["CONFLICT-003"]

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "TASK_NOT_READY"


def test_unresolved_open_question_is_refused(
    spec_artifacts: dict, unresolved_unknown: dict, tmp_path: Path
) -> None:
    spec_artifacts["requirements"]["unknowns"] = [unresolved_unknown]
    spec_artifacts["backlog"]["tasks"][0]["open_questions"] = ["UNKNOWN-014"]

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "TASK_HAS_OPEN_QUESTIONS"


def test_open_conflict_is_refused(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["requirements"]["conflicts"] = [
        {
            "conflict_id": "CONFLICT-003",
            "requirement_a": "REQ-AUTH-001",
            "requirement_b": "REQ-APP-021",
            "reason": "Two sections assign the same transition to different roles.",
            "decision_required": "Which role may close a record?",
            "status": "OPEN",
            "resolved_by": None,
        }
    ]
    spec_artifacts["backlog"]["tasks"][0]["open_questions"] = ["CONFLICT-003"]

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "TASK_HAS_OPEN_QUESTIONS"


def test_answered_question_no_longer_blocks(
    spec_artifacts: dict, unresolved_unknown: dict, tmp_path: Path
) -> None:
    unresolved_unknown["status"] = "ANSWERED"
    unresolved_unknown["resolved_by"] = "DEC-004"
    spec_artifacts["requirements"]["unknowns"] = [unresolved_unknown]
    spec_artifacts["backlog"]["tasks"][0]["open_questions"] = ["UNKNOWN-014"]

    return_code, _ = run_script(spec_artifacts, tmp_path)

    assert return_code == 0


@pytest.mark.parametrize("state", ["AMBIGUOUS", "BLOCKED", "OUT_OF_SCOPE"])
def test_unimplementable_requirement_is_refused(
    spec_artifacts: dict, tmp_path: Path, state: str
) -> None:
    spec_artifacts["requirements"]["requirements"][0]["state"] = state

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "REQUIREMENT_NOT_CONFIRMED"


def test_missing_requirement_is_refused(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["source_requirements"] = ["REQ-GHOST-999"]

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "REQUIREMENT_NOT_CONFIRMED"


def test_untraceable_task_is_refused(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["source_requirements"] = []

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "REQUIREMENT_NOT_CONFIRMED"


def test_dependency_that_is_not_done_is_refused(spec_artifacts: dict, tmp_path: Path) -> None:
    return_code, payload = run_script(spec_artifacts, tmp_path, "TASK-DEMO-011")

    assert return_code == 1
    assert payload["error_code"] == "DEPENDENCY_NOT_DONE"
    assert "TASK-DEMO-010" in payload["message"]


def test_done_dependency_is_accepted(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["readiness"] = "DONE"

    return_code, payload = run_script(spec_artifacts, tmp_path, "TASK-DEMO-011")

    assert return_code == 0
    assert payload["open_dependencies"] == []


def test_open_dependency_override_is_recorded(spec_artifacts: dict, tmp_path: Path) -> None:
    return_code, payload = run_script(
        spec_artifacts, tmp_path, "TASK-DEMO-011", "--allow-open-dependencies"
    )

    assert return_code == 0
    assert payload["open_dependencies"] == ["TASK-DEMO-010"]


def test_unknown_dependency_is_refused(spec_artifacts: dict, tmp_path: Path) -> None:
    spec_artifacts["backlog"]["tasks"][0]["dependencies"] = ["TASK-DEMO-404"]

    return_code, payload = run_script(spec_artifacts, tmp_path)

    assert return_code == 1
    assert payload["error_code"] == "UNKNOWN_DEPENDENCY"


def test_script_never_touches_a_repository() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "subprocess" not in source
    assert "git " not in source
    assert "--force" not in source

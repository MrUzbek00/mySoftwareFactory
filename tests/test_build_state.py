"""The map must report what the files say, and nothing else.

Every test here changes one file or one field and asserts the one status that
should change with it. A test that passed because a status was hardcoded would
fail here, because the same node is asserted in more than one state.
"""

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "factory-map" / "scripts" / "build_state.py"
STATE_SCHEMA = ROOT / "my-software-factory" / "schemas" / "factory-map-state.schema.json"


def load_module():
    """Import the script by path, the way the factory runs it."""
    spec = importlib.util.spec_from_file_location("build_state", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_state_module = load_module()


def state_for(factory: Path | None, task: str | None = None) -> dict[str, Any]:
    return build_state_module.build_state(ROOT, factory or (ROOT / ".factory"), task)


def node(state: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(item for item in state["nodes"] if item["id"] == node_id)


def gate(state: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(item for item in state["gates"] if item["id"] == gate_id)


def test_repository_mode_describes_every_stage_without_a_factory(tmp_path: Path) -> None:
    state = state_for(tmp_path / "absent")

    assert state["mode"] == "repo"
    assert state["factory"]["present"] is False
    assert len(state["nodes"]) == 17
    assert [lane["header"] for lane in state["lanes"]] == [
        "SPEC INTAKE",
        "UNDERSTAND",
        "BUILD",
        "VERIFY",
        "PUBLISH",
    ]
    assert all(item["status"] == "pending" for item in state["gates"])


def test_emitted_state_satisfies_its_own_schema(tmp_path: Path, factory_run: Callable) -> None:
    schema = json.loads(STATE_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    for factory in (tmp_path / "absent", factory_run()):
        Draft202012Validator(schema).validate(state_for(factory))


def test_build_status_comes_from_the_files_each_stage_has(tmp_path: Path) -> None:
    state = state_for(tmp_path / "absent")

    validate = node(state, "validate-change")
    assert validate["build"]["script"] == (
        "my-software-factory/stages/engineering/validate-change/scripts/run_validation.py"
    )
    assert validate["build"]["schema"] == (
        "my-software-factory/schemas/validation-report.schema.json"
    )
    assert "tests/test_run_validation.py" in validate["build"]["tests"]
    assert validate["build"]["status"] == "built"

    # A stage whose script no test exercises is reported partial, not built.
    review = node(state, "review-pull-request")
    assert review["build"]["status"] == "partial"
    assert review["build"]["missing"] == ["a test exercising fetch_pull_request.py"]


def test_chips_are_derived_rather_than_assigned(tmp_path: Path) -> None:
    state = state_for(tmp_path / "absent")

    assert "SCRIPT" in node(state, "isolate-task")["chips"]
    assert "MODEL" in node(state, "implement-change")["chips"]
    assert "GATE" in node(state, "validate-change")["chips"]
    assert "OPTIONAL" in node(state, "before-after")["chips"]
    assert "READ-ONLY" in node(state, "review-pull-request")["chips"]
    assert "READ-ONLY" not in node(state, "create-pull-request")["chips"]


def test_a_full_run_passes_every_stage_it_has_an_artifact_for(factory_run: Callable) -> None:
    state = state_for(factory_run())

    assert state["mode"] == "run"
    assert state["selected_task"] == "TASK-DEMO-010"
    for stage_id in (
        "clarify-project",
        "decompose-spec",
        "prepare-task",
        "inspect-repository",
        "plan-change",
        "isolate-task",
        "implement-change",
        "validate-change",
        "security-review",
    ):
        assert node(state, stage_id)["run"]["status"] == "passed", stage_id

    assert gate(state, "context-confirmed")["status"] == "passed"
    assert gate(state, "backlog-approved")["status"] == "passed"
    assert gate(state, "ready")["status"] == "passed"
    assert gate(state, "validation-passed")["status"] == "passed"
    assert gate(state, "no-critical")["status"] == "passed"


def test_the_human_merge_gate_never_passes(factory_run: Callable) -> None:
    state = state_for(factory_run())

    assert gate(state, "human-merge")["status"] == "pending"
    assert gate(state, "human-merge")["expected"] is None


def test_an_unconfirmed_project_blocks_the_context_gate(
    factory_run: Callable, spec_artifacts: dict
) -> None:
    factory = factory_run()
    draft = spec_artifacts["project"]
    draft["status"] = "draft"
    (factory / "project.json").write_text(json.dumps(draft), encoding="utf-8")

    state = state_for(factory)

    assert node(state, "clarify-project")["run"]["status"] == "blocked"
    assert gate(state, "context-confirmed")["status"] == "blocked"
    assert gate(state, "context-confirmed")["observed"] == "draft"


def test_failed_validation_blocks_the_node_and_the_gate(
    factory_run: Callable, make_validation_report: Callable
) -> None:
    report = make_validation_report(
        "TASK-DEMO-010", status="fail", ready_for_pull_request=False
    )
    state = state_for(factory_run(overrides={"validation.json": report}))

    assert node(state, "validate-change")["run"]["status"] == "blocked"
    assert gate(state, "validation-passed")["status"] == "blocked"


def test_a_blocking_quality_finding_blocks_validation_even_when_status_says_pass(
    factory_run: Callable, make_validation_report: Callable
) -> None:
    report = make_validation_report("TASK-DEMO-010")
    report["code_quality"] = {
        "status": "findings",
        "reviewed_files": ["app/Services/ContractService.php"],
        "skipped_files": [],
        "findings": [
            {
                "criterion": "return-types",
                "severity": "BLOCKING",
                "file": "app/Services/ContractService.php",
                "detail": "No declared return type.",
            }
        ],
        "counts": {"BLOCKING": 1, "ADVISORY": 0},
    }
    state = state_for(factory_run(overrides={"validation.json": report}))

    assert node(state, "validate-change")["run"]["status"] == "blocked"
    assert state["views"]["standards"]["counts"]["BLOCKING"] == 1
    assert state["views"]["standards"]["source"] == "validation.json:code_quality"


def test_a_critical_security_finding_blocks_publication(
    factory_run: Callable, make_security_review: Callable
) -> None:
    review = make_security_review(
        "TASK-DEMO-010",
        status="findings",
        counts={"CRITICAL": 1, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
        requires_human_review=True,
    )
    state = state_for(factory_run(overrides={"security.json": review}))

    assert node(state, "security-review")["run"]["status"] == "blocked"
    assert gate(state, "no-critical")["status"] == "blocked"
    assert gate(state, "no-critical")["observed"] == 1


def test_a_high_risk_plan_without_a_recorded_approval_is_blocked(
    factory_run: Callable, make_change_plan: Callable
) -> None:
    plan = make_change_plan(
        "TASK-DEMO-010", risk_level="HIGH", requires_human_approval=True, approval_reason=None
    )
    state = state_for(factory_run(overrides={"plan.json": plan}))

    assert node(state, "plan-change")["run"]["status"] == "blocked"
    assert gate(state, "plan-approved")["status"] == "blocked"

    plan["approval_reason"] = "Approved by the repository owner."
    state = state_for(factory_run(overrides={"plan.json": plan}))

    assert node(state, "plan-change")["run"]["status"] == "passed"
    assert gate(state, "plan-approved")["status"] == "passed"


def test_a_malformed_artifact_is_invalid_rather_than_passing(factory_run: Callable) -> None:
    state = state_for(factory_run(overrides={"validation.json": "{not json"}))

    assert node(state, "validate-change")["run"]["status"] == "invalid"
    assert node(state, "validate-change")["run"]["artifact"]["valid"] is False
    assert gate(state, "validation-passed")["status"] == "blocked"


def test_an_artifact_that_does_not_satisfy_its_schema_is_invalid(
    factory_run: Callable, make_validation_report: Callable
) -> None:
    report = make_validation_report("TASK-DEMO-010")
    del report["checks"]
    state = state_for(factory_run(overrides={"validation.json": report}))

    assert node(state, "validate-change")["run"]["status"] == "invalid"


def test_presence_alone_does_not_pass_a_stage(
    factory_run: Callable, make_security_review: Callable
) -> None:
    """The same file present twice, with one field changed, gives two verdicts."""
    clean = state_for(factory_run())
    critical = state_for(
        factory_run(
            overrides={
                "security.json": make_security_review(
                    "TASK-DEMO-010",
                    status="findings",
                    counts={"CRITICAL": 2, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
                    requires_human_review=True,
                )
            }
        )
    )

    assert node(clean, "security-review")["run"]["artifact"]["present"] is True
    assert node(critical, "security-review")["run"]["artifact"]["present"] is True
    assert node(clean, "security-review")["run"]["status"] == "passed"
    assert node(critical, "security-review")["run"]["status"] == "blocked"


def test_the_active_stage_is_the_first_one_with_no_artifact(factory_run: Callable) -> None:
    factory = factory_run(stages=("task-handoff.json", "context.json", "plan.json"))
    state = state_for(factory)

    assert node(state, "plan-change")["run"]["status"] == "passed"
    assert node(state, "isolate-task")["run"]["status"] == "active"
    assert node(state, "implement-change")["run"]["status"] == "pending"


def test_an_optional_stage_the_run_went_past_is_skipped(factory_run: Callable) -> None:
    state = state_for(factory_run())

    assert node(state, "before-after")["run"]["status"] == "skipped"
    assert node(state, "before-after")["optional"] is True


def test_a_scoped_ticket_run_marks_the_intake_lane_not_applicable(factory_run: Callable) -> None:
    state = state_for(factory_run(intake=False))

    assert state["factory"]["intake_applies"] is False
    for stage_id in ("start-from-spec", "clarify-project", "decompose-spec"):
        assert node(state, stage_id)["run"]["status"] == "not_applicable"
    assert node(state, "inspect-repository")["run"]["status"] == "passed"


def test_every_status_names_the_file_and_field_it_came_from(factory_run: Callable) -> None:
    state = state_for(factory_run())

    validation = node(state, "validate-change")["run"]
    fields = {mark["field"] for mark in validation["evidence"]}
    assert "status" in fields
    assert "code_quality.counts.BLOCKING" in fields
    assert all(mark["file"] == "validation.json" for mark in validation["evidence"])

    assert gate(state, "no-critical")["source_file"] == "security.json:counts.CRITICAL"


def test_more_than_one_task_is_selectable(factory_run: Callable) -> None:
    factory = factory_run()
    (factory / "tasks" / "TASK-DEMO-011").mkdir(parents=True, exist_ok=True)

    state = state_for(factory)
    assert state["tasks"] == ["TASK-DEMO-010", "TASK-DEMO-011"]

    other = state_for(factory, "TASK-DEMO-011")
    assert other["selected_task"] == "TASK-DEMO-011"
    assert node(other, "validate-change")["run"]["status"] == "pending"


def index_entry(state: dict[str, Any], task_id: str) -> dict[str, Any]:
    return next(item for item in state["task_index"] if item["task_id"] == task_id)


def test_the_task_index_lists_planned_backlog_tasks_as_not_done(factory_run: Callable) -> None:
    state = state_for(factory_run())

    # TASK-DEMO-011 is in the backlog but no run has started it.
    assert state["tasks"] == ["TASK-DEMO-010"]
    assert [item["task_id"] for item in state["task_index"]] == ["TASK-DEMO-010", "TASK-DEMO-011"]
    planned = index_entry(state, "TASK-DEMO-011")
    assert planned["done"] is False
    assert planned["title"] == "Do the thing"
    assert planned["evidence"] == {
        "file": "completion-report.json",
        "field": None,
        "value": "absent",
    }

    # A planned task can be selected; it has nothing on disk, so every stage is pending.
    chosen = state_for(factory_run(), "TASK-DEMO-011")
    assert chosen["selected_task"] == "TASK-DEMO-011"
    assert node(chosen, "inspect-repository")["run"]["status"] == "pending"


def test_a_task_is_done_only_when_its_completion_report_says_complete(
    factory_run: Callable,
) -> None:
    complete = {"status": "complete", "inconsistencies": []}
    done = state_for(factory_run(overrides={"completion-report.json": complete}))
    assert index_entry(done, "TASK-DEMO-010")["done"] is True
    assert index_entry(done, "TASK-DEMO-010")["evidence"]["value"] == "complete"
    assert index_entry(done, "TASK-DEMO-011")["done"] is False

    incomplete = {"status": "incomplete", "inconsistencies": []}
    state = state_for(factory_run(overrides={"completion-report.json": incomplete}))
    assert index_entry(state, "TASK-DEMO-010")["done"] is False

    contradicted = {"status": "complete", "inconsistencies": ["validation says fail"]}
    state = state_for(factory_run(overrides={"completion-report.json": contradicted}))
    assert index_entry(state, "TASK-DEMO-010")["done"] is False

    # The name the completion-report node reads counts too.
    state = state_for(factory_run(overrides={"completion.json": complete}))
    assert index_entry(state, "TASK-DEMO-010")["done"] is True
    assert index_entry(state, "TASK-DEMO-010")["evidence"]["file"] == "completion.json"


def test_a_run_without_a_backlog_indexes_its_task_directories(factory_run: Callable) -> None:
    state = state_for(factory_run(intake=False))

    assert state["task_index"] == [
        {
            "task_id": "TASK-DEMO-010",
            "title": None,
            "done": False,
            "evidence": {"file": "completion-report.json", "field": None, "value": "absent"},
        }
    ]


def test_the_fingerprint_changes_when_an_artifact_changes(
    factory_run: Callable, make_security_review: Callable
) -> None:
    before = state_for(factory_run())
    after = state_for(
        factory_run(
            overrides={
                "security.json": make_security_review(
                    "TASK-DEMO-010",
                    status="findings",
                    counts={"CRITICAL": 1, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
                    requires_human_review=True,
                )
            }
        )
    )

    assert before["fingerprint"] != after["fingerprint"]


def test_the_artifact_view_says_which_names_the_repository_documents(
    factory_run: Callable,
) -> None:
    state = state_for(factory_run())
    by_file = {row["file"]: row for row in state["views"]["artifacts"]}

    assert by_file["validation.json"]["named_by"] == "repository"
    assert by_file["review.json"]["named_by"] == "factory-map"


def test_the_scripts_view_takes_its_wording_from_the_architecture_document(
    tmp_path: Path,
) -> None:
    state = state_for(tmp_path / "absent")
    rows = {row["script"]: row for row in state["views"]["scripts"]}

    assert len(rows) == 10
    isolate = "my-software-factory/stages/engineering/isolate-task/scripts/create_worktree.py"
    assert rows[isolate]["enforces"] == "safe branch naming, clean tree, no overwrite"


def test_an_unplaced_skill_directory_is_reported_rather_than_dropped(tmp_path: Path) -> None:
    state = state_for(tmp_path / "absent")
    assert state["warnings"] == []
    assert set(build_state_module.STAGE_IDS) == {
        path.parent.name for path in ROOT.glob(build_state_module.SKILL_GLOB)
    }

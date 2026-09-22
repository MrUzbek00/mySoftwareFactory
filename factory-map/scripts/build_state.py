"""Scan the repository and any run state, and emit the pipeline map as JSON.

The map has two independent state sources. Repository mode describes how
completely each stage is built, and is derived by looking at the files on disk.
Run mode describes where a task has actually got to, and is derived from the
artifacts under the factory directory and from the status fields inside them.

Nothing here decides a status by assumption. Every status this script emits
carries the file and the field it came from, so a reader can check it. The
pipeline topology - lanes, edges, and where the gates sit - is structural
knowledge taken from AGENTS.md and README.md, and is the only thing declared
rather than discovered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_REFERENCE = re.compile(r"schemas/([a-z0-9-]+)\.schema\.json")
OUTPUT_CONTRACT = re.compile(r"^## Output Contract$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
PURPOSE = re.compile(r"^## Purpose$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
FAILURE_CONDITIONS = re.compile(
    r"^## Failure Conditions$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
)
ESCALATION_CONDITIONS = re.compile(
    r"^## Escalation Conditions$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
)
BULLET = re.compile(r"^[-*]\s+(.*)$", re.MULTILINE)

LANES: tuple[dict[str, Any], ...] = (
    {
        "index": 0,
        "key": "intake",
        "header": "SPEC INTAKE",
        "color": "#8b7cf6",
        "conditional": True,
        "condition_label": "RUNS ONLY FOR A SPECIFICATION",
    },
    {
        "index": 1,
        "key": "understand",
        "header": "UNDERSTAND",
        "color": "#f0b429",
        "conditional": False,
        "condition_label": None,
    },
    {
        "index": 2,
        "key": "build",
        "header": "BUILD",
        "color": "#f59e0b",
        "conditional": False,
        "condition_label": None,
    },
    {
        "index": 3,
        "key": "verify",
        "header": "VERIFY",
        "color": "#ff4d6d",
        "conditional": False,
        "condition_label": None,
    },
    {
        "index": 4,
        "key": "publish",
        "header": "PUBLISH",
        "color": "#2dd4bf",
        "conditional": False,
        "condition_label": None,
    },
)

# One entry per pipeline stage, in pipeline order.
#
# `artifact` is the filename this map looks for. Where `artifact_source` is
# "repository" the name is documented: project.json, requirements.json and
# backlog.json by start-from-spec/SKILL.md, task-handoff.json by
# prepare-task/SKILL.md, and the nine stage artifacts by
# completion-report/references/audit-trail.md. Where it is "factory-map" the
# repository documents no filename for that stage and this map chose one.
STAGES: tuple[dict[str, Any], ...] = (
    {
        "id": "start-from-spec",
        "lane": 0,
        "scope": "project",
        "artifact": None,
        "artifact_source": None,
        "optional": False,
        "read_only": False,
    },
    {
        "id": "ingest-requirements",
        "lane": 0,
        "scope": "project",
        "artifact": "requirements.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "clarify-project",
        "lane": 0,
        "scope": "project",
        "artifact": "project.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "decompose-spec",
        "lane": 0,
        "scope": "project",
        "artifact": "backlog.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "prepare-task",
        "lane": 0,
        "scope": "task",
        "artifact": "task-handoff.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "inspect-repository",
        "lane": 1,
        "scope": "task",
        "artifact": "context.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "plan-change",
        "lane": 1,
        "scope": "task",
        "artifact": "plan.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "isolate-task",
        "lane": 2,
        "scope": "task",
        "artifact": "workspace.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "implement-change",
        "lane": 2,
        "scope": "task",
        "artifact": "implementation.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "validate-change",
        "lane": 3,
        "scope": "task",
        "artifact": "validation.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "before-after",
        "lane": 3,
        "scope": "task",
        "artifact": "before-after.json",
        "artifact_source": "repository",
        "optional": True,
        "read_only": False,
    },
    {
        "id": "security-review",
        "lane": 3,
        "scope": "task",
        "artifact": "security.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "update-documentation",
        "lane": 3,
        "scope": "task",
        "artifact": "documentation.json",
        "artifact_source": "repository",
        "optional": True,
        "read_only": False,
    },
    {
        "id": "create-pull-request",
        "lane": 4,
        "scope": "task",
        "artifact": "pull-request.json",
        "artifact_source": "repository",
        "optional": False,
        "read_only": False,
    },
    {
        "id": "review-pull-request",
        "lane": 4,
        "scope": "task",
        "artifact": "review.json",
        "artifact_source": "factory-map",
        "optional": True,
        "read_only": True,
    },
    {
        "id": "revise-pull-request",
        "lane": 4,
        "scope": "task",
        "artifact": "revision.json",
        "artifact_source": "factory-map",
        "optional": True,
        "read_only": False,
    },
    {
        "id": "completion-report",
        "lane": 4,
        "scope": "task",
        "artifact": "completion.json",
        "artifact_source": "factory-map",
        "optional": False,
        "read_only": False,
    },
)

STAGE_IDS: tuple[str, ...] = tuple(stage["id"] for stage in STAGES)

LOOP_CAPTION = (
    "THE LOOP - FEEDBACK · FAST-FORWARD COMMITS · REVALIDATE · NEVER REWRITE"
)

EDGES: tuple[dict[str, Any], ...] = (
    {"source": None, "target": "start-from-spec", "kind": "entry", "gate": None,
     "label": "SPECIFICATION"},
    {"source": "start-from-spec", "target": "ingest-requirements", "kind": "normal", "gate": None,
     "label": None},
    {"source": "ingest-requirements", "target": "clarify-project", "kind": "normal", "gate": None,
     "label": None},
    {"source": "clarify-project", "target": "decompose-spec", "kind": "normal",
     "gate": "context-confirmed", "label": None},
    {"source": "decompose-spec", "target": "prepare-task", "kind": "normal",
     "gate": "backlog-approved", "label": None},
    {"source": "prepare-task", "target": "inspect-repository", "kind": "normal", "gate": "ready",
     "label": None},
    {"source": None, "target": "inspect-repository", "kind": "entry", "gate": None,
     "label": "SCOPED TICKET"},
    {"source": "inspect-repository", "target": "plan-change", "kind": "normal", "gate": None,
     "label": None},
    {"source": "plan-change", "target": "isolate-task", "kind": "normal", "gate": "plan-approved",
     "label": None},
    {"source": "isolate-task", "target": "implement-change", "kind": "normal", "gate": None,
     "label": None},
    {"source": "implement-change", "target": "validate-change", "kind": "normal", "gate": None,
     "label": None},
    {"source": "validate-change", "target": "before-after", "kind": "normal", "gate": None,
     "label": None},
    {"source": "validate-change", "target": "security-review", "kind": "normal", "gate": None,
     "label": None},
    {"source": "validate-change", "target": "update-documentation", "kind": "normal",
     "gate": None, "label": None},
    {"source": "validate-change", "target": "create-pull-request", "kind": "normal",
     "gate": "validation-passed", "label": None},
    {"source": "before-after", "target": "create-pull-request", "kind": "evidence", "gate": None,
     "label": None},
    {"source": "security-review", "target": "create-pull-request", "kind": "normal",
     "gate": "no-critical", "label": None},
    {"source": "update-documentation", "target": "create-pull-request", "kind": "evidence",
     "gate": None, "label": None},
    {"source": "create-pull-request", "target": "review-pull-request", "kind": "normal",
     "gate": None, "label": None},
    {"source": "review-pull-request", "target": "revise-pull-request", "kind": "normal",
     "gate": None, "label": None},
    {"source": "revise-pull-request", "target": "validate-change", "kind": "loop", "gate": None,
     "label": LOOP_CAPTION},
    {"source": "create-pull-request", "target": "completion-report", "kind": "normal",
     "gate": None, "label": None},
    {"source": "completion-report", "target": "STOP", "kind": "terminal", "gate": "human-merge",
     "label": None},
)

GATES: tuple[dict[str, Any], ...] = (
    {
        "id": "context-confirmed",
        "label": "CONTEXT CONFIRMED",
        "source": "clarify-project",
        "target": "decompose-spec",
        "passes_when": "the user confirms the project intake summary",
        "artifact": "project.json",
        "field": "status",
        "expected": "confirmed",
    },
    {
        "id": "backlog-approved",
        "label": "BACKLOG APPROVED",
        "source": "decompose-spec",
        "target": "prepare-task",
        "passes_when": "the backlog status is approved",
        "artifact": "backlog.json",
        "field": "status",
        "expected": "approved",
    },
    {
        "id": "ready",
        "label": "READY",
        "source": "prepare-task",
        "target": "inspect-repository",
        "passes_when": "exactly one task, readiness READY",
        "artifact": "task-handoff.json",
        "field": "readiness",
        "expected": "READY",
    },
    {
        "id": "plan-approved",
        "label": "PLAN APPROVED",
        "source": "plan-change",
        "target": "isolate-task",
        "passes_when": "approval is recorded when risk_level is HIGH or CRITICAL",
        "artifact": "plan.json",
        "field": "ready_for_isolation",
        "expected": True,
    },
    {
        "id": "validation-passed",
        "label": "VALIDATION PASSED",
        "source": "validate-change",
        "target": "create-pull-request",
        "passes_when": "status is pass and no BLOCKING quality finding stands",
        "artifact": "validation.json",
        "field": "status",
        "expected": "pass",
    },
    {
        "id": "no-critical",
        "label": "NO CRITICAL",
        "source": "security-review",
        "target": "create-pull-request",
        "passes_when": "zero CRITICAL findings",
        "artifact": "security.json",
        "field": "counts.CRITICAL",
        "expected": 0,
    },
    {
        "id": "human-merge",
        "label": "HUMAN MERGE",
        "source": "completion-report",
        "target": "STOP",
        "passes_when": "never automatically; a human owns the merge",
        "artifact": None,
        "field": None,
        "expected": None,
    },
)

OUT_OF_SCOPE: tuple[dict[str, str], ...] = (
    {"item": "merging or approving a pull request", "state": "deliberately unimplemented"},
    {"item": "enabling auto-merge or dismissing reviews", "state": "deliberately unimplemented"},
    {"item": "deploying, releasing, or touching production", "state": "deliberately unimplemented"},
    {
        "item": "modifying branch protection or repository settings",
        "state": "deliberately unimplemented",
    },
)


class ScriptError(Exception):
    """Structured error that can be returned as JSON."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def utc_now() -> str:
    """Current time as a timezone-aware ISO 8601 string ending in Z."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_from_timestamp(timestamp: float) -> str:
    """Convert a filesystem modification time to the same ISO 8601 form."""
    return datetime.fromtimestamp(timestamp, UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def resolve_directory(path_arg: str, error_code: str) -> Path:
    resolved = Path(path_arg).expanduser().resolve()
    if not resolved.is_dir():
        raise ScriptError(error_code, f"Not a directory: {resolved}")
    return resolved


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Return the parsed object, or None with the reason it could not be read."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, f"unreadable: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "top level is not a JSON object"
    return payload, None


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Parse the YAML frontmatter of a SKILL.md, or None when it does not parse.

    Deliberately the same shape of parse that tests/test_skill_metadata.py uses:
    a leading delimiter, key: value lines, and a closing delimiter.
    """
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        closing = lines[1:].index("---") + 1
    except ValueError:
        return None

    metadata: dict[str, str] = {}
    for line in lines[1:closing]:
        key, separator, value = line.partition(":")
        if separator != ":":
            return None
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def section_text(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def section_bullets(pattern: re.Pattern[str], text: str) -> list[str]:
    return [item.strip() for item in BULLET.findall(section_text(pattern, text))]


def first_paragraph(text: str) -> str:
    for block in text.split("\n\n"):
        cleaned = " ".join(line.strip() for line in block.strip().splitlines() if line.strip())
        if cleaned and not cleaned.startswith(("-", "*", "|", "```")):
            return cleaned
    return ""


def dotted(payload: dict[str, Any], field: str) -> tuple[Any, bool]:
    """Read a dotted field path. Returns the value and whether it was present."""
    current: Any = payload
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]
    return current, True


RESOLVED_UNKNOWN_STATES = ("ANSWERED", "DEFERRED")
RESOLVED_CONFLICT_STATES = ("RESOLVED",)

# How each stage's artifact decides its run status. The field names here are
# the ones the schemas actually declare; see factory-map/README.md.
RUN_RULES: dict[str, dict[str, Any]] = {
    "ingest-requirements": {"kind": "requirements"},
    "clarify-project": {"kind": "status", "passed": ("confirmed",), "blocked": ("draft",)},
    "decompose-spec": {"kind": "status", "passed": ("approved",), "blocked": ("draft",)},
    "prepare-task": {"kind": "present"},
    "inspect-repository": {"kind": "present"},
    "plan-change": {"kind": "plan"},
    "isolate-task": {"kind": "status", "passed": ("created",), "blocked": ()},
    "implement-change": {"kind": "status", "passed": ("implemented",), "blocked": ("blocked",)},
    "validate-change": {"kind": "validation"},
    "before-after": {"kind": "status", "passed": ("captured",), "blocked": ("partial",)},
    "security-review": {"kind": "security"},
    "update-documentation": {
        "kind": "status",
        "passed": ("updated", "no_change_required"),
        "blocked": ("blocked",),
    },
    "create-pull-request": {"kind": "status", "passed": ("created",), "blocked": ()},
    "review-pull-request": {"kind": "status", "passed": ("reviewed",), "blocked": ()},
    "revise-pull-request": {"kind": "status", "passed": ("revised",), "blocked": ("blocked",)},
    "completion-report": {"kind": "completion"},
}

COMPLETE_STATES = ("passed", "skipped", "not_applicable")


def validate_payload(payload: dict[str, Any], schema_path: Path) -> tuple[bool, list[str]]:
    """Validate an artifact against its schema.

    jsonschema is a development dependency, not a runtime one, so this falls
    back to a required-key check when it is not installed - the same
    compromise completion-report/scripts/build_report.py makes.
    """
    schema, reason = read_json(schema_path)
    if schema is None:
        return False, [f"schema unreadable: {reason}"]

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        missing = [key for key in schema.get("required", []) if key not in payload]
        if missing:
            return False, [f"missing required key: {key}" for key in missing]
        return True, ["jsonschema not installed; only required keys were checked"]

    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.path))
    if not errors:
        return True, []
    return False, [f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
                   for error in errors[:5]]


def scan_skill(repo: Path, stage: dict[str, Any]) -> dict[str, Any]:
    """Collect everything the repository says about one stage."""
    directory = repo / stage["id"]
    skill_path = directory / "SKILL.md"
    detail: dict[str, Any] = {
        "id": stage["id"],
        "directory": stage["id"],
        "skill_present": skill_path.is_file(),
        "frontmatter_valid": False,
        "name_matches_directory": False,
        "description": "",
        "purpose": "",
        "failure_conditions": [],
        "escalation_conditions": [],
        "references": [],
        "scripts": [],
        "schemas": [],
        "own_schema": None,
        "tests": [],
    }
    if not detail["skill_present"]:
        return detail

    text = skill_path.read_text(encoding="utf-8")
    metadata = parse_frontmatter(text)
    if metadata is not None:
        detail["frontmatter_valid"] = True
        detail["name_matches_directory"] = metadata.get("name") == stage["id"]
        detail["description"] = metadata.get("description", "")

    detail["purpose"] = first_paragraph(section_text(PURPOSE, text))
    detail["failure_conditions"] = section_bullets(FAILURE_CONDITIONS, text)
    detail["escalation_conditions"] = section_bullets(ESCALATION_CONDITIONS, text)
    detail["references"] = sorted(
        path.relative_to(repo).as_posix() for path in directory.glob("references/*.md")
    )
    detail["scripts"] = sorted(
        path.relative_to(repo).as_posix() for path in directory.glob("scripts/*.py")
    )

    contract_schemas = sorted(set(SCHEMA_REFERENCE.findall(section_text(OUTPUT_CONTRACT, text))))
    detail["schemas"] = [f"schemas/{name}.schema.json" for name in contract_schemas]
    if len(contract_schemas) == 1:
        detail["own_schema"] = detail["schemas"][0]
    return detail


def scan_tests(repo: Path) -> dict[str, list[str]]:
    """Map a script filename to the test modules that exercise it.

    tests/test_repository_structure.py is excluded deliberately. It lists every
    script path to assert the file exists, which is not the same as running it,
    and counting it would report coverage this repository does not have.
    """
    coverage: dict[str, list[str]] = {}
    for test_path in sorted((repo / "tests").glob("test_*.py")):
        if test_path.name == "test_repository_structure.py":
            continue
        try:
            text = test_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for script_name in sorted(set(re.findall(r"[a-z_]+\.py", text))):
            if not references_script_path(text, script_name):
                continue
            coverage.setdefault(script_name, []).append(test_path.relative_to(repo).as_posix())
    return coverage


def references_script_path(text: str, script_name: str) -> bool:
    """True when a test builds a path to the script, not merely names it.

    The existing tests reach a script as ROOT / "<stage>" / "scripts" / "<name>",
    so that is the signal. Naming a script in a string - a required-paths list,
    or an assertion message - is not evidence that anything runs it.
    """
    name = re.escape(script_name)
    pattern = rf'"scripts"\s*/\s*"{name}"|scripts/{name}'
    return re.search(pattern, text) is not None


def build_status(repo: Path, detail: dict[str, Any], coverage: dict[str, list[str]]) -> dict:
    """Decide how completely one stage is built, and say what is missing."""
    missing: list[str] = []
    if not detail["skill_present"]:
        missing.append("SKILL.md")
    elif not detail["frontmatter_valid"]:
        missing.append("parsable frontmatter")
    elif not detail["name_matches_directory"]:
        missing.append("frontmatter name matching the directory")
    if not detail["references"]:
        missing.append("references/*.md")

    tests: list[str] = []
    for script in detail["scripts"]:
        named = coverage.get(Path(script).name, [])
        tests.extend(named)
        if not named:
            missing.append(f"a test exercising {Path(script).name}")

    schema = detail["own_schema"]
    if schema is not None and not (repo / schema).is_file():
        missing.append(schema)

    if not detail["skill_present"]:
        status = "missing"
    elif missing:
        status = "partial"
    else:
        status = "built"

    return {
        "status": status,
        "missing": missing,
        "tests": sorted(set(tests)),
        "script": detail["scripts"][0] if detail["scripts"] else None,
        "schema": schema,
        "references": len(detail["references"]),
    }


def chips(stage: dict[str, Any], detail: dict[str, Any], gate_ids: set[str]) -> list[str]:
    """Derive a card's tag chips from what the repository contains."""
    tags = ["SCRIPT" if detail["scripts"] else "MODEL"]
    if stage["id"] in gate_ids:
        tags.append("GATE")
    if stage["optional"]:
        tags.append("OPTIONAL")
    if stage["read_only"]:
        tags.append("READ-ONLY")
    return tags


def artifact_path(factory: Path, stage: dict[str, Any], task_id: str | None) -> Path | None:
    if stage["artifact"] is None:
        return None
    if stage["scope"] == "project":
        return factory / stage["artifact"]
    if task_id is None:
        return None
    return factory / "tasks" / task_id / stage["artifact"]


def load_artifact(
    repo: Path, factory: Path, stage: dict[str, Any], task_id: str | None, schema: str | None
) -> dict[str, Any]:
    """Read one stage artifact and say whether it satisfies its schema."""
    path = artifact_path(factory, stage, task_id)
    record: dict[str, Any] = {
        "path": path.as_posix() if path is not None else None,
        "name": stage["artifact"],
        "source": stage["artifact_source"],
        "present": False,
        "valid": None,
        "errors": [],
        "modified_at": None,
        "payload": None,
    }
    if path is None or not path.is_file():
        return record

    record["present"] = True
    record["modified_at"] = utc_from_timestamp(path.stat().st_mtime)
    payload, reason = read_json(path)
    if payload is None:
        record["valid"] = False
        record["errors"] = [reason or "unreadable"]
        return record

    record["payload"] = payload
    if schema is not None and (repo / schema).is_file():
        valid, errors = validate_payload(payload, repo / schema)
        record["valid"] = valid
        record["errors"] = errors
    return record


def evidence(file_name: str | None, field: str | None, value: Any) -> dict[str, Any]:
    """One traceable reason for a status: the file, the field, and the value."""
    return {"file": file_name, "field": field, "value": value}


def derive_run_status(
    stage: dict[str, Any], record: dict[str, Any], intake_applies: bool
) -> dict[str, Any]:
    """Decide one node run status from its artifact, and record the evidence."""
    stage_id = stage["id"]
    if stage["lane"] == 0 and not intake_applies:
        return {
            "status": "not_applicable",
            "evidence": [evidence(None, None, "no intake artifacts; entered as a scoped ticket")],
        }

    if stage_id == "start-from-spec":
        return {
            "status": "passed",
            "evidence": [evidence(None, None, "inferred from the presence of intake artifacts")],
        }

    if not record["present"]:
        return {"status": "pending", "evidence": [evidence(record["name"], None, "absent")]}

    if record["valid"] is False:
        return {
            "status": "invalid",
            "evidence": [evidence(record["name"], "<schema>", record["errors"][:3])],
        }

    payload = record["payload"] or {}
    rule = RUN_RULES.get(stage_id, {"kind": "present"})
    kind = rule["kind"]

    if kind == "present":
        return {
            "status": "passed",
            "evidence": [evidence(record["name"], None, "present and schema-valid")],
        }

    if kind == "status":
        value, found = dotted(payload, "status")
        if not found:
            return {"status": "invalid", "evidence": [evidence(record["name"], "status", None)]}
        status = "passed" if value in rule["passed"] else "blocked"
        return {"status": status, "evidence": [evidence(record["name"], "status", value)]}

    if kind == "requirements":
        unknowns = [
            item
            for item in payload.get("unknowns", [])
            if isinstance(item, dict) and item.get("status") not in RESOLVED_UNKNOWN_STATES
        ]
        conflicts = [
            item
            for item in payload.get("conflicts", [])
            if isinstance(item, dict) and item.get("status") not in RESOLVED_CONFLICT_STATES
        ]
        marks = [
            evidence(record["name"], "unknowns[].status", f"{len(unknowns)} unresolved"),
            evidence(record["name"], "conflicts[].status", f"{len(conflicts)} open"),
        ]
        return {"status": "blocked" if unknowns or conflicts else "passed", "evidence": marks}

    if kind == "plan":
        ready, _ = dotted(payload, "ready_for_isolation")
        risk, _ = dotted(payload, "risk_level")
        reason, _ = dotted(payload, "approval_reason")
        marks = [
            evidence(record["name"], "ready_for_isolation", ready),
            evidence(record["name"], "risk_level", risk),
            evidence(record["name"], "approval_reason", reason),
        ]
        if ready is not True:
            return {"status": "blocked", "evidence": marks}
        if risk in ("HIGH", "CRITICAL") and not reason:
            return {"status": "blocked", "evidence": marks}
        return {"status": "passed", "evidence": marks}

    if kind == "validation":
        status, _ = dotted(payload, "status")
        ready, _ = dotted(payload, "ready_for_pull_request")
        blocking, found = dotted(payload, "code_quality.counts.BLOCKING")
        marks = [
            evidence(record["name"], "status", status),
            evidence(record["name"], "ready_for_pull_request", ready),
            evidence(
                record["name"],
                "code_quality.counts.BLOCKING",
                blocking if found else "not reviewed",
            ),
        ]
        passed = status == "pass" and ready is True and not (found and blocking)
        return {"status": "passed" if passed else "blocked", "evidence": marks}

    if kind == "security":
        critical, found = dotted(payload, "counts.CRITICAL")
        status, _ = dotted(payload, "status")
        marks = [
            evidence(record["name"], "status", status),
            evidence(record["name"], "counts.CRITICAL", critical if found else None),
        ]
        return {"status": "blocked" if found and critical else "passed", "evidence": marks}

    if kind == "completion":
        status, _ = dotted(payload, "status")
        inconsistencies = payload.get("inconsistencies") or []
        marks = [
            evidence(record["name"], "status", status),
            evidence(record["name"], "inconsistencies", len(inconsistencies)),
        ]
        passed = status == "complete" and not inconsistencies
        return {"status": "passed" if passed else "blocked", "evidence": marks}

    return {"status": "pending", "evidence": []}


def apply_flow_states(nodes: list[dict[str, Any]]) -> None:
    """Mark the active node and any optional stage the run went past.

    Both depend on the whole graph rather than on one artifact, so they are
    applied after every node has read its own file.
    """
    by_id = {node["id"]: node for node in nodes}
    predecessors: dict[str, list[str]] = {node["id"]: [] for node in nodes}
    for edge in EDGES:
        if edge["kind"] == "normal" and edge["source"] is not None and edge["target"] != "STOP":
            predecessors[edge["target"]].append(edge["source"])

    order = {stage_id: index for index, stage_id in enumerate(STAGE_IDS)}
    reached = [
        node for node in nodes if node["run"]["status"] not in ("pending", "not_applicable")
    ]
    furthest = max((order[node["id"]] for node in reached), default=-1)

    for node in nodes:
        if node["run"]["status"] != "pending":
            continue
        if node["optional"] and order[node["id"]] < furthest:
            node["run"]["status"] = "skipped"
            node["run"]["evidence"] = [
                evidence(node["run"]["artifact"]["name"], None, "absent while a later stage ran")
            ]

    for stage_id in STAGE_IDS:
        node = by_id[stage_id]
        if node["run"]["status"] != "pending":
            continue
        if all(by_id[p]["run"]["status"] in COMPLETE_STATES for p in predecessors[stage_id]):
            node["run"]["status"] = "active"
            return


def evaluate_gate(
    gate: dict[str, Any], records: dict[str, dict[str, Any]], nodes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Resolve one gate from the artifact field it depends on."""
    result = dict(gate)
    result["status"] = "pending"
    result["observed"] = None
    result["source_file"] = None

    if gate["id"] == "human-merge":
        result["source_file"] = "no artifact; a human owns the merge"
        return result

    record = records.get(gate["source"])
    if record is None or not record["present"]:
        result["source_file"] = f"{gate['artifact']} absent"
        return result

    result["source_file"] = f"{gate['artifact']}:{gate['field']}"
    if record["valid"] is False:
        result["status"] = "blocked"
        result["observed"] = "artifact does not satisfy its schema"
        return result

    value, found = dotted(record["payload"] or {}, gate["field"])
    result["observed"] = value if found else None
    if not found:
        result["status"] = "pending"
        return result

    node_status = nodes[gate["source"]]["run"]["status"]
    if node_status == "blocked":
        result["status"] = "blocked"
    elif value == gate["expected"] and node_status == "passed":
        result["status"] = "passed"
    else:
        result["status"] = "blocked"
    return result


def parse_scripts_table(repo: Path) -> dict[str, str]:
    """Read what each script enforces from the architecture document.

    The wording belongs to docs/architecture.md, so it is read from there
    rather than copied here, and an absent table simply yields no wording.
    """
    path = repo / "docs" / "architecture.md"
    if not path.is_file():
        return {}
    wording: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*`([^`]+\.py)`\s*\|\s*(.+?)\s*\|$", line.strip())
        if match:
            wording[match.group(1)] = match.group(2)
    return wording


def factory_tree(factory: Path, task_id: str | None) -> list[dict[str, Any]]:
    """List the artifacts the factory directory holds, present or not."""
    rows: list[dict[str, Any]] = []
    expected = [stage for stage in STAGES if stage["artifact"] is not None]
    for stage in expected:
        path = artifact_path(factory, stage, task_id)
        if path is None:
            continue
        exists = path.is_file()
        rows.append(
            {
                "stage": stage["id"],
                "file": stage["artifact"],
                "path": path.as_posix(),
                "present": exists,
                "modified_at": utc_from_timestamp(path.stat().st_mtime) if exists else None,
                "named_by": stage["artifact_source"],
            }
        )
    if task_id is not None:
        quality = factory / "tasks" / task_id / "quality-review.json"
        rows.append(
            {
                "stage": "validate-change",
                "file": "quality-review.json",
                "path": quality.as_posix(),
                "present": quality.is_file(),
                "modified_at": (
                    utc_from_timestamp(quality.stat().st_mtime) if quality.is_file() else None
                ),
                "named_by": "repository",
            }
        )
    return rows


def standards_view(factory: Path, task_id: str | None, records: dict[str, Any]) -> dict[str, Any]:
    """Backend code quality counts, from the review file or the validation report."""
    view: dict[str, Any] = {
        "source": None,
        "counts": {"BLOCKING": None, "ADVISORY": None},
        "reviewed_files": [],
        "skipped_files": [],
        "findings": [],
    }
    payload: dict[str, Any] | None = None
    if task_id is not None:
        path = factory / "tasks" / task_id / "quality-review.json"
        if path.is_file():
            payload, _ = read_json(path)
            view["source"] = "quality-review.json"

    if payload is None:
        validation = records.get("validate-change")
        if validation is not None and validation["present"]:
            candidate = (validation["payload"] or {}).get("code_quality")
            if isinstance(candidate, dict):
                payload = candidate
                view["source"] = "validation.json:code_quality"

    if payload is None:
        return view

    counts = payload.get("counts") or {}
    view["counts"] = {
        "BLOCKING": counts.get("BLOCKING"),
        "ADVISORY": counts.get("ADVISORY"),
    }
    view["reviewed_files"] = payload.get("reviewed_files") or []
    view["skipped_files"] = payload.get("skipped_files") or []
    view["findings"] = [
        {
            "severity": finding.get("severity"),
            "criterion": finding.get("criterion"),
            "file": finding.get("file"),
            "detail": finding.get("detail"),
        }
        for finding in payload.get("findings") or []
        if isinstance(finding, dict)
    ]
    return view


def discover_tasks(factory: Path) -> list[str]:
    tasks_root = factory / "tasks"
    if not tasks_root.is_dir():
        return []
    return sorted(path.name for path in tasks_root.iterdir() if path.is_dir())


def unmapped_skills(repo: Path) -> list[str]:
    """Skill directories the drawn pipeline does not place.

    An eighteenth skill would otherwise vanish from the map silently.
    """
    found = sorted(path.parent.name for path in repo.glob("*/SKILL.md"))
    return [name for name in found if name not in STAGE_IDS]


def fingerprint(state: dict[str, Any]) -> str:
    """Stable hash of everything except the timestamp, for cheap polling."""
    comparable = {key: value for key, value in state.items() if key != "generated_at"}
    encoded = json.dumps(comparable, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def truncate(text: str, limit: int = 96) -> str:
    """Shorten a description for a card without cutting a word in half."""
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0]
    return clipped.rstrip(",.;:") + "…"


def build_state(repo: Path, factory: Path, task_id: str | None) -> dict[str, Any]:
    """Assemble the whole map: topology, build status, and run status."""
    coverage = scan_tests(repo)
    gate_ids = {gate["source"] for gate in GATES}
    details = {stage["id"]: scan_skill(repo, stage) for stage in STAGES}
    builds = {stage_id: build_status(repo, detail, coverage) for stage_id, detail in
              details.items()}

    factory_present = factory.is_dir()
    intake_applies = factory_present and any(
        (factory / name).is_file()
        for name in ("project.json", "requirements.json", "backlog.json")
    )
    tasks = discover_tasks(factory) if factory_present else []
    selected = task_id if task_id in tasks else (tasks[0] if tasks else None)

    records: dict[str, dict[str, Any]] = {}
    nodes: list[dict[str, Any]] = []
    for stage in STAGES:
        detail = details[stage["id"]]
        record = (
            load_artifact(repo, factory, stage, selected, detail["own_schema"])
            if factory_present
            else {
                "path": None,
                "name": stage["artifact"],
                "source": stage["artifact_source"],
                "present": False,
                "valid": None,
                "errors": [],
                "modified_at": None,
                "payload": None,
            }
        )
        records[stage["id"]] = record
        run = (
            derive_run_status(stage, record, intake_applies)
            if factory_present
            else {"status": "pending", "evidence": []}
        )
        run["artifact"] = {key: value for key, value in record.items() if key != "payload"}
        nodes.append(
            {
                "id": stage["id"],
                "lane": stage["lane"],
                "scope": stage["scope"],
                "optional": stage["optional"],
                "read_only": stage["read_only"],
                "description": detail["description"],
                "subtitle": truncate(detail["description"]),
                "purpose": detail["purpose"],
                "failure_conditions": detail["failure_conditions"],
                "escalation_conditions": detail["escalation_conditions"],
                "chips": chips(stage, detail, gate_ids),
                "build": builds[stage["id"]],
                "run": run,
            }
        )

    if factory_present:
        apply_flow_states(nodes)

    by_id = {node["id"]: node for node in nodes}
    gates = [evaluate_gate(gate, records, by_id) for gate in GATES]

    project_payload = records["clarify-project"]["payload"] or {}
    active = next((node["id"] for node in nodes if node["run"]["status"] == "active"), None)
    modified = [
        node["run"]["artifact"]["modified_at"]
        for node in nodes
        if node["run"]["artifact"]["modified_at"]
    ]

    state: dict[str, Any] = {
        "generated_at": utc_now(),
        "mode": "run" if factory_present else "repo",
        "repo": {"path": repo.as_posix(), "name": repo.name},
        "factory": {
            "present": factory_present,
            "path": factory.as_posix(),
            "intake_applies": intake_applies,
        },
        "lanes": [dict(lane) for lane in LANES],
        "nodes": nodes,
        "edges": [dict(edge) for edge in EDGES],
        "gates": gates,
        "terminal": {"id": "STOP", "label": "STOP — A HUMAN OWNS THE MERGE"},
        "tasks": tasks,
        "selected_task": selected,
        "warnings": [
            f"skill directory not placed on the map: {name}" for name in unmapped_skills(repo)
        ],
        "views": {
            "run": {
                "project_id": project_payload.get("project_id"),
                "project_name": project_payload.get("project_name"),
                "selected_task": selected,
                "current_stage": active,
                "gates_passed": sum(1 for gate in gates if gate["status"] == "passed"),
                "gates_total": len(gates),
                "latest_artifact_at": max(modified) if modified else None,
            },
            "checkpoints": [
                {
                    "gate": gate["label"],
                    "between": f"{gate['source']} → {gate['target']}",
                    "status": gate["status"],
                    "source": gate["source_file"],
                    "observed": gate["observed"],
                    "passes_when": gate["passes_when"],
                }
                for gate in gates
            ],
            "skills": [
                {
                    "skill": node["id"],
                    "purpose": node["description"],
                    "script": node["build"]["script"],
                    "schema": node["build"]["schema"],
                    "tests": node["build"]["tests"],
                    "build": node["build"]["status"],
                    "missing": node["build"]["missing"],
                }
                for node in nodes
            ],
            "scripts": scripts_view(repo, details, coverage),
            "schemas": schemas_view(repo, details, records),
            "artifacts": factory_tree(factory, selected) if factory_present else [],
            "standards": standards_view(factory, selected, records),
            "out_of_scope": [dict(entry) for entry in OUT_OF_SCOPE],
        },
    }
    state["fingerprint"] = fingerprint(state)
    return state


def scripts_view(
    repo: Path, details: dict[str, dict[str, Any]], coverage: dict[str, list[str]]
) -> list[dict[str, Any]]:
    wording = parse_scripts_table(repo)
    rows: list[dict[str, Any]] = []
    for stage_id in STAGE_IDS:
        for script in details[stage_id]["scripts"]:
            rows.append(
                {
                    "script": script,
                    "stage": stage_id,
                    "enforces": wording.get(script, ""),
                    "tests": sorted(set(coverage.get(Path(script).name, []))),
                }
            )
    return rows


def schemas_view(
    repo: Path, details: dict[str, dict[str, Any]], records: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    owner = {
        detail["own_schema"]: stage_id
        for stage_id, detail in details.items()
        if detail["own_schema"]
    }
    rows: list[dict[str, Any]] = []
    for path in sorted((repo / "schemas").glob("*.schema.json")):
        relative = path.relative_to(repo).as_posix()
        stage_id = owner.get(relative)
        record = records.get(stage_id) if stage_id else None
        rows.append(
            {
                "schema": relative,
                "stage": stage_id,
                "artifact": record["name"] if record else None,
                "artifact_present": bool(record and record["present"]),
                "validates": record["valid"] if record else None,
            }
        )
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan the repository and any run state, and emit the pipeline map as JSON.",
    )
    parser.add_argument("--repo", default=".", help="Path to the repository root.")
    parser.add_argument(
        "--factory",
        default=None,
        help="Path to the factory run-state directory. Defaults to <repo>/.factory.",
    )
    parser.add_argument("--task", default=None, help="Task ID to render. Defaults to the first.")
    parser.add_argument("--out", default=None, help="Optional path to write the state JSON.")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo = resolve_directory(args.repo, "INVALID_REPO")
    factory = (
        Path(args.factory).expanduser().resolve()
        if args.factory is not None
        else repo / ".factory"
    )

    state = build_state(repo, factory, args.task)

    if args.out is not None:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    return state


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        emit(run(args))
        return 0
    except ScriptError as exc:
        emit({"status": "error", "error_code": exc.error_code, "message": exc.message})
        return 1
    except Exception as exc:  # pragma: no cover - last-resort CLI guard
        emit({"status": "error", "error_code": "INTERNAL_ERROR", "message": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())

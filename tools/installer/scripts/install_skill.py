"""Install the my-software-factory skill folder for Claude Code and Codex."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SKILL_NAME = "my-software-factory"
# Earlier names of this skill. An install under one of them would load beside
# the new one, so it is reported, and left for the user to remove.
LEGACY_NAMES = ("software-factory-gpt",)
MANIFEST_NAME = ".install.json"

# The skill is one folder in the repository. An install is that folder, plus the
# repository's rules and license, which live at the root so that agents working
# in the repository load them too. Tests, CI, docs, and tools never ship.
SKILL_DIR = SKILL_NAME
ROOT_FILES = ("AGENTS.md", "LICENSE")
REQUIRED_FILES = ("SKILL.md", "agents/openai.yaml")
IGNORED_NAMES = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")

TARGETS = ("claude", "codex")
DONE = {"create": "created", "replace": "replaced"}


class ScriptError(Exception):
    """Structured error that can be returned as JSON."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def default_skills_root(target: str) -> Path:
    """Return the user-level skills directory each agent scans."""
    if target == "claude":
        home = os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"
    else:
        home = os.environ.get("CODEX_HOME") or Path.home() / ".codex"
    return Path(home).expanduser() / "skills"


def read_skill_name(skill_md: Path) -> str | None:
    """Return the frontmatter `name` of a SKILL.md, or None when it has none."""
    try:
        lines = skill_md.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("\"'")
    return None


def payload_entries(source: Path) -> list[Path]:
    """Return the skill folder followed by the root files copied beside its contents."""
    skill_dir = source / SKILL_DIR
    missing = [
        *(f"{SKILL_DIR}/{name}" for name in REQUIRED_FILES if not (skill_dir / name).is_file()),
        *(name for name in ROOT_FILES if not (source / name).is_file()),
    ]
    if missing:
        raise ScriptError("SOURCE_INCOMPLETE", f"Source is missing: {', '.join(missing)}.")
    if read_skill_name(skill_dir / "SKILL.md") != SKILL_NAME:
        raise ScriptError("SOURCE_INVALID", f"Source SKILL.md is not named {SKILL_NAME}.")
    return [skill_dir, *(source / name for name in ROOT_FILES)]


def count_files(entries: list[Path]) -> int:
    total = 0
    for entry in entries:
        if entry.is_file():
            total += 1
            continue
        for _, dirnames, filenames in os.walk(entry):
            dirnames[:] = [name for name in dirnames if name != "__pycache__"]
            total += sum(1 for name in filenames if not name.endswith((".pyc", ".pyo")))
    return total


def source_commit(source: Path) -> tuple[str | None, bool | None]:
    """Return the source HEAD commit and whether its tree is dirty, when Git is available."""
    try:
        head = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            ["git", "-C", str(source), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None, None
    if head.returncode != 0 or status.returncode != 0:
        return None, None
    return head.stdout.strip(), bool(status.stdout.strip())


def legacy_installs(skills_root: Path) -> list[str]:
    """List installs of this skill under an earlier name. They are never removed here."""
    return [
        str(skills_root / name)
        for name in LEGACY_NAMES
        if (skills_root / name / "SKILL.md").is_file()
    ]


def is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def plan_install(source: Path, target: str, skills_root: Path, replace: bool) -> dict[str, Any]:
    """Decide what installing into one skills root would do, refusing unsafe cases."""
    destination = (skills_root / SKILL_NAME).absolute()
    if is_within(destination, source) or is_within(source, destination):
        raise ScriptError(
            "DESTINATION_OVERLAPS_SOURCE",
            f"{destination} overlaps the source repository.",
        )
    if destination.is_symlink():
        raise ScriptError(
            "DESTINATION_IS_LINK",
            f"{destination} is a link. Remove it yourself before installing a copy.",
        )
    if not destination.exists():
        return {"target": target, "path": str(destination), "action": "create"}
    if not destination.is_dir():
        raise ScriptError("DESTINATION_NOT_DIRECTORY", f"{destination} exists and is a file.")
    if not replace:
        raise ScriptError(
            "DESTINATION_EXISTS",
            f"{destination} already exists. Pass --replace to overwrite a previous install.",
        )
    if read_skill_name(destination / "SKILL.md") != SKILL_NAME:
        raise ScriptError(
            "DESTINATION_NOT_THIS_SKILL",
            f"{destination} is not a {SKILL_NAME} install. Refusing to replace it.",
        )
    return {"target": target, "path": str(destination), "action": "replace"}


def copy_payload(entries: list[Path], staging: Path) -> None:
    """Copy the skill folder's contents to the staging root, then the root files beside them."""
    skill_dir, *root_files = entries
    shutil.copytree(skill_dir, staging, ignore=IGNORED_NAMES)
    for path in root_files:
        shutil.copy2(path, staging / path.name)


def install(entries: list[Path], destination: Path, manifest: dict[str, Any]) -> None:
    """Stage the payload beside the destination, then swap it in."""
    staging = destination.with_name(f".{SKILL_NAME}.staging-{os.getpid()}")
    previous = destination.with_name(f".{SKILL_NAME}.previous-{os.getpid()}")
    if staging.exists() or previous.exists():
        raise ScriptError("STAGING_EXISTS", f"Leftover staging directory near {destination}.")

    try:
        copy_payload(entries, staging)
        (staging / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if destination.exists():
            destination.rename(previous)
        staging.rename(destination)
    except OSError as exc:
        if previous.exists() and not destination.exists():
            previous.rename(destination)
        shutil.rmtree(staging, ignore_errors=True)
        raise ScriptError("INSTALL_FAILED", f"Could not install to {destination}: {exc}") from exc

    shutil.rmtree(previous, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=[*TARGETS, "all"],
        default="all",
        help="Agent to install for (default all). Ignored when --skills-dir is given.",
    )
    parser.add_argument(
        "--skills-dir",
        action="append",
        default=[],
        metavar="PATH",
        help="Explicit skills directory to install into, e.g. a project's .claude/skills. "
        "Repeatable.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help=f"Overwrite an existing {SKILL_NAME} install. Never overwrites anything else.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be installed without writing anything.",
    )
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parents[3]),
        help="Repository to install from (default: this repository).",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.source).expanduser().resolve()
    entries = payload_entries(source)

    if args.skills_dir:
        roots = [("custom", Path(path).expanduser()) for path in args.skills_dir]
    else:
        targets = TARGETS if args.target == "all" else (args.target,)
        roots = [(target, default_skills_root(target)) for target in targets]

    # Every destination is checked before any is written, so a refusal never
    # leaves one agent updated and the other stale.
    plans = [plan_install(source, target, root, args.replace) for target, root in roots]
    commit, dirty = source_commit(source)
    file_count = count_files(entries)

    if not args.dry_run:
        manifest = {
            "skill": SKILL_NAME,
            "source": str(source),
            "source_commit": commit,
            "source_dirty": dirty,
            "installed_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
                "+00:00", "Z"
            ),
        }
        for plan in plans:
            install(entries, Path(plan["path"]), manifest)

    for plan in plans:
        plan["action"] = f"would_{plan['action']}" if args.dry_run else DONE[plan["action"]]
        plan["payload_files"] = file_count
        plan["legacy_installs"] = legacy_installs(Path(plan["path"]).parent)

    return {
        "status": "dry_run" if args.dry_run else "installed",
        "skill": SKILL_NAME,
        "source": str(source),
        "source_commit": commit,
        "source_dirty": dirty,
        "installs": plans,
    }


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

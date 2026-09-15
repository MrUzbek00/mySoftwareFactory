"""Scan the added lines of a task diff for security-relevant patterns.

This is a deterministic first pass, not a substitute for judgment. It reads only
lines the change ADDED, so it flags what this task introduced rather than what
the repository already contained.

Matched secrets are always redacted before they reach the report.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

TASK_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
EVIDENCE_CHARS = 160
DEPENDENCY_FILES = {
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "Gemfile",
    "Gemfile.lock",
    "composer.json",
    "pom.xml",
    "build.gradle",
}


class Rule(NamedTuple):
    name: str
    severity: str
    pattern: re.Pattern[str]
    redact: bool


RULES: list[Rule] = [
    Rule("private-key-block", "CRITICAL", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), True),
    Rule("aws-access-key-id", "CRITICAL", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), True),
    Rule("github-token", "CRITICAL", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), True),
    Rule("slack-token", "CRITICAL", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), True),
    Rule("google-api-key", "CRITICAL", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), True),
    Rule("stripe-secret-key", "CRITICAL", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{20,}\b"), True),
    Rule("jwt-literal", "HIGH", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."), True),
    Rule(
        "hardcoded-credential",
        "HIGH",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)"
            r"\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"
        ),
        True,
    ),
    Rule("shell-injection-risk", "HIGH", re.compile(r"shell\s*=\s*True"), False),
    Rule("os-system-call", "HIGH", re.compile(r"\bos\.system\s*\("), False),
    Rule("python-eval-exec", "HIGH", re.compile(r"(?<![\w.])(?:eval|exec)\s*\("), False),
    Rule("pickle-load", "HIGH", re.compile(r"\bpickle\.loads?\s*\("), False),
    Rule("yaml-unsafe-load", "HIGH", re.compile(r"\byaml\.load\s*\((?![^)]*Safe)"), False),
    Rule(
        "dangerous-inner-html",
        "HIGH",
        re.compile(r"dangerouslySetInnerHTML|\.innerHTML\s*="),
        False,
    ),
    Rule(
        "sql-string-building",
        "HIGH",
        re.compile(r"(?i)(?:SELECT|INSERT|UPDATE|DELETE)\b[^\n]*(?:\+\s*\w+|%\s*\(|\{\w+\}|f[\"'])"),
        False,
    ),
    Rule(
        "tls-verification-disabled",
        "HIGH",
        re.compile(r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false"),
        False,
    ),
    Rule("md5-or-sha1-hash", "MEDIUM", re.compile(r"\b(?:md5|sha1)\s*\("), False),
    Rule("subprocess-call", "LOW", re.compile(r"\bsubprocess\.(?:run|Popen|call)\s*\("), False),
    Rule(
        "cors-wildcard",
        "MEDIUM",
        re.compile(r"[\"']Access-Control-Allow-Origin[\"']\s*[:,]\s*[\"']\*[\"']"),
        False,
    ),
    Rule(
        "permissive-file-mode",
        "MEDIUM",
        re.compile(r"chmod\s*\(\s*[^,]+,\s*0o?7[0-7][0-7]"),
        False,
    ),
]


class ScriptError(Exception):
    """Structured error that can be returned as JSON."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def run_git(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ScriptError("GIT_COMMAND_FAILED", detail or f"git {' '.join(args)} failed")
    return result


def validate_task_id(task_id: str) -> str:
    value = task_id.strip()
    if not TASK_ID_PATTERN.fullmatch(value):
        raise ScriptError(
            "INVALID_TASK_ID",
            "Task ID must match TASK-* using uppercase safe parts.",
        )
    return value


def resolve_worktree(worktree_arg: str) -> Path:
    worktree = Path(worktree_arg).expanduser().resolve()
    if not worktree.exists() or not worktree.is_dir():
        raise ScriptError("INVALID_WORKTREE", "Worktree path must be an existing directory.")

    result = run_git(worktree, ["rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        raise ScriptError("INVALID_WORKTREE", "Worktree path must be inside a Git repository.")
    return worktree


def redact(line: str, match: re.Match[str]) -> str:
    """Replace the matched secret with a length-preserving mask."""
    start, end = match.span()
    masked = f"{line[:start]}<redacted:{end - start}chars>{line[end:]}"
    return masked.strip()[:EVIDENCE_CHARS]


def iter_added_lines(diff: str):
    """Yield (path, line_number_in_new_file, added_line_text)."""
    current_file = None
    new_line_no = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:].strip()
            continue
        if raw.startswith("+++ ") or raw.startswith("--- "):
            continue
        if raw.startswith("@@"):
            header = re.search(r"\+(\d+)", raw)
            new_line_no = int(header.group(1)) if header else 0
            continue
        if current_file is None:
            continue
        if raw.startswith("+"):
            yield current_file, new_line_no, raw[1:]
            new_line_no += 1
        elif not raw.startswith("-"):
            new_line_no += 1


def scan(diff: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    dependency_hits: dict[str, list[str]] = {}

    for path, line_no, text in iter_added_lines(diff):
        basename = path.rsplit("/", 1)[-1]
        if basename in DEPENDENCY_FILES and text.strip():
            dependency_hits.setdefault(path, []).append(text.strip()[:EVIDENCE_CHARS])

        for rule in RULES:
            match = rule.pattern.search(text)
            if match is None:
                continue
            evidence = redact(text, match) if rule.redact else text.strip()[:EVIDENCE_CHARS]
            findings.append(
                {
                    "rule": rule.name,
                    "severity": rule.severity,
                    "file": path,
                    "line": line_no,
                    "evidence": evidence,
                }
            )

    dependency_changes = [
        {"file": path, "added_lines": lines[:50]} for path, lines in sorted(dependency_hits.items())
    ]
    return findings, dependency_changes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan added diff lines for security-relevant patterns.",
    )
    parser.add_argument("--worktree", required=True, help="Path to the task worktree.")
    parser.add_argument("--task-id", required=True, help="Traceable task ID, for example TASK-123.")
    parser.add_argument(
        "--base",
        required=True,
        help="Base branch or ref, for example origin/main.",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    task_id = validate_task_id(args.task_id)
    worktree = resolve_worktree(args.worktree)

    base = run_git(worktree, ["merge-base", args.base, "HEAD"], check=False)
    if base.returncode != 0:
        raise ScriptError("MISSING_BASE_BRANCH", f"Cannot resolve base ref: {args.base}.")
    base_commit = base.stdout.strip()

    branch = run_git(worktree, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    head_commit = run_git(worktree, ["rev-parse", "HEAD"]).stdout.strip()
    diff = run_git(worktree, ["diff", "--unified=0", f"{base_commit}..HEAD"]).stdout

    findings, dependency_changes = scan(diff)
    counts = {level: 0 for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
    for finding in findings:
        counts[finding["severity"]] += 1

    return {
        "status": "findings" if findings else "clean",
        "task_id": task_id,
        "branch": branch,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "findings": findings,
        "dependency_changes": dependency_changes,
        "counts": counts,
        "requires_human_review": bool(
            counts["CRITICAL"] or counts["HIGH"] or dependency_changes
        ),
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = run(args)
        emit(report)
        return 0 if report["status"] == "clean" else 1
    except ScriptError as exc:
        emit({"status": "error", "error_code": exc.error_code, "message": exc.message})
        return 1
    except Exception as exc:  # pragma: no cover - last-resort CLI guard
        emit({"status": "error", "error_code": "INTERNAL_ERROR", "message": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())

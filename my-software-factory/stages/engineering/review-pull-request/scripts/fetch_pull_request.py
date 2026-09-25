"""Fetch a pull request's metadata, diff, checks, and review threads.

Strictly read-only. This script has no code path that approves, merges, closes,
comments on, or otherwise modifies a pull request.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

MAX_DIFF_BYTES = 400000
PR_FIELDS = (
    "number,title,body,state,isDraft,url,author,baseRefName,headRefName,"
    "additions,deletions,changedFiles,mergeable,reviewDecision,headRefOid,"
    "reviews,comments,labels,createdAt,updatedAt"
)


class ScriptError(Exception):
    """Structured error that can be returned as JSON."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def run_gh(cwd: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    import shutil

    executable = shutil.which("gh")
    if executable is None:
        raise ScriptError("GH_NOT_FOUND", "GitHub CLI (gh) is not installed or not on PATH.")

    result = subprocess.run(
        [executable, *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ScriptError("GH_COMMAND_FAILED", detail or f"gh {' '.join(args)} failed")
    return result


def resolve_repo_path(repo_arg: str) -> Path:
    repo = Path(repo_arg).expanduser().resolve()
    if not repo.exists() or not repo.is_dir():
        raise ScriptError("INVALID_REPOSITORY", "Repository path must be an existing directory.")
    return repo


def ensure_gh_authenticated(repo: Path) -> None:
    result = run_gh(repo, ["auth", "status"], check=False)
    if result.returncode != 0:
        raise ScriptError(
            "GH_NOT_AUTHENTICATED",
            "GitHub CLI is not authenticated. Run: gh auth login",
        )


def fetch_metadata(repo: Path, selector: str) -> dict[str, Any]:
    result = run_gh(repo, ["pr", "view", selector, "--json", PR_FIELDS])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ScriptError("PR_PARSE_FAILED", "Could not parse pull request metadata.") from exc


def fetch_diff(repo: Path, selector: str, out_dir: Path | None) -> dict[str, Any]:
    result = run_gh(repo, ["pr", "diff", selector], check=False)
    if result.returncode != 0:
        return {"available": False, "truncated": False, "path": None, "bytes": 0}

    diff = result.stdout
    encoded = diff.encode("utf-8")
    truncated = len(encoded) > MAX_DIFF_BYTES
    if truncated:
        diff = encoded[:MAX_DIFF_BYTES].decode("utf-8", errors="ignore")

    path = None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"pr-{selector}.diff"
        target.write_text(diff, encoding="utf-8")
        path = str(target)

    return {
        "available": True,
        "truncated": truncated,
        "path": path,
        "bytes": len(encoded),
        "text": None if path else diff,
    }


def fetch_checks(repo: Path, selector: str) -> list[dict[str, str]]:
    result = run_gh(repo, ["pr", "checks", selector, "--json", "name,state"], check=False)
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return [
        {"name": str(item.get("name", "")), "state": str(item.get("state", ""))}
        for item in data
        if isinstance(item, dict)
    ]


def fetch_review_threads(repo: Path, number: int) -> dict[str, Any]:
    """Read review threads through the GraphQL API to learn what is unresolved."""
    query = (
        "query($owner:String!,$repo:String!,$number:Int!){"
        "repository(owner:$owner,name:$repo){pullRequest(number:$number){"
        "reviewThreads(first:100){nodes{id isResolved isOutdated "
        "comments(first:10){nodes{author{login} body path line}}}}}}}"
    )
    result = run_gh(
        repo,
        [
            "api",
            "graphql",
            "-F",
            "owner={owner}",
            "-F",
            "repo={repo}",
            "-F",
            f"number={number}",
            "-f",
            f"query={query}",
        ],
        check=False,
    )
    if result.returncode != 0:
        return {"available": False, "unresolved": 0, "threads": []}

    try:
        payload = json.loads(result.stdout)
        nodes = payload["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return {"available": False, "unresolved": 0, "threads": []}

    threads = []
    for node in nodes:
        comments = node.get("comments", {}).get("nodes", [])
        first = comments[0] if comments else {}
        author = (first.get("author") or {}).get("login")
        threads.append(
            {
                "id": node.get("id"),
                "resolved": bool(node.get("isResolved")),
                "outdated": bool(node.get("isOutdated")),
                "path": first.get("path"),
                "line": first.get("line"),
                "author": author,
                "body": (first.get("body") or "")[:1000],
                "comment_count": len(comments),
            }
        )

    return {
        "available": True,
        "unresolved": sum(1 for t in threads if not t["resolved"]),
        "threads": threads,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch pull request context for review. Read-only.",
    )
    parser.add_argument("--repo-path", required=True, help="Path inside the Git repository.")
    parser.add_argument("--pr", required=True, help="Pull request number or branch name.")
    parser.add_argument("--out-dir", default=None, help="Directory to write the diff into.")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo = resolve_repo_path(args.repo_path)
    selector = str(args.pr).strip()
    if not selector:
        raise ScriptError("INVALID_PR", "Pull request selector cannot be empty.")

    ensure_gh_authenticated(repo)
    metadata = fetch_metadata(repo, selector)

    number = metadata.get("number")
    if not isinstance(number, int):
        raise ScriptError("PR_PARSE_FAILED", "Pull request metadata is missing a number.")

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else None
    threads = fetch_review_threads(repo, number)

    return {
        "status": "fetched",
        "pull_request": {
            "number": number,
            "title": metadata.get("title"),
            "body": metadata.get("body"),
            "state": metadata.get("state"),
            "draft": metadata.get("isDraft"),
            "url": metadata.get("url"),
            "author": (metadata.get("author") or {}).get("login"),
            "base_branch": metadata.get("baseRefName"),
            "head_branch": metadata.get("headRefName"),
            "head_commit": metadata.get("headRefOid"),
            "additions": metadata.get("additions"),
            "deletions": metadata.get("deletions"),
            "changed_files": metadata.get("changedFiles"),
            "mergeable": metadata.get("mergeable"),
            "review_decision": metadata.get("reviewDecision"),
            "labels": [
                label.get("name")
                for label in (metadata.get("labels") or [])
                if isinstance(label, dict)
            ],
        },
        "checks": fetch_checks(repo, selector),
        "review_threads": threads,
        "diff": fetch_diff(repo, selector, out_dir),
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

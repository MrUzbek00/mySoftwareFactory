"""Serve the pipeline map from a local HTTP server, read-only.

The server binds the loopback interface explicitly and never anything else. It
reads the repository and the factory directory, and writes nothing to either.
It runs no subprocess and executes no pipeline stage. It answers the page at
a fixed set of page routes, the projects at /api/projects, the state at
/api/state and one stage at /api/skill/<name>; everything else is a 404.

The page draws every view in the browser, so each page route serves the same
file. A route that names a stage or a task is answered only when that name is
already known, and the name is compared, never used to build a path.

A project is a factory directory. The default one is --factory; others are the
<folder>/.factory directories one level under --projects-dir. A request chooses
among them with ?project=<slug>, and the slug is looked up in that list, so a
request can only ever reach a directory the server found itself.

State is rebuilt on request rather than cached, so the page always reflects the
files as they are now. The fingerprint is served as an ETag so that a client
polling every few seconds gets a 304 and re-renders nothing.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_state import (  # noqa: E402
    STAGE_IDS,
    ScriptError,
    build_state,
    discover_tasks,
    emit,
    read_json,
    resolve_directory,
    task_index,
)

ASSET = Path(__file__).resolve().parent.parent / "assets" / "index.html"
BOOTSTRAP = '<script id="bootstrap-state" type="application/json">null</script>'
HOST = "127.0.0.1"
# Pages that take no parameter. /stages/<name> and /tasks/<task id> are the
# other two page routes, checked in is_page_route.
FIXED_PAGE_ROUTES = frozenset({"/", "/tasks", "/stages", "/repository"})
FACTORY_DIR_NAME = ".factory"


class Project(NamedTuple):
    """One factory directory the map can show, addressed by its slug."""

    slug: str
    factory: Path
    is_default: bool


def project_folder(factory: Path) -> Path:
    """The folder a factory directory belongs to: its parent when it is a .factory."""
    return factory.parent if factory.name == FACTORY_DIR_NAME else factory


def slug_for(folder_name: str, taken: set[str]) -> str:
    """A URL-safe name for a project folder, unique among `taken`."""
    base = re.sub(r"[^a-z0-9]+", "-", folder_name.lower()).strip("-") or "project"
    slug = base
    suffix = 2
    while slug in taken:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def discover_projects(default_factory: Path, projects_dir: Path | None) -> list[Project]:
    """The default factory first, then every <folder>/.factory under `projects_dir`.

    `projects_dir` is scanned one level deep and only for directories named
    .factory; None scans nothing. A factory found twice is listed once.
    """
    factories = [default_factory]
    if projects_dir is not None and projects_dir.is_dir():
        candidates = sorted(
            (child / FACTORY_DIR_NAME for child in projects_dir.iterdir() if child.is_dir()),
            key=lambda path: path.parent.name.lower(),
        )
        factories += [candidate for candidate in candidates if candidate.is_dir()]

    projects: list[Project] = []
    seen: set[Path] = set()
    taken: set[str] = set()
    for factory in factories:
        resolved = factory.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        slug = slug_for(project_folder(factory).name, taken)
        taken.add(slug)
        projects.append(Project(slug=slug, factory=factory, is_default=not projects))
    return projects


def project_summary(project: Project) -> dict[str, Any]:
    """What the project dropdown shows for one project, read from its factory."""
    context, _ = read_json(project.factory / "project.json")
    context = context or {}
    present = project.factory.is_dir()
    index = task_index(project.factory, discover_tasks(project.factory)) if present else []
    return {
        "slug": project.slug,
        "name": context.get("project_name") or project_folder(project.factory).name,
        "project_id": context.get("project_id"),
        "path": project.factory.as_posix(),
        "present": present,
        "tasks_total": len(index),
        "tasks_done": sum(1 for entry in index if entry["done"]),
        "default": project.is_default,
    }


def read_page() -> str:
    if not ASSET.is_file():
        raise ScriptError("MISSING_ASSET", f"Page asset does not exist: {ASSET}")
    return ASSET.read_text(encoding="utf-8")


def snapshot(page: str, state: dict[str, Any]) -> str:
    """Inline the state so the page renders from the filesystem alone."""
    encoded = json.dumps(state, sort_keys=True).replace("</", "<\\/")
    return page.replace(
        BOOTSTRAP,
        f'<script id="bootstrap-state" type="application/json">{encoded}</script>',
    )


def skill_detail(state: dict[str, Any], name: str) -> dict[str, Any] | None:
    for node in state["nodes"]:
        if node["id"] == name:
            return node
    return None


def is_page_route(route: str, factory: Path) -> bool:
    """Whether the page answers at this route.

    `route` is the request path with any trailing slash removed. A stage name
    must be one of the known stages and a task ID one of the task directories
    already in the factory, so an unknown name is a 404 like any other route.
    """
    if route in FIXED_PAGE_ROUTES:
        return True
    section, _, name = route.lstrip("/").partition("/")
    if not name or "/" in name:
        return False
    if section == "stages":
        return name in STAGE_IDS
    if section == "tasks":
        return name in discover_tasks(factory)
    return False


class MapHandler(BaseHTTPRequestHandler):
    """Page routes and three API routes; no filesystem path is taken from the request."""

    server_version = "factory-map"
    repo: Path
    factory: Path
    projects_dir: Path | None = None

    def chosen_project(self, query: dict[str, list[str]]) -> Project | None:
        """The project ?project= names, the default when it names none, or None if unknown."""
        projects = discover_projects(self.factory, self.projects_dir)
        slug = query.get("project", [None])[0]
        if slug is None:
            return projects[0]
        return next((project for project in projects if project.slug == slug), None)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Stay quiet; a polling client would otherwise fill the terminal."""

    def respond(self, code: int, body: bytes, content_type: str, etag: str | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if etag is not None:
            self.send_header("ETag", etag)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def respond_json(self, code: int, payload: dict[str, Any], etag: str | None = None) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.respond(code, body, "application/json; charset=utf-8", etag)

    def not_found(self) -> None:
        self.respond_json(404, {"error_code": "NOT_FOUND", "message": "No such route."})

    def do_GET(self) -> None:  # noqa: N802 - http.server names the method
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if route == "/api/projects":
            projects = discover_projects(self.factory, self.projects_dir)
            self.respond_json(200, {"projects": [project_summary(p) for p in projects]})
            return

        project = self.chosen_project(query)
        if project is None:
            self.not_found()
            return

        if is_page_route(route, project.factory):
            self.respond(200, read_page().encode("utf-8"), "text/html; charset=utf-8")
            return

        if route == "/api/state":
            task = query.get("task", [None])[0]
            state = build_state(self.repo, project.factory, task)
            etag = '"' + state["fingerprint"] + '"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.end_headers()
                return
            self.respond_json(200, state, etag)
            return

        if route.startswith("/api/skill/"):
            name = route[len("/api/skill/"):]
            # Checked against the known stage list, never used as a path.
            if name not in STAGE_IDS:
                self.not_found()
                return
            state = build_state(self.repo, project.factory, None)
            detail = skill_detail(state, name)
            if detail is None:
                self.not_found()
                return
            self.respond_json(200, detail)
            return

        self.not_found()

    def do_HEAD(self) -> None:  # noqa: N802 - http.server names the method
        self.do_GET()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Serve the factory pipeline map on the loopback interface.",
    )
    parser.add_argument("--repo", default=".", help="Path to the repository root.")
    parser.add_argument(
        "--factory",
        default=None,
        help="Path to the factory run-state directory. Defaults to <repo>/.factory.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8787,
        help="Port to bind on 127.0.0.1. Use 0 to pick a free one.",
    )
    parser.add_argument(
        "--projects-dir",
        default=None,
        help="Folder whose subfolders' .factory directories are listed as projects. "
        "Defaults to the folder containing --repo.",
    )
    parser.add_argument("--open", action="store_true", help="Open the map in a browser.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Write a self-contained snapshot instead of serving.",
    )
    parser.add_argument("--out", default=None, help="Snapshot destination, required by --once.")
    return parser


IN_USE = {errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", errno.EADDRINUSE)}


class MapServer(ThreadingHTTPServer):
    """A loopback server that refuses a port something else is already serving.

    SO_REUSEADDR does not mean the same thing on both platforms. On Windows it
    lets a second socket bind a port that is actively in use, so the default
    would silently start a second server that never receives a request. The
    option is therefore disabled there, and kept on POSIX where it only skips
    the TIME_WAIT delay on restart.
    """

    daemon_threads = True
    allow_reuse_address = os.name != "nt"


def make_server(
    repo: Path, factory: Path, port: int, projects_dir: Path | None = None
) -> MapServer:
    """A server for `factory` and, when `projects_dir` is given, its sibling projects."""
    handler = type(
        "BoundMapHandler",
        (MapHandler,),
        {"repo": repo, "factory": factory, "projects_dir": projects_dir},
    )
    try:
        return MapServer((HOST, port), handler)
    except OSError as exc:
        if exc.errno in IN_USE:
            raise ScriptError(
                "PORT_IN_USE",
                f"Port {port} on {HOST} is already in use. Pass --port 0 for a free one.",
            ) from exc
        raise ScriptError("BIND_FAILED", f"Could not bind {HOST}:{port}: {exc}") from exc


def run(args: argparse.Namespace) -> int:
    repo = resolve_directory(args.repo, "INVALID_REPO")
    factory = (
        Path(args.factory).expanduser().resolve()
        if args.factory is not None
        else repo / ".factory"
    )

    if args.once:
        if args.out is None:
            raise ScriptError("MISSING_OUT", "--once requires --out <file>.")
        state = build_state(repo, factory, None)
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(snapshot(read_page(), state), encoding="utf-8")
        print(f"Wrote a self-contained snapshot to {out_path}")
        return 0

    if args.port != 0 and not 1 <= args.port <= 65535:
        raise ScriptError("INVALID_PORT", f"Not a usable port: {args.port}")

    projects_dir = (
        resolve_directory(args.projects_dir, "INVALID_PROJECTS_DIR")
        if args.projects_dir is not None
        else repo.parent
    )
    server = make_server(repo, factory, args.port, projects_dir)
    url = f"http://{HOST}:{server.server_address[1]}"
    # Flushed explicitly: stdout is block-buffered when it is a pipe, and a
    # caller waiting to read the address would otherwise wait forever.
    print(url, flush=True)
    print(f"Repository: {repo}", flush=True)
    print(
        f"Factory:    {factory}"
        + ("" if factory.is_dir() else "  (absent; the map runs in repository mode)"),
        flush=True,
    )
    print(f"Projects:   .factory folders under {projects_dir}", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except ScriptError as exc:
        emit({"status": "error", "error_code": exc.error_code, "message": exc.message})
        return 1
    except Exception as exc:  # pragma: no cover - last-resort CLI guard
        emit({"status": "error", "error_code": "INTERNAL_ERROR", "message": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())

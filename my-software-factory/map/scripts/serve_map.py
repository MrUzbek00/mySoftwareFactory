"""Serve the pipeline map from a local HTTP server, read-only.

The server binds the loopback interface explicitly and never anything else. It
reads the repository and the factory directory, and writes nothing to either.
It runs no subprocess and executes no pipeline stage. There are three routes
and everything else is a 404.

State is rebuilt on request rather than cached, so the page always reflects the
files as they are now. The fingerprint is served as an ETag so that a client
polling every few seconds gets a 304 and re-renders nothing.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_state import (  # noqa: E402
    DEFAULT_REPO,
    STAGE_IDS,
    ScriptError,
    build_state,
    emit,
    resolve_directory,
)

ASSET = Path(__file__).resolve().parent.parent / "assets" / "index.html"
BOOTSTRAP = '<script id="bootstrap-state" type="application/json">null</script>'
HOST = "127.0.0.1"


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


class MapHandler(BaseHTTPRequestHandler):
    """Three routes, no filesystem path ever taken from the request."""

    server_version = "factory-map"
    repo: Path
    factory: Path

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

        if route == "/":
            self.respond(200, read_page().encode("utf-8"), "text/html; charset=utf-8")
            return

        if route == "/api/state":
            task = parse_qs(parsed.query).get("task", [None])[0]
            state = build_state(self.repo, self.factory, task)
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
            state = build_state(self.repo, self.factory, None)
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
    parser.add_argument(
        "--repo",
        default=str(DEFAULT_REPO),
        help="Folder that holds my-software-factory/. Defaults to the one this script ships in.",
    )
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


def make_server(repo: Path, factory: Path, port: int) -> MapServer:
    handler = type("BoundMapHandler", (MapHandler,), {"repo": repo, "factory": factory})
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

    server = make_server(repo, factory, args.port)
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

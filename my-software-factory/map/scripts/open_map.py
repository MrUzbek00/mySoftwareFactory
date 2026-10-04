"""Open the pipeline map in a browser, starting its server only when needed.

The skill runs this first on every use, so it must be quick and idempotent. It
looks for a map already serving this project on the loopback ports it owns and
reuses it. Otherwise it starts serve_map.py detached, so the server outlives
this call and the agent's turn, waits until the server answers, and then opens
the browser.

It never blocks the pipeline. A failure is reported as JSON with a non-zero
exit, and the agent carries on without the map.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_state import DEFAULT_REPO, ScriptError, emit, resolve_directory  # noqa: E402
from serve_map import HOST  # noqa: E402

SERVE_SCRIPT = Path(__file__).resolve().parent / "serve_map.py"
DEFAULT_PORT = 8787
# One port per project, so several projects can each keep a map open.
PORT_RANGE = 10
READY_TIMEOUT_SECONDS = 10.0
# Loopback only: a system proxy setting must never see these requests.
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch_state(port: int) -> dict[str, Any] | None:
    """The state a map on this port serves, or None when nothing map-like answers."""
    try:
        with LOCAL.open(f"http://{HOST}:{port}/api/state", timeout=2) as response:
            payload = json.loads(response.read())
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def same_path(served: Any, expected: Path) -> bool:
    return isinstance(served, str) and os.path.normcase(served) == os.path.normcase(
        expected.as_posix()
    )


def serves_project(state: dict[str, Any] | None, repo: Path, factory: Path) -> bool:
    """Whether a map's state was built from this skill and this project's factory."""
    if state is None:
        return False
    return same_path(state.get("repo", {}).get("path"), repo) and same_path(
        state.get("factory", {}).get("path"), factory
    )


def is_listening(port: int) -> bool:
    """A quick connect with a short timeout.

    Windows takes about two seconds to refuse a loopback connection, so asking
    ten idle ports for their state would stall the launch. This does not.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.1)
        try:
            return probe.connect_ex((HOST, port)) == 0
        except OSError:
            return False


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, port))
        except OSError:
            return False
    return True


def any_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def serves_project_on(port: int, repo: Path, factory: Path) -> bool:
    return is_listening(port) and serves_project(fetch_state(port), repo, factory)


def find_running_map(ports: range, repo: Path, factory: Path) -> int | None:
    return next((port for port in ports if serves_project_on(port, repo, factory)), None)


def start_server(repo: Path, factory: Path, port: int) -> subprocess.Popen:
    """Start serve_map.py detached from this process, its console, and its session."""
    options: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    command = [
        sys.executable,
        str(SERVE_SCRIPT),
        "--repo",
        str(repo),
        "--factory",
        str(factory),
        "--port",
        str(port),
    ]
    return subprocess.Popen(command, **options)


def wait_until_ready(process: subprocess.Popen, port: int, repo: Path, factory: Path) -> bool:
    """Wait for the new server to answer. False when another launch won the port.

    Two launches at once can both pick the same free port; the loser's server
    exits on the bind, and the winner's map is just as good.
    """
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if serves_project_on(port, repo, factory):
            return process.poll() is None
        if process.poll() is not None:
            if serves_project_on(port, repo, factory):
                return False
            raise ScriptError(
                "SERVER_EXITED",
                f"The map server exited with code {process.returncode} before answering.",
            )
        time.sleep(0.2)
    process.terminate()
    raise ScriptError(
        "SERVER_TIMEOUT",
        f"The map server did not answer on {HOST}:{port} within {READY_TIMEOUT_SECONDS:g}s.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open the factory map for this project, starting its server if needed.",
    )
    parser.add_argument(
        "--factory",
        default=".factory",
        help="Project run-state directory. Defaults to .factory in the working directory.",
    )
    parser.add_argument(
        "--repo",
        default=str(DEFAULT_REPO),
        help="Folder that holds my-software-factory/. Defaults to the one this script ships in.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"First of {PORT_RANGE} loopback ports to reuse or claim. Default {DEFAULT_PORT}.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start or find the server and print its URL, without opening a browser.",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo = resolve_directory(args.repo, "INVALID_REPO")
    factory = Path(args.factory).expanduser().resolve()
    if not 1 <= args.port <= 65535 - PORT_RANGE:
        raise ScriptError("INVALID_PORT", f"Not a usable port: {args.port}")
    ports = range(args.port, args.port + PORT_RANGE)

    pid: int | None = None
    port = find_running_map(ports, repo, factory)
    if port is not None:
        status = "reused"
    else:
        port = next((candidate for candidate in ports if port_is_free(candidate)), None)
        if port is None:
            port = any_free_port()
        process = start_server(repo, factory, port)
        if wait_until_ready(process, port, repo, factory):
            status, pid = "started", process.pid
        else:
            status = "reused"

    url = f"http://{HOST}:{port}"
    opened = False if args.no_browser else webbrowser.open(url)
    return {
        "status": status,
        "url": url,
        "pid": pid,
        "repo": repo.as_posix(),
        "factory": factory.as_posix(),
        "factory_present": factory.is_dir(),
        "browser_opened": opened,
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

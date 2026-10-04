"""The launcher opens one map per project and reuses it on every later call.

These tests run the launcher as the skill does, as a separate process, and let
it start a real detached server. Every server started here is stopped again.
"""

import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "my-software-factory" / "map" / "scripts" / "open_map.py"
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def load_module():
    spec = importlib.util.spec_from_file_location("open_map", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


open_map = load_module()


def free_base_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def launch() -> Iterator[Callable[..., dict[str, Any]]]:
    """Run the launcher without a browser, and stop whatever it started."""
    started: list[int] = []

    def run(factory: Path, port: int) -> dict[str, Any]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--no-browser", "--port", str(port),
             "--factory", str(factory)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        result = json.loads(completed.stdout)
        assert completed.returncode == 0, result
        if result["pid"]:
            started.append(result["pid"])
        return result

    yield run
    for pid in started:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def state_at(url: str) -> dict[str, Any]:
    with LOCAL.open(url + "/api/state", timeout=10) as response:
        return json.loads(response.read())


def test_the_first_call_starts_a_map_and_later_calls_reuse_it(
    factory_run: Callable, launch: Callable
) -> None:
    factory = factory_run()
    port = free_base_port()

    first = launch(factory, port)
    assert first["status"] == "started"
    assert first["url"].startswith("http://127.0.0.1:")
    assert first["browser_opened"] is False
    assert first["factory_present"] is True

    served = state_at(first["url"])
    assert served["factory"]["path"] == factory.resolve().as_posix()
    assert served["repo"]["path"] == ROOT.as_posix()

    second = launch(factory, port)
    assert second["status"] == "reused"
    assert second["url"] == first["url"]
    assert second["pid"] is None


def test_another_project_gets_its_own_map(
    tmp_path: Path, factory_run: Callable, launch: Callable
) -> None:
    port = free_base_port()
    first = launch(factory_run(), port)
    other = launch(tmp_path / "other-project" / ".factory", port)

    assert other["status"] == "started"
    assert other["url"] != first["url"]
    assert other["factory_present"] is False
    assert state_at(other["url"])["mode"] == "repo"


def test_a_map_for_a_different_factory_is_not_reused(tmp_path: Path) -> None:
    state = {"repo": {"path": ROOT.as_posix()}, "factory": {"path": "/elsewhere/.factory"}}

    assert open_map.serves_project(state, ROOT, tmp_path / ".factory") is False
    assert open_map.serves_project(None, ROOT, tmp_path / ".factory") is False
    state["factory"]["path"] = (tmp_path / ".factory").as_posix()
    assert open_map.serves_project(state, ROOT, tmp_path / ".factory") is True


def test_an_out_of_range_port_is_refused(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--no-browser", "--port", "70000",
         "--factory", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 1
    assert json.loads(completed.stdout)["error_code"] == "INVALID_PORT"

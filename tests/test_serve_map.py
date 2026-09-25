"""The server is read-only, loopback-only, and has exactly three routes.

These tests start the real server on an ephemeral port and speak HTTP to it,
rather than calling the handler directly, so the binding and the status codes
are the ones a browser would see.
"""

import importlib.util
import json
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "factory-map" / "scripts" / "serve_map.py"


def load_module():
    spec = importlib.util.spec_from_file_location("serve_map", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve_map = load_module()


@pytest.fixture
def server(factory_run: Callable) -> Iterator[dict[str, Any]]:
    """A running server bound to a free loopback port."""
    factory = factory_run()
    instance = serve_map.make_server(ROOT, factory, 0)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield {
            "url": f"http://127.0.0.1:{instance.server_address[1]}",
            "server": instance,
            "factory": factory,
        }
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=5)


def get(url: str, headers: dict[str, str] | None = None) -> tuple[int, bytes, Any]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers


def test_the_server_binds_the_loopback_interface_only(server: dict) -> None:
    assert server["server"].server_address[0] == "127.0.0.1"
    assert serve_map.HOST == "127.0.0.1"


def test_the_root_route_serves_the_page(server: dict) -> None:
    status, body, headers = get(server["url"] + "/")

    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    assert b"<title>Factory Map</title>" in body
    assert b"bootstrap-state" in body


def test_the_page_loads_nothing_from_the_network() -> None:
    """Everything is inline, so the page renders with no network at all."""
    page = (ROOT / "tools" / "factory-map" / "assets" / "index.html").read_text(encoding="utf-8")

    for marker in ("<link", "@import", "<script src", "url(http", "//cdn", "googleapis"):
        assert marker not in page, marker

    # The only absolute URL is the SVG namespace, which is an identifier and is
    # never fetched.
    urls = re.findall(r"https?://[^\s\"')]+", page)
    assert set(urls) == {"http://www.w3.org/2000/svg"}


# Properties of window that a classic script cannot redeclare at top level.
# A global `function top()` throws on load, and the whole map stays blank.
UNFORGEABLE_WINDOW_PROPERTIES = ("top", "window", "document", "location")


def test_the_page_script_declares_no_global_that_shadows_window() -> None:
    page = (ROOT / "tools" / "factory-map" / "assets" / "index.html").read_text(encoding="utf-8")
    names = "|".join(UNFORGEABLE_WINDOW_PROPERTIES)
    top_level_declaration = re.compile(
        rf"^(?:function|var|let|const|class)\s+({names})\b", re.MULTILINE
    )

    assert top_level_declaration.findall(page) == []


def test_the_state_route_serves_state_with_an_etag(server: dict) -> None:
    status, body, headers = get(server["url"] + "/api/state")
    state = json.loads(body)

    assert status == 200
    assert headers["Content-Type"].startswith("application/json")
    assert headers["ETag"] == '"' + state["fingerprint"] + '"'
    assert state["mode"] == "run"
    assert len(state["nodes"]) == 17


def test_an_unchanged_state_answers_not_modified(server: dict) -> None:
    _, _, headers = get(server["url"] + "/api/state")
    etag = headers["ETag"]

    status, body, _ = get(server["url"] + "/api/state", {"If-None-Match": etag})

    assert status == 304
    assert body == b""


def test_a_changed_artifact_changes_the_etag(
    server: dict, make_security_review: Callable
) -> None:
    _, _, headers = get(server["url"] + "/api/state")
    before = headers["ETag"]

    critical = make_security_review(
        "TASK-DEMO-010",
        status="findings",
        counts={"CRITICAL": 1, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
        requires_human_review=True,
    )
    path = server["factory"] / "tasks" / "TASK-DEMO-010" / "security.json"
    path.write_text(json.dumps(critical), encoding="utf-8")

    status, body, headers = get(server["url"] + "/api/state", {"If-None-Match": before})

    assert status == 200
    assert headers["ETag"] != before
    node = next(n for n in json.loads(body)["nodes"] if n["id"] == "security-review")
    assert node["run"]["status"] == "blocked"


def test_the_skill_route_serves_one_known_skill(server: dict) -> None:
    status, body, _ = get(server["url"] + "/api/skill/validate-change")
    payload = json.loads(body)

    assert status == 200
    assert payload["id"] == "validate-change"
    assert payload["purpose"]


def test_an_unknown_skill_name_is_rejected_without_touching_the_filesystem(
    server: dict,
) -> None:
    for name in ("nope", "..", "%2e%2e", "schemas", "validate-change.md"):
        status, _, _ = get(f"{server['url']}/api/skill/{name}")
        assert status == 404, name


def test_a_traversal_attempt_is_a_404(server: dict) -> None:
    for path in ("/api/skill/../../AGENTS.md", "/../AGENTS.md", "/assets/index.html"):
        status, _, _ = get(server["url"] + path)
        assert status == 404, path


def test_any_other_route_is_a_404(server: dict) -> None:
    status, body, _ = get(server["url"] + "/anything-else")

    assert status == 404
    assert json.loads(body)["error_code"] == "NOT_FOUND"


def test_serving_writes_nothing_to_the_repository_or_the_factory(server: dict) -> None:
    def listing(root: Path) -> dict[str, float]:
        return {
            path.as_posix(): path.stat().st_mtime
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    before = listing(server["factory"])
    get(server["url"] + "/")
    get(server["url"] + "/api/state")
    get(server["url"] + "/api/skill/plan-change")

    assert listing(server["factory"]) == before


def test_a_snapshot_inlines_the_state(tmp_path: Path, factory_run: Callable) -> None:
    out = tmp_path / "snapshot.html"
    exit_code = serve_map.main(
        [
            "--repo",
            str(ROOT),
            "--factory",
            str(factory_run()),
            "--once",
            "--out",
            str(out),
        ]
    )

    page = out.read_text(encoding="utf-8")

    assert exit_code == 0
    assert serve_map.BOOTSTRAP not in page
    assert '"mode": "run"' in page or '"mode":"run"' in page
    assert "validate-change" in page


def test_once_without_an_output_path_fails_with_a_reason(capsys: pytest.CaptureFixture) -> None:
    exit_code = serve_map.main(["--repo", str(ROOT), "--once"])

    assert exit_code == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == "MISSING_OUT"


def test_an_occupied_port_reports_a_reason_rather_than_a_traceback(
    server: dict, capsys: pytest.CaptureFixture
) -> None:
    port = server["server"].server_address[1]

    exit_code = serve_map.main(["--repo", str(ROOT), "--port", str(port)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["error_code"] == "PORT_IN_USE"
    assert str(port) in payload["message"]


def test_an_impossible_port_is_refused(capsys: pytest.CaptureFixture) -> None:
    exit_code = serve_map.main(["--repo", str(ROOT), "--port", "70000"])

    assert exit_code == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == "INVALID_PORT"


def test_the_script_runs_as_a_command_and_prints_its_address(tmp_path: Path) -> None:
    """The acceptance path: run it, see a loopback URL, stop it."""
    process = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--repo", str(ROOT), "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(tmp_path),
    )
    try:
        line = process.stdout.readline().strip()
        assert line.startswith("http://127.0.0.1:")
        status, body, _ = get(line + "/api/state")
        assert status == 200
        assert json.loads(body)["mode"] == "repo"
    finally:
        process.terminate()
        process.wait(timeout=10)

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "installer" / "scripts" / "install_skill.py"
SKILL = "my-software-factory"


def run_installer(*args: str, env: dict[str, str] | None = None) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, json.loads(result.stdout)


def test_installs_the_skill_folder_with_the_rules(tmp_path: Path) -> None:
    code, result = run_installer("--skills-dir", str(tmp_path))

    assert code == 0, result
    assert result["status"] == "installed"
    assert result["installs"][0]["action"] == "created"

    installed = tmp_path / SKILL
    skill_dir = ROOT / "my-software-factory"
    source_files = sorted(
        path.relative_to(skill_dir)
        for path in skill_dir.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    installed_files = sorted(
        path.relative_to(installed)
        for path in installed.rglob("*")
        if path.is_file() and path.name not in {"AGENTS.md", "LICENSE", ".install.json"}
    )
    assert installed_files == source_files
    assert len(list(installed.glob("stages/*/*/SKILL.md"))) == 17
    assert (installed / "AGENTS.md").read_text(encoding="utf-8") == (
        (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    )
    assert (installed / "LICENSE").is_file()

    for excluded in ("tests", "tools", "docs", ".github", "pyproject.toml", "README.md"):
        assert not (installed / excluded).exists(), excluded
    assert not list(installed.rglob("__pycache__"))

    manifest = json.loads((installed / ".install.json").read_text(encoding="utf-8"))
    assert manifest["skill"] == SKILL
    assert manifest["source"] == str(ROOT)


def test_refuses_to_overwrite_without_replace(tmp_path: Path) -> None:
    run_installer("--skills-dir", str(tmp_path))
    marker = tmp_path / SKILL / "local-note.md"
    marker.write_text("keep me", encoding="utf-8")

    code, result = run_installer("--skills-dir", str(tmp_path))

    assert code == 1
    assert result["error_code"] == "DESTINATION_EXISTS"
    assert marker.read_text(encoding="utf-8") == "keep me"


def test_replace_swaps_a_previous_install(tmp_path: Path) -> None:
    run_installer("--skills-dir", str(tmp_path))
    stale = tmp_path / SKILL / "stale-stage" / "SKILL.md"
    stale.parent.mkdir()
    stale.write_text("old", encoding="utf-8")

    code, result = run_installer("--skills-dir", str(tmp_path), "--replace")

    assert code == 0, result
    assert result["installs"][0]["action"] == "replaced"
    assert not stale.exists()
    assert (tmp_path / SKILL / "SKILL.md").is_file()
    assert [path.name for path in tmp_path.iterdir()] == [SKILL]


def test_replace_refuses_a_directory_that_is_not_this_skill(tmp_path: Path) -> None:
    foreign = tmp_path / SKILL
    foreign.mkdir()
    (foreign / "SKILL.md").write_text("---\nname: something-else\n---\n", encoding="utf-8")

    code, result = run_installer("--skills-dir", str(tmp_path), "--replace")

    assert code == 1
    assert result["error_code"] == "DESTINATION_NOT_THIS_SKILL"
    assert (foreign / "SKILL.md").read_text(encoding="utf-8").startswith("---\nname: something")


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    code, result = run_installer("--skills-dir", str(tmp_path / "skills"), "--dry-run")

    assert code == 0, result
    assert result["status"] == "dry_run"
    assert result["installs"][0]["action"] == "would_create"
    assert result["installs"][0]["payload_files"] > 0
    assert not (tmp_path / "skills").exists()


def test_default_targets_follow_agent_home_variables(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "claude")
    env["CODEX_HOME"] = str(tmp_path / "codex")

    code, result = run_installer(env=env)

    assert code == 0, result
    assert [install["target"] for install in result["installs"]] == ["claude", "codex"]
    assert (tmp_path / "claude" / "skills" / SKILL / "SKILL.md").is_file()
    assert (tmp_path / "codex" / "skills" / SKILL / "SKILL.md").is_file()


def test_one_refusal_blocks_every_target(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "claude")
    env["CODEX_HOME"] = str(tmp_path / "codex")
    (tmp_path / "codex" / "skills" / SKILL).mkdir(parents=True)

    code, result = run_installer(env=env)

    assert code == 1
    assert result["error_code"] == "DESTINATION_EXISTS"
    assert not (tmp_path / "claude" / "skills" / SKILL).exists()


def test_refuses_to_install_inside_the_source(tmp_path: Path) -> None:
    code, result = run_installer("--skills-dir", str(ROOT), "--dry-run")

    assert code == 1
    assert result["error_code"] == "DESTINATION_OVERLAPS_SOURCE"


def test_reports_but_keeps_a_legacy_install(tmp_path: Path) -> None:
    legacy = tmp_path / "software-factory-gpt"
    legacy.mkdir()
    (legacy / "SKILL.md").write_text("---\nname: software-factory-gpt\n---\n", encoding="utf-8")

    code, result = run_installer("--skills-dir", str(tmp_path))

    assert code == 0, result
    assert result["installs"][0]["legacy_installs"] == [str(legacy)]
    assert (legacy / "SKILL.md").is_file()

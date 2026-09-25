import re
from pathlib import Path


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "---"
    closing_index = lines[1:].index("---") + 1

    metadata: dict[str, str] = {}
    for line in lines[1:closing_index]:
        key, separator, value = line.partition(":")
        assert separator == ":", f"Invalid frontmatter line in {path}: {line}"
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def test_skill_frontmatter_is_present_and_matches_directory() -> None:
    root = Path(__file__).resolve().parents[1]
    skill_paths = sorted(root.glob("my-software-factory/stages/*/*/SKILL.md"))
    by_phase: dict[str, list[str]] = {}
    for path in skill_paths:
        by_phase.setdefault(path.parent.parent.name, []).append(path.parent.name)

    assert by_phase == {
        "engineering": [
            "before-after",
            "completion-report",
            "create-pull-request",
            "implement-change",
            "inspect-repository",
            "isolate-task",
            "plan-change",
            "review-pull-request",
            "revise-pull-request",
            "security-review",
            "update-documentation",
            "validate-change",
        ],
        "intake": [
            "clarify-project",
            "decompose-spec",
            "ingest-requirements",
            "prepare-task",
            "start-from-spec",
        ],
    }
    # The skill is one folder: its router is the only SKILL.md outside stages/.
    assert sorted(path.parent.name for path in root.glob("*/SKILL.md")) == ["my-software-factory"]
    assert not (root / "SKILL.md").exists()

    for path in skill_paths:
        metadata = parse_frontmatter(path)
        assert metadata["name"] == path.parent.name
        assert metadata["description"]


# Claude Code and Codex both load a skill from the SKILL.md at the top of its
# folder. Codex's validator is the stricter of the two, so the router's
# frontmatter is held to it.
SKILL_DIR = Path(__file__).resolve().parents[1] / "my-software-factory"
PORTABLE_FRONTMATTER_KEYS = {"name", "description", "license", "allowed-tools", "metadata"}


def test_root_skill_frontmatter_is_portable() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "---"
    frontmatter = lines[1 : lines[1:].index("---") + 1]

    top_level = {line.partition(":")[0] for line in frontmatter if not line.startswith(" ")}
    assert top_level <= PORTABLE_FRONTMATTER_KEYS

    metadata = parse_frontmatter(SKILL_DIR / "SKILL.md")
    assert metadata["name"] == "my-software-factory"
    description = metadata["description"]
    assert description
    assert len(description) <= 1024
    assert "<" not in description and ">" not in description


def test_root_skill_names_only_paths_that_exist() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    path_pattern = r"`([a-z-]+/(?:[a-z-]+/)*[A-Za-z_.-]+\.(?:md|py|json|yaml))`"
    referenced = set(re.findall(path_pattern, text))

    assert "stages/engineering/inspect-repository/SKILL.md" in referenced
    missing = sorted(path for path in referenced if not (SKILL_DIR / path).is_file())
    assert missing == []


def test_codex_interface_metadata_names_the_skill() -> None:
    fields = {}
    for line in (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.strip().partition(":")
        if separator and value.strip():
            fields[key] = value.strip().strip('"')

    assert fields["display_name"]
    assert 25 <= len(fields["short_description"]) <= 64
    assert "$my-software-factory" in fields["default_prompt"]

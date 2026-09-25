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
    skill_paths = sorted(root.glob("*/SKILL.md"))
    assert [path.parent.name for path in skill_paths] == [
        "before-after",
        "clarify-project",
        "completion-report",
        "create-pull-request",
        "decompose-spec",
        "implement-change",
        "ingest-requirements",
        "inspect-repository",
        "isolate-task",
        "plan-change",
        "prepare-task",
        "review-pull-request",
        "revise-pull-request",
        "security-review",
        "start-from-spec",
        "update-documentation",
        "validate-change",
    ]

    for path in skill_paths:
        metadata = parse_frontmatter(path)
        assert metadata["name"] == path.parent.name
        assert metadata["description"]


# Claude Code and Codex both load a skill from its root SKILL.md. Codex's
# validator is the stricter of the two, so the root frontmatter is held to it.
PORTABLE_FRONTMATTER_KEYS = {"name", "description", "license", "allowed-tools", "metadata"}


def test_root_skill_frontmatter_is_portable() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "---"
    frontmatter = lines[1 : lines[1:].index("---") + 1]

    top_level = {line.partition(":")[0] for line in frontmatter if not line.startswith(" ")}
    assert top_level <= PORTABLE_FRONTMATTER_KEYS

    metadata = parse_frontmatter(root / "SKILL.md")
    assert metadata["name"] == "software-factory-gpt"
    description = metadata["description"]
    assert description
    assert len(description) <= 1024
    assert "<" not in description and ">" not in description


def test_root_skill_names_only_paths_that_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "SKILL.md").read_text(encoding="utf-8")
    path_pattern = r"`([a-z-]+/(?:[a-z-]+/)*[A-Za-z_.-]+\.(?:md|py|json|yaml))`"
    referenced = set(re.findall(path_pattern, text))

    assert "inspect-repository/SKILL.md" in referenced
    missing = sorted(path for path in referenced if not (root / path).is_file())
    assert missing == []


def test_codex_interface_metadata_names_the_skill() -> None:
    root = Path(__file__).resolve().parents[1]
    fields = {}
    for line in (root / "agents" / "openai.yaml").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.strip().partition(":")
        if separator and value.strip():
            fields[key] = value.strip().strip('"')

    assert fields["display_name"]
    assert 25 <= len(fields["short_description"]) <= 64
    assert "$software-factory-gpt" in fields["default_prompt"]

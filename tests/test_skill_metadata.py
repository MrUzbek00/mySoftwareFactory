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
    ]

    for path in skill_paths:
        metadata = parse_frontmatter(path)
        assert metadata["name"] == path.parent.name
        assert metadata["description"]

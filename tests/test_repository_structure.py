from pathlib import Path

REQUIRED_PATHS = [
    "README.md",
    "AGENTS.md",
    "LICENSE",
    "pyproject.toml",
    ".gitignore",
    ".editorconfig",
    ".github/workflows/ci.yml",
    "inspect-repository/SKILL.md",
    "inspect-repository/references/repository-analysis.md",
    "plan-change/SKILL.md",
    "plan-change/references/planning-guidelines.md",
    "isolate-task/SKILL.md",
    "isolate-task/scripts/create_worktree.py",
    "isolate-task/references/git-isolation.md",
    "schemas/repository-context.schema.json",
    "schemas/change-plan.schema.json",
    "schemas/workspace-result.schema.json",
    "examples/sample-task.md",
    "tests/test_repository_structure.py",
    "tests/test_skill_metadata.py",
    "tests/test_json_schemas.py",
    "tests/test_create_worktree.py",
]


def test_required_repository_paths_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    missing = [path for path in REQUIRED_PATHS if not (root / path).exists()]
    assert missing == []

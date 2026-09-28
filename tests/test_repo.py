"""Repository-level rules: layering, dependencies, document tables, hygiene."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tomllib

from tests.helpers import REPO_ROOT

FORBIDDEN_IN_ENGINE = ("tools", "crosscheck", "ec3", "tests")


def test_engine_imports_only_stdlib_and_itself():
    stdlib = set(sys.stdlib_module_names)
    for path in (REPO_ROOT / "section_properties").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for name in names:
                top = name.split(".")[0]
                assert top not in FORBIDDEN_IN_ENGINE, f"{path.name} imports {name} (layer rule)"
                assert top in stdlib or top == "section_properties" or top == "__future__", f"{path.name} imports {name}"


def test_no_runtime_dependencies_and_canonical_environment_declared():
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    assert pyproject["project"]["dependencies"] == []
    assert pyproject["project"]["requires-python"] == ">=3.11"
    canonical = pyproject["tool"]["steel_section_database"]
    assert canonical["canonical_python"] and canonical["canonical_platform"]


def test_markdown_tables_are_well_formed():
    """GitHub renders a table only if header and delimiter rows have the same number of cells."""

    def cells(line: str) -> int:
        return len(re.split(r"(?<!\\)\|", line.strip().strip("|")))

    paths = [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").glob("*.md"))]
    for path in paths:
        lines = path.read_text(encoding="utf-8").splitlines()
        for index in range(1, len(lines)):
            if re.fullmatch(r"\|?(\s*:?-+:?\s*\|)+\s*:?-*:?\s*\|?", lines[index].strip()) and lines[index - 1].lstrip().startswith("|"):
                # a table must not continue a paragraph line directly (GitHub would not render it)
                assert index < 2 or not lines[index - 2].strip() or lines[index - 2].lstrip().startswith("|") or lines[index - 2].lstrip().startswith("#"), (
                    f"{path.name}:{index - 1}: table must be preceded by an empty line"
                )
                assert cells(lines[index - 1]) == cells(lines[index]), f"{path.name}:{index}: header/delimiter cell count"


def test_no_secrets_or_nested_repositories():
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    assert not any(line.split("/")[-1] == ".env" or line.endswith(".env") for line in tracked.splitlines())
    assert not [p for p in REPO_ROOT.rglob(".git") if p.parent != REPO_ROOT and ".venv" not in p.parts]

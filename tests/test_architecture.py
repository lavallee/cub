"""
Tests for architectural boundaries and constraints.

This module enforces critical design constraints:
- Rich UI framework is NOT imported in core business logic
- Core modules are UI-agnostic and can be used in any interface
- CLI layer (presentation) isolates Rich dependencies from core (logic)

These constraints ensure:
1. Core can be consumed by multiple interfaces (CLI, Web, API, etc.)
2. Core remains testable without UI dependencies
3. Clean separation of concerns between logic and presentation
"""

import ast
import sys
from pathlib import Path


class RichImportChecker(ast.NodeVisitor):
    """AST visitor that detects Rich imports in Python source code."""

    def __init__(self) -> None:
        """Initialize the checker."""
        self.rich_imports: list[tuple[int, str]] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check 'from rich ...' imports."""
        if node.module and node.module.startswith("rich"):
            for alias in node.names:
                import_name = f"from {node.module} import {alias.name}"
                self.rich_imports.append((node.lineno, import_name))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Check 'import rich' imports."""
        for alias in node.names:
            if alias.name.startswith("rich"):
                import_name = f"import {alias.name}"
                self.rich_imports.append((node.lineno, import_name))
        self.generic_visit(node)


def find_python_files(directory: Path) -> list[Path]:
    """Recursively find all Python files in a directory."""
    return sorted(directory.rglob("*.py"))


def check_file_for_rich_imports(file_path: Path) -> list[tuple[int, str]]:
    """
    Check a single Python file for Rich imports.

    Args:
        file_path: Path to the Python file to check

    Returns:
        List of (line_number, import_statement) tuples for Rich imports found
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        checker = RichImportChecker()
        checker.visit(tree)
        return checker.rich_imports
    except (SyntaxError, OSError):
        # If we can't parse the file, return empty (tests shouldn't fail on syntax)
        return []


def test_no_rich_imports_in_core() -> None:
    """
    Verify that no Rich imports exist in core modules.

    This is a critical architectural constraint: the core business logic layer
    must remain independent of the Rich UI framework so that multiple interfaces
    (CLI, Web, API, etc.) can use core without forcing Rich as a dependency.

    This test scans all Python files in src/cub/core and verifies:
    - No 'from rich' imports
    - No 'import rich' imports

    If this test fails, it indicates that core modules have been coupled to
    Rich, violating the architectural boundary. The fix is to:
    1. Move Rich-using code to cli/ layer
    2. Have core expose plain data structures (strings, dicts, objects)
    3. Have CLI layer format and render those structures using Rich

    CI will fail if Rich imports appear in core, preventing regression.
    """
    core_dir = Path(__file__).parent.parent / "src" / "cub" / "core"
    assert core_dir.exists(), f"Core directory not found: {core_dir}"

    python_files = find_python_files(core_dir)
    assert len(python_files) > 0, f"No Python files found in {core_dir}"

    violations: dict[Path, list[tuple[int, str]]] = {}

    for file_path in python_files:
        rich_imports = check_file_for_rich_imports(file_path)
        if rich_imports:
            violations[file_path] = rich_imports

    if violations:
        error_message = (
            "❌ Rich imports found in core modules (architectural boundary violation):\n\n"
        )
        for file_path, imports in sorted(violations.items()):
            rel_path = file_path.relative_to(core_dir.parent.parent)
            error_message += f"{rel_path}:\n"
            for line_num, import_stmt in imports:
                error_message += f"  Line {line_num}: {import_stmt}\n"
            error_message += "\n"

        error_message += (
            "Core must not import Rich. Move Rich usage to cli/ layer.\n"
            "Core should return plain data; CLI renders it with Rich."
        )

        raise AssertionError(error_message)


def test_rich_imports_not_in_core_cli() -> None:
    """
    Verify the boundary: Rich imports are OK in CLI, but NOT in core.

    This secondary check helps developers understand where Rich is allowed:
    - ✅ CLI layer (cub.cli.*) - can use Rich
    - ❌ Core layer (cub.core.*) - must NOT use Rich
    - ⚠️  Dashboard module - can use Rich (it's UI-focused)

    This test documents the expected architecture without failing (since
    CLI legitimately uses Rich). The primary enforcement is in
    test_no_rich_imports_in_core above.
    """
    core_dir = Path(__file__).parent.parent / "src" / "cub" / "core"
    cli_dir = Path(__file__).parent.parent / "src" / "cub" / "cli"

    # Core should have no Rich imports
    core_files = find_python_files(core_dir)
    core_violations = {}
    for file_path in core_files:
        rich_imports = check_file_for_rich_imports(file_path)
        if rich_imports:
            core_violations[file_path] = rich_imports

    assert (
        not core_violations
    ), f"Core must not import Rich. Found violations: {core_violations}"

    # CLI can (and does) have Rich imports - just verify it exists
    assert cli_dir.exists(), f"CLI directory not found: {cli_dir}"
    cli_files = find_python_files(cli_dir)
    assert len(cli_files) > 0, f"No Python files found in {cli_dir}"


if __name__ == "__main__":
    # Allow running tests directly
    test_no_rich_imports_in_core()
    test_rich_imports_not_in_core_cli()
    print("✓ All architecture tests passed!")
    sys.exit(0)

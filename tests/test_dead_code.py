"""
Tests for dead code detection module.
"""

from pathlib import Path

import pytest

from cub.audit import detect_unused, find_python_definitions, find_python_references


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a sample project with various dead code patterns."""
    project = tmp_path / "sample_project"
    project.mkdir()

    # Module with unused imports
    (project / "module_a.py").write_text(
        """\
import os
import sys  # unused
from typing import Dict  # unused
from pathlib import Path

def use_path():
    return Path("/tmp")

# os is used here
home = os.getenv("HOME")
"""
    )

    # Module with unused functions
    (project / "module_b.py").write_text(
        """\
def used_function():
    return "used"

def unused_function():  # dead code
    return "unused"

result = used_function()
"""
    )

    # Module with unused class
    (project / "module_c.py").write_text(
        """\
class UsedClass:
    def method(self):
        return "used"

class UnusedClass:  # dead code
    def method(self):
        return "unused"

obj = UsedClass()
"""
    )

    # Module with __all__ exports (should exclude from dead code)
    (project / "module_d.py").write_text(
        """\
__all__ = ["public_function", "PublicClass"]

def public_function():
    return "exported"

def private_function():  # Not in __all__ but not referenced
    return "private"

class PublicClass:
    pass

class PrivateClass:  # Not in __all__ but not referenced
    pass
"""
    )

    # Module with magic methods (should exclude)
    (project / "module_e.py").write_text(
        """\
class MyClass:
    def __init__(self):
        pass

    def __str__(self):
        return "MyClass"

    def unused_method(self):  # dead code
        pass

obj = MyClass()
"""
    )

    # Module with unused variables
    (project / "module_f.py").write_text(
        """\
USED_CONSTANT = 42
UNUSED_CONSTANT = 99  # dead code

def function():
    return USED_CONSTANT
"""
    )

    return project


def test_find_python_definitions_imports(tmp_path: Path) -> None:
    """Test finding import definitions."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """\
import os
import sys as system
from pathlib import Path
from typing import Dict as DictType
"""
    )

    definitions = find_python_definitions(test_file)
    names = {d.name for d in definitions}

    assert "os" in names
    assert "system" in names  # aliased import
    assert "Path" in names
    assert "DictType" in names  # aliased import
    assert all(d.kind == "import" for d in definitions)


def test_find_python_definitions_functions(tmp_path: Path) -> None:
    """Test finding function definitions."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """\
def function_a():
    pass

async def async_function():
    pass

class MyClass:
    def method(self):
        pass
"""
    )

    definitions = find_python_definitions(test_file)
    func_defs = {d.name: d.kind for d in definitions}

    assert func_defs["function_a"] == "function"
    assert func_defs["async_function"] == "function"
    assert func_defs["method"] == "method"
    assert func_defs["MyClass"] == "class"


def test_find_python_definitions_classes(tmp_path: Path) -> None:
    """Test finding class definitions."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """\
class ClassA:
    pass

class ClassB:
    def method(self):
        pass
"""
    )

    definitions = find_python_definitions(test_file)
    class_defs = [d for d in definitions if d.kind == "class"]

    assert len(class_defs) == 2
    assert {d.name for d in class_defs} == {"ClassA", "ClassB"}


def test_find_python_definitions_variables(tmp_path: Path) -> None:
    """Test finding module-level variable definitions."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """\
MODULE_CONSTANT = 42
another_var = "test"

class MyClass:
    class_var = 100
"""
    )

    definitions = find_python_definitions(test_file)
    var_defs = [d for d in definitions if d.kind == "variable"]

    names = {d.name for d in var_defs}
    assert "MODULE_CONSTANT" in names
    assert "another_var" in names
    assert "class_var" in names


def test_find_python_references(tmp_path: Path) -> None:
    """Test finding name references."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """\
import os

def function():
    path = os.path.join("/tmp", "file")
    return path

result = function()
"""
    )

    references = find_python_references(test_file)

    assert "os" in references
    assert "function" in references
    # path is assigned, not just referenced in Load context


def test_detect_unused_imports(sample_project: Path) -> None:
    """Test detection of unused imports."""
    report = detect_unused(sample_project)

    # Find unused imports in module_a
    module_a_findings = [
        f for f in report.findings if "module_a.py" in f.file_path and f.kind == "import"
    ]

    unused_names = {f.name for f in module_a_findings}
    assert "sys" in unused_names
    assert "Dict" in unused_names
    # os and Path should NOT be in unused (they are used)
    assert "os" not in unused_names
    assert "Path" not in unused_names


def test_detect_unused_functions(sample_project: Path) -> None:
    """Test detection of unused functions."""
    report = detect_unused(sample_project)

    # Find unused functions in module_b
    module_b_findings = [
        f for f in report.findings if "module_b.py" in f.file_path and f.kind == "function"
    ]

    unused_names = {f.name for f in module_b_findings}
    assert "unused_function" in unused_names
    assert "used_function" not in unused_names


def test_detect_unused_classes(sample_project: Path) -> None:
    """Test detection of unused classes."""
    report = detect_unused(sample_project)

    # Find unused classes in module_c
    module_c_findings = [
        f for f in report.findings if "module_c.py" in f.file_path and f.kind == "class"
    ]

    unused_names = {f.name for f in module_c_findings}
    assert "UnusedClass" in unused_names
    assert "UsedClass" not in unused_names


def test_respect_all_exports(sample_project: Path) -> None:
    """Test that __all__ exports are excluded from dead code detection."""
    report = detect_unused(sample_project)

    # Find findings in module_d
    module_d_findings = [f for f in report.findings if "module_d.py" in f.file_path]

    # Public exports should NOT be flagged
    public_names = {f.name for f in module_d_findings}
    assert "public_function" not in public_names
    assert "PublicClass" not in public_names

    # Private items not in __all__ should be flagged
    assert "private_function" in public_names
    assert "PrivateClass" in public_names


def test_exclude_magic_methods(sample_project: Path) -> None:
    """Test that magic methods are excluded from dead code detection."""
    report = detect_unused(sample_project)

    # Find findings in module_e
    module_e_findings = [f for f in report.findings if "module_e.py" in f.file_path]

    # Magic methods should NOT be flagged
    magic_names = {f.name for f in module_e_findings}
    assert "__init__" not in magic_names
    assert "__str__" not in magic_names

    # Regular unused methods should be flagged
    assert "unused_method" in magic_names


def test_detect_unused_variables(sample_project: Path) -> None:
    """Test detection of unused module-level variables."""
    report = detect_unused(sample_project)

    # Find unused variables in module_f
    module_f_findings = [
        f for f in report.findings if "module_f.py" in f.file_path and f.kind == "variable"
    ]

    unused_names = {f.name for f in module_f_findings}
    assert "UNUSED_CONSTANT" in unused_names
    assert "USED_CONSTANT" not in unused_names


def test_exclude_patterns(sample_project: Path) -> None:
    """Test that exclude patterns work correctly."""
    # Create a test file that should be excluded
    (sample_project / "test_module.py").write_text(
        """\
def unused_test_function():
    pass
"""
    )

    report = detect_unused(sample_project, exclude_patterns=["**/test_*.py"])

    # test_module.py should not appear in findings
    test_findings = [f for f in report.findings if "test_module.py" in f.file_path]
    assert len(test_findings) == 0


def test_report_has_findings(sample_project: Path) -> None:
    """Test DeadCodeReport.has_findings property."""
    report = detect_unused(sample_project)
    assert report.has_findings is True

    # Create empty project
    empty_project = sample_project / "empty"
    empty_project.mkdir()
    (empty_project / "empty.py").write_text("# Nothing here\n")

    empty_report = detect_unused(empty_project)
    assert empty_report.has_findings is False


def test_report_findings_by_kind(sample_project: Path) -> None:
    """Test DeadCodeReport.findings_by_kind property."""
    report = detect_unused(sample_project)
    by_kind = report.findings_by_kind

    # Should have various kinds of findings
    assert "import" in by_kind
    assert "function" in by_kind
    assert "class" in by_kind
    assert by_kind["import"] > 0
    assert by_kind["function"] > 0
    assert by_kind["class"] > 0


def test_syntax_error_handling(tmp_path: Path) -> None:
    """Test that files with syntax errors are skipped gracefully."""
    project = tmp_path / "bad_syntax"
    project.mkdir()

    # File with syntax error
    (project / "bad.py").write_text("def function(\n")  # incomplete

    # File with valid syntax
    (project / "good.py").write_text("def unused():\n    pass\n")

    # Should not raise, should process the good file
    report = detect_unused(project)

    assert report.files_scanned == 1  # Only the good file
    assert report.has_findings is True  # unused function in good.py


def test_line_numbers(tmp_path: Path) -> None:
    """Test that line numbers are correctly reported."""
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """\
# Line 1: comment
import unused_import  # Line 2

def unused_function():  # Line 4
    pass

class UnusedClass:  # Line 7
    pass
"""
    )

    report = detect_unused(tmp_path)

    findings_by_name = {f.name: f.line_number for f in report.findings}
    assert findings_by_name["unused_import"] == 2
    assert findings_by_name["unused_function"] == 4
    assert findings_by_name["UnusedClass"] == 7


def test_empty_project(tmp_path: Path) -> None:
    """Test detection on empty project."""
    empty_project = tmp_path / "empty"
    empty_project.mkdir()

    report = detect_unused(empty_project)

    assert report.files_scanned == 0
    assert report.total_definitions == 0
    assert len(report.findings) == 0
    assert report.has_findings is False

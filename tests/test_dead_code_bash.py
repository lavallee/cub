"""
Tests for Bash dead code detection module.
"""

from pathlib import Path

import pytest

from cub.audit import (
    detect_unused_bash,
    find_bash_calls,
    find_bash_functions,
    run_shellcheck,
)


@pytest.fixture
def sample_bash_project(tmp_path: Path) -> Path:
    """Create a sample project with Bash scripts."""
    project = tmp_path / "bash_project"
    project.mkdir()

    # Script with unused function (style: function_name() {)
    (project / "script_a.sh").write_text(
        """\
#!/usr/bin/env bash

used_function() {
    echo "This is used"
}

unused_function() {
    echo "This is never called"
}

# Main execution
used_function
"""
    )

    # Script with unused function (style: function function_name() {)
    (project / "script_b.sh").write_text(
        """\
#!/usr/bin/env bash

function used_func() {
    echo "Used"
}

function unused_func() {
    echo "Unused"
}

used_func
"""
    )

    # Script with unused function (style: function function_name {)
    (project / "script_c.sh").write_text(
        """\
#!/usr/bin/env bash

function used_no_parens {
    echo "Used"
}

function unused_no_parens {
    echo "Unused"
}

used_no_parens
"""
    )

    # Script with sourcing and cross-file calls
    (project / "library.sh").write_text(
        """\
#!/usr/bin/env bash

library_function() {
    echo "Library function"
}

unused_library_function() {
    echo "Unused in library"
}
"""
    )

    (project / "main.sh").write_text(
        """\
#!/usr/bin/env bash

source "$(dirname "${BASH_SOURCE[0]}")/library.sh"

main() {
    library_function
}

main
"""
    )

    # Script with functions called in various contexts
    (project / "complex.sh").write_text(
        """\
#!/usr/bin/env bash

function_in_pipe() {
    echo "piped"
}

function_in_command_sub() {
    echo "substituted"
}

function_in_condition() {
    return 0
}

unused_complex() {
    echo "never called"
}

# Various call patterns
echo "test" | function_in_pipe
result=$(function_in_command_sub)
if function_in_condition; then
    echo "ok"
fi
"""
    )

    return project


def test_find_bash_functions_style1(tmp_path: Path) -> None:
    """Test finding Bash functions with style: function_name() {"""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

function_a() {
    echo "a"
}

function_b() {
    echo "b"
}
"""
    )

    definitions = find_bash_functions(test_file)
    names = {d.name for d in definitions}

    assert "function_a" in names
    assert "function_b" in names
    assert len(definitions) == 2


def test_find_bash_functions_style2(tmp_path: Path) -> None:
    """Test finding Bash functions with style: function function_name() {"""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

function function_a() {
    echo "a"
}

function function_b() {
    echo "b"
}
"""
    )

    definitions = find_bash_functions(test_file)
    names = {d.name for d in definitions}

    assert "function_a" in names
    assert "function_b" in names
    assert len(definitions) == 2


def test_find_bash_functions_style3(tmp_path: Path) -> None:
    """Test finding Bash functions with style: function function_name {"""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

function function_a {
    echo "a"
}

function function_b {
    echo "b"
}
"""
    )

    definitions = find_bash_functions(test_file)
    names = {d.name for d in definitions}

    assert "function_a" in names
    assert "function_b" in names
    assert len(definitions) == 2


def test_find_bash_functions_mixed_styles(tmp_path: Path) -> None:
    """Test finding Bash functions with mixed styles."""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

func_a() {
    echo "a"
}

function func_b() {
    echo "b"
}

function func_c {
    echo "c"
}
"""
    )

    definitions = find_bash_functions(test_file)
    names = {d.name for d in definitions}

    assert "func_a" in names
    assert "func_b" in names
    assert "func_c" in names
    assert len(definitions) == 3


def test_find_bash_functions_with_line_numbers(tmp_path: Path) -> None:
    """Test that line numbers are correctly reported."""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash
# Line 2: comment

func_a() {
    echo "a"
}

# Line 8: comment
function func_b() {
    echo "b"
}
"""
    )

    definitions = find_bash_functions(test_file)
    func_lines = {d.name: d.line_number for d in definitions}

    assert func_lines["func_a"] == 4
    assert func_lines["func_b"] == 9


def test_find_bash_calls_basic(tmp_path: Path) -> None:
    """Test finding basic Bash function calls."""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

my_function() {
    echo "test"
}

# Call the function
my_function
"""
    )

    calls = find_bash_calls(test_file)

    assert "my_function" in calls


def test_find_bash_calls_in_pipe(tmp_path: Path) -> None:
    """Test finding function calls in pipes."""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

process_data() {
    echo "processed"
}

echo "data" | process_data
"""
    )

    calls = find_bash_calls(test_file)

    assert "process_data" in calls


def test_find_bash_calls_in_command_substitution(tmp_path: Path) -> None:
    """Test finding function calls in command substitution."""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

get_value() {
    echo "value"
}

result=$(get_value)
"""
    )

    calls = find_bash_calls(test_file)

    assert "get_value" in calls


def test_find_bash_calls_excludes_keywords(tmp_path: Path) -> None:
    """Test that Bash keywords are not included in calls."""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

if [ -f file.txt ]; then
    echo "exists"
fi

for item in list; do
    echo "$item"
done
"""
    )

    calls = find_bash_calls(test_file)

    # Keywords should not be in calls
    assert "if" not in calls
    assert "then" not in calls
    assert "fi" not in calls
    assert "for" not in calls
    assert "do" not in calls
    assert "done" not in calls


def test_find_bash_calls_excludes_builtins(tmp_path: Path) -> None:
    """Test that common Bash builtins are not included in calls."""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

echo "test"
printf "formatted"
cd /tmp
source other.sh
"""
    )

    calls = find_bash_calls(test_file)

    # Builtins should not be in calls
    assert "echo" not in calls
    assert "printf" not in calls
    assert "cd" not in calls
    assert "source" not in calls


def test_detect_unused_bash_basic(sample_bash_project: Path) -> None:
    """Test basic unused Bash function detection."""
    report = detect_unused_bash(sample_bash_project)

    # Find unused functions in script_a
    script_a_findings = [
        f for f in report.findings if "script_a.sh" in f.file_path and f.kind == "bash_function"
    ]

    unused_names = {f.name for f in script_a_findings}
    assert "unused_function" in unused_names
    assert "used_function" not in unused_names


def test_detect_unused_bash_all_styles(sample_bash_project: Path) -> None:
    """Test unused detection works for all function declaration styles."""
    report = detect_unused_bash(sample_bash_project)

    # Check script_b (function keyword with parens)
    script_b_findings = [f for f in report.findings if "script_b.sh" in f.file_path]
    script_b_names = {f.name for f in script_b_findings}
    assert "unused_func" in script_b_names
    assert "used_func" not in script_b_names

    # Check script_c (function keyword without parens)
    script_c_findings = [f for f in report.findings if "script_c.sh" in f.file_path]
    script_c_names = {f.name for f in script_c_findings}
    assert "unused_no_parens" in script_c_names
    assert "used_no_parens" not in script_c_names


def test_detect_unused_bash_cross_file_calls(sample_bash_project: Path) -> None:
    """Test that cross-file function calls are detected."""
    report = detect_unused_bash(sample_bash_project)

    # library_function is called in main.sh, should not be unused
    library_findings = [f for f in report.findings if "library.sh" in f.file_path]
    library_names = {f.name for f in library_findings}

    # library_function is called from main.sh
    assert "library_function" not in library_names

    # unused_library_function is never called
    assert "unused_library_function" in library_names


def test_detect_unused_bash_complex_calls(sample_bash_project: Path) -> None:
    """Test detection of functions called in various contexts."""
    report = detect_unused_bash(sample_bash_project)

    complex_findings = [f for f in report.findings if "complex.sh" in f.file_path]
    complex_names = {f.name for f in complex_findings}

    # Functions called in different contexts should not be flagged
    assert "function_in_pipe" not in complex_names
    assert "function_in_command_sub" not in complex_names
    assert "function_in_condition" not in complex_names

    # Unused function should be flagged
    assert "unused_complex" in complex_names


def test_detect_unused_bash_exclude_patterns(sample_bash_project: Path) -> None:
    """Test that exclude patterns work correctly."""
    # Create a test script that should be excluded
    (sample_bash_project / "test_script.sh").write_text(
        """\
#!/usr/bin/env bash

unused_test_function() {
    echo "never called"
}
"""
    )

    report = detect_unused_bash(sample_bash_project, exclude_patterns=["**/test_*.sh"])

    # test_script.sh should not appear in findings
    test_findings = [f for f in report.findings if "test_script.sh" in f.file_path]
    assert len(test_findings) == 0


def test_run_shellcheck_not_installed(tmp_path: Path) -> None:
    """Test that run_shellcheck gracefully handles missing shellcheck."""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

unused_function() {
    echo "unused"
}
"""
    )

    # Should return empty list if shellcheck not available (or just no warnings)
    warnings = run_shellcheck(test_file)

    # Should be a list (empty or with warnings, depending on shellcheck availability)
    assert isinstance(warnings, list)


def test_detect_unused_bash_line_numbers(tmp_path: Path) -> None:
    """Test that line numbers are correctly reported in findings."""
    project = tmp_path / "project"
    project.mkdir()

    (project / "test.sh").write_text(
        """\
#!/usr/bin/env bash
# Line 2: comment

unused_a() {
    echo "a"
}

# Line 8: comment
function unused_b() {
    echo "b"
}
"""
    )

    report = detect_unused_bash(project)

    findings_by_name = {f.name: f.line_number for f in report.findings}
    assert findings_by_name["unused_a"] == 4
    assert findings_by_name["unused_b"] == 9


def test_detect_unused_bash_empty_project(tmp_path: Path) -> None:
    """Test detection on empty project."""
    empty_project = tmp_path / "empty"
    empty_project.mkdir()

    report = detect_unused_bash(empty_project)

    assert report.files_scanned == 0
    assert report.total_definitions == 0
    assert len(report.findings) == 0
    assert report.has_findings is False


def test_detect_unused_bash_report_stats(sample_bash_project: Path) -> None:
    """Test that report statistics are correct."""
    report = detect_unused_bash(sample_bash_project)

    # Should have scanned multiple files
    assert report.files_scanned > 0

    # Should have found multiple definitions
    assert report.total_definitions > 0

    # Should have unused findings
    assert report.has_findings is True
    assert len(report.findings) > 0


def test_bash_definition_kind(sample_bash_project: Path) -> None:
    """Test that Bash functions have the correct 'kind' field."""
    report = detect_unused_bash(sample_bash_project)

    # All findings should have kind="bash_function"
    for finding in report.findings:
        assert finding.kind == "bash_function"


def test_find_bash_functions_invalid_file(tmp_path: Path) -> None:
    """Test that find_bash_functions handles invalid files gracefully."""
    # Non-existent file
    result = find_bash_functions(tmp_path / "nonexistent.sh")
    assert result == []


def test_find_bash_calls_invalid_file(tmp_path: Path) -> None:
    """Test that find_bash_calls handles invalid files gracefully."""
    # Non-existent file
    result = find_bash_calls(tmp_path / "nonexistent.sh")
    assert result == set()


def test_find_bash_functions_with_comments(tmp_path: Path) -> None:
    """Test finding functions with comments before them."""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

# This is a comment before the function
# Multi-line comment
my_function() {
    echo "test"
}

### Another comment style
function another_func {
    echo "test2"
}
"""
    )

    definitions = find_bash_functions(test_file)
    names = {d.name for d in definitions}

    assert "my_function" in names
    assert "another_func" in names


def test_find_bash_functions_indented(tmp_path: Path) -> None:
    """Test finding functions with indentation (e.g., in conditionals)."""
    test_file = tmp_path / "test.sh"
    test_file.write_text(
        """\
#!/usr/bin/env bash

if true; then
    nested_function() {
        echo "nested"
    }
fi

    indented_function() {
        echo "indented"
    }
"""
    )

    definitions = find_bash_functions(test_file)
    names = {d.name for d in definitions}

    # Regex should handle indentation
    assert "nested_function" in names
    assert "indented_function" in names

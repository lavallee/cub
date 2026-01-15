"""
Code audit tools for detecting dead code, security issues, and code quality problems.
"""

from .coverage import (
    CoverageFile,
    CoverageReport,
    format_coverage_report,
    get_uncovered_lines,
    identify_low_coverage,
    parse_coverage_report,
    run_coverage,
)
from .dead_code import (
    detect_unused,
    detect_unused_bash,
    find_bash_calls,
    find_bash_functions,
    find_python_definitions,
    find_python_references,
    run_shellcheck,
)
from .docs import (
    check_links,
    extract_code_blocks,
    extract_links,
    validate_code,
    validate_docs,
)
from .models import (
    CodeBlockFinding,
    DeadCodeFinding,
    DeadCodeReport,
    DocsReport,
    LinkFinding,
)

__all__ = [
    "CodeBlockFinding",
    "CoverageFile",
    "CoverageReport",
    "DeadCodeFinding",
    "DeadCodeReport",
    "DocsReport",
    "LinkFinding",
    "check_links",
    "detect_unused",
    "detect_unused_bash",
    "extract_code_blocks",
    "extract_links",
    "find_bash_calls",
    "find_bash_functions",
    "find_python_definitions",
    "find_python_references",
    "format_coverage_report",
    "get_uncovered_lines",
    "identify_low_coverage",
    "parse_coverage_report",
    "run_coverage",
    "run_shellcheck",
    "validate_code",
    "validate_docs",
]

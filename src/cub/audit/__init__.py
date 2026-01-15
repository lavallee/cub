"""
Code audit tools for detecting dead code, security issues, and code quality problems.
"""

from .dead_code import (
    detect_unused,
    detect_unused_bash,
    find_bash_calls,
    find_bash_functions,
    find_python_definitions,
    find_python_references,
    run_shellcheck,
)
from .models import DeadCodeFinding, DeadCodeReport

__all__ = [
    "DeadCodeFinding",
    "DeadCodeReport",
    "detect_unused",
    "detect_unused_bash",
    "find_bash_calls",
    "find_bash_functions",
    "find_python_definitions",
    "find_python_references",
    "run_shellcheck",
]

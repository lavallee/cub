"""
Routes module - Command frequency analysis and route learning.

This module provides functionality to:
1. Parse raw command logs from hook events
2. Normalize commands (strip task IDs, file paths)
3. Aggregate command frequencies
4. Filter out noise (low-frequency commands)
5. Compile learned routes into a shareable markdown file
"""

from cub.core.routes.compiler import (
    compile_routes,
    normalize_command,
    render_learned_routes,
)

__all__ = [
    "compile_routes",
    "normalize_command",
    "render_learned_routes",
]

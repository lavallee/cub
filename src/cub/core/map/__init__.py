"""
Cub map module.

Provides structure analysis and codebase mapping functionality.
This module analyzes project structure, detects tech stacks, extracts
build commands, and identifies key files and module boundaries.

Main entry point: analyze_structure()

Example:
    >>> from cub.core.map import analyze_structure
    >>> structure = analyze_structure("/path/to/project", max_depth=4)
    >>> structure.primary_tech_stack
    <TechStack.PYTHON: 'python'>
    >>> len(structure.build_commands)
    5
"""

from cub.core.map.models import (
    BuildCommand,
    DirectoryNode,
    DirectoryTree,
    KeyFile,
    ModuleInfo,
    ProjectStructure,
    TechStack,
)
from cub.core.map.structure import analyze_structure

__all__ = [
    # Main function
    "analyze_structure",
    # Models
    "BuildCommand",
    "DirectoryNode",
    "DirectoryTree",
    "KeyFile",
    "ModuleInfo",
    "ProjectStructure",
    "TechStack",
]

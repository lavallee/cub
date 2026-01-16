"""
Cub captures module.

Provides data models and storage layer for low-friction idea collection.
Captures are Markdown files with YAML frontmatter that serve as raw
material for the vision-to-tasks pipeline.
"""

from cub.core.captures.models import Capture, CaptureSource, CaptureStatus

__all__ = [
    "Capture",
    "CaptureSource",
    "CaptureStatus",
]

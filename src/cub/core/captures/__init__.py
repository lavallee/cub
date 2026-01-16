"""
Cub captures module.

Provides data models and storage layer for low-friction idea collection.
Captures are Markdown files with YAML frontmatter that serve as raw
material for the vision-to-tasks pipeline.

Two-tier storage model:
1. Global captures (default): ~/.local/share/cub/captures/{project_id}/
2. Project captures (imported): {project}/captures/
"""

from cub.core.captures.models import Capture, CaptureSource, CaptureStatus
from cub.core.captures.project_id import get_project_id
from cub.core.captures.store import CaptureStore

__all__ = [
    "Capture",
    "CaptureSource",
    "CaptureStatus",
    "CaptureStore",
    "get_project_id",
]

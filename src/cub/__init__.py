"""
Cub - AI Coding Assistant Loop

A CLI tool that wraps AI coding assistants for autonomous task execution.
"""

__version__ = "0.25.1"

# Re-export core models for convenience
from cub.core.config.models import CubConfig
from cub.core.tasks.models import Task, TaskPriority, TaskStatus

__all__ = ["CubConfig", "Task", "TaskStatus", "TaskPriority", "__version__"]

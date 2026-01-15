"""
Cub - AI Coding Assistant Loop

A CLI tool that wraps AI coding assistants for autonomous task execution.
"""

__version__ = "0.21.0-dev"

# Re-export core models for convenience
from cub.core.config.models import CubConfig
from cub.core.tasks.models import Task, TaskStatus, TaskPriority

__all__ = ["CubConfig", "Task", "TaskStatus", "TaskPriority", "__version__"]

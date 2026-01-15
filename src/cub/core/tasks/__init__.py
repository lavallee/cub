"""
Task management models and interfaces.

This module provides the core data models for task management,
including the Task model, status enums, and priority levels, as well
as the TaskBackend protocol for pluggable backend implementations.
"""

from .backend import (
    TaskBackend,
    detect_backend,
    get_backend,
    is_backend_available,
    list_backends,
    register_backend,
)
from .models import Task, TaskCounts, TaskPriority, TaskStatus, TaskType

# Import backend implementations to trigger registration
from . import beads  # noqa: F401

__all__ = [
    # Models
    "Task",
    "TaskStatus",
    "TaskPriority",
    "TaskType",
    "TaskCounts",
    # Backend protocol and registry
    "TaskBackend",
    "register_backend",
    "get_backend",
    "detect_backend",
    "list_backends",
    "is_backend_available",
]

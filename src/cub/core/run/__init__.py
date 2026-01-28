"""
Core run package.

Provides business logic for the cub run command, separated from CLI concerns.
This package contains prompt building, task context generation, budget tracking,
and related pure logic that can be used by any interface (CLI, API, skills, etc.).

Modules:
    prompt_builder: System prompt generation, task context injection, and
                    related prompt composition functions.
    budget: Budget tracking and limit enforcement for token/cost management.
"""

from cub.core.run.budget import (
    BudgetCheckResult,
    BudgetConfig,
    BudgetManager,
    BudgetState,
)
from cub.core.run.prompt_builder import (
    generate_direct_task_prompt,
    generate_epic_context,
    generate_retry_context,
    generate_system_prompt,
    generate_task_prompt,
)

__all__ = [
    # Prompt builder
    "generate_direct_task_prompt",
    "generate_epic_context",
    "generate_retry_context",
    "generate_system_prompt",
    "generate_task_prompt",
    # Budget tracking
    "BudgetCheckResult",
    "BudgetConfig",
    "BudgetManager",
    "BudgetState",
]

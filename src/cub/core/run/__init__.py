"""
Core run package.

Provides business logic for the cub run command, separated from CLI concerns.
This package contains prompt building, task context generation, budget tracking,
loop state machine, and related pure logic that can be used by any interface
(CLI, API, skills, etc.).

Modules:
    prompt_builder: System prompt generation, task context injection, and
                    related prompt composition functions.
    budget: Budget tracking and limit enforcement for token/cost management.
    models: Configuration and event models for the run loop.
    loop: Run loop state machine (pick task → execute → record → next).
"""

from cub.core.run.budget import (
    BudgetCheckResult,
    BudgetConfig,
    BudgetManager,
    BudgetState,
)
from cub.core.run.loop import RunLoop
from cub.core.run.models import (
    RunConfig,
    RunEvent,
    RunEventType,
    RunResult,
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
    # Run loop
    "RunConfig",
    "RunEvent",
    "RunEventType",
    "RunLoop",
    "RunResult",
]

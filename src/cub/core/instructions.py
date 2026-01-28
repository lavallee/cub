"""
Instruction file generation for direct harness sessions.

This module generates CLAUDE.md and AGENTS.md files that guide AI assistants
to use cub commands when running directly (not via `cub run`). This enables
a symbiotic workflow where work is tracked in the ledger regardless of whether
it came from autonomous mode or direct harness sessions.

Key Functions:
    - generate_agents_md: Creates harness-agnostic instructions (AGENTS.md)
    - generate_claude_md: Creates Claude-specific instructions (CLAUDE.md)

Architecture:
    The instruction generator produces markdown files that:
    1. Guide agents to use `bd` commands for task management
    2. Instruct agents to use `cub` commands for logging and status
    3. Include escape hatch language for signaling when stuck
    4. Provide workflow instructions for finding, claiming, and completing tasks

Usage:
    >>> from pathlib import Path
    >>> from cub.core.config.loader import load_config
    >>> from cub.core.instructions import generate_agents_md, generate_claude_md
    >>>
    >>> project_dir = Path.cwd()
    >>> config = load_config(project_dir)
    >>>
    >>> # Generate AGENTS.md for cross-harness compatibility
    >>> agents_content = generate_agents_md(project_dir, config)
    >>> (project_dir / "AGENTS.md").write_text(agents_content)
    >>>
    >>> # Generate CLAUDE.md with Claude-specific additions
    >>> claude_content = generate_claude_md(project_dir, config)
    >>> (project_dir / "CLAUDE.md").write_text(claude_content)

Dependencies:
    - pathlib: For file path handling
    - cub.core.config.models: For CubConfig type hints
"""

from pathlib import Path

from cub.core.config.models import CubConfig

# Escape hatch language from E5 spec
ESCAPE_HATCH_SECTION = """## Escape Hatch: Signal When Stuck

If you get stuck and cannot make progress despite a genuine attempt to solve
the task, signal your state to the autonomous loop so it can stop gracefully
instead of consuming time and budget on a blocked task.

**How to signal "stuck":**

Output this XML tag with your reason:

```
<stuck>REASON FOR BEING STUCK</stuck>
```

**Example:**
```
<stuck>Cannot find the required configuration file after exhaustive search.
The file may not exist in this repository, preventing further progress on
dependency injection setup.</stuck>
```

**What "stuck" means:**

- You have genuinely attempted to solve the task (multiple approaches, searched
  codebase, read docs)
- An external blocker prevents progress (missing file, dependency not found,
  environment issue, unclear requirements)
- Continuing to work on this task will waste time and money without producing
  value
- The blocker cannot be resolved within the scope of this task

**What "stuck" does NOT mean:**

- "This task is hard" — Keep working
- "I'm confused about how something works" — Search docs, read code, ask in a
  follow-up task
- "I've spent 30 minutes" — Time spent is not a blocker; genuine blockers are

**Effect of signaling "stuck":**

- The autonomous loop detects this signal and stops the run gracefully
- Your work so far is captured in artifacts and the ledger
- The task is marked with context for manual review
- This complements the time-based circuit breaker which trips after inactivity
  timeout

**Important:** This is not a replacement for the time-based circuit breaker.
The circuit breaker monitors subprocess activity. This escape hatch is your
active signal that you, the agent, are genuinely blocked and should stop.
"""


def generate_agents_md(project_dir: Path, config: CubConfig) -> str:
    """
    Generate AGENTS.md with harness-agnostic workflow instructions.

    Creates instructions for AI assistants running in direct mode (not via `cub run`)
    to use cub commands for task tracking and work logging. This file is compatible
    with Claude Code, Codex, OpenCode, and other AI coding assistants.

    The generated file includes:
    - Project context and overview
    - How to find available tasks (`cub status`, `bd ready`)
    - How to claim work (`bd update <id> --status in_progress`)
    - How to complete tasks (`bd close <id>`)
    - How to log work (`cub log`)
    - Escape hatch language for signaling when stuck

    Args:
        project_dir: Path to the project root directory
        config: CubConfig instance with project configuration

    Returns:
        Complete AGENTS.md content as a string

    Example:
        >>> config = load_config()
        >>> content = generate_agents_md(Path.cwd(), config)
        >>> Path("AGENTS.md").write_text(content)
    """
    # Read project name from config or use directory name
    project_name = project_dir.name

    # Circuit breaker timeout from config
    timeout_minutes = config.circuit_breaker.timeout_minutes

    content = f"""# Agent Instructions

This project uses **cub** for task management and autonomous coding workflows.

## Project Context

You are working in the `{project_name}` project. This project uses:
- **Task backend**: Beads CLI (`bd`) for task tracking
- **Cub**: Autonomous coding loop and workflow management
- **Circuit breaker**: {timeout_minutes}-minute timeout for detecting stagnation

For detailed build/test instructions, see `.cub/agent.md`.

## When Running Directly (Not via cub run)

If you're running as a direct harness session (Claude Code, Codex, OpenCode,
etc.) rather than via `cub run`, follow this workflow to keep work tracked:

### 1. Find Available Tasks

```bash
# See all open tasks
bd list --status open

# See tasks ready to work on (no blockers)
bd ready

# Show current project status
cub status
```

### 2. Claim a Task

Before starting work, claim the task:

```bash
bd update <task-id> --status in_progress
```

Example:
```bash
bd update cub-abc.1 --status in_progress
```

### 3. Do the Work

- Read task description: `bd show <task-id>`
- Implement the changes
- Run tests and quality checks
- Commit your work with conventional commit format: `type(task-id): description`

### 4. Complete the Task

When done, close the task with a brief reason:

```bash
bd close <task-id> -r "brief description of what was done"
```

Example:
```bash
bd close cub-abc.1 -r "implemented feature with tests and docs"
```

### 5. Log Your Session (Optional)

Record what you accomplished:

```bash
cub log --notes="Completed task cub-abc.1: implemented X feature"
```

{ESCAPE_HATCH_SECTION}

## Workflow Summary

```
1. Find work    → bd ready
2. Claim task   → bd update <id> --status in_progress
3. Implement    → (code, test, commit)
4. Complete     → bd close <id> -r "done"
5. Log session  → cub log --notes="..."
```

## Important Notes

- **Always claim tasks** before starting work (`bd update --status in_progress`)
- **Always close tasks** when done (`bd close -r "reason"`)
- **Use conventional commits**: Format commits as `type(task-id): description`
- **Run quality checks**: Tests, linting, type checking before closing tasks
- **Signal if stuck**: Use the `<stuck>` tag if genuinely blocked (see above)

## Commands Reference

### Task Management (bd)
- `bd list --status open` - List open tasks
- `bd ready` - Show tasks ready to work on
- `bd show <id>` - View task details
- `bd update <id> --status in_progress` - Claim a task
- `bd close <id> -r "reason"` - Complete a task

### Cub Commands
- `cub status` - Show project status and progress
- `cub log --notes="..."` - Log work done in this session
- `cub run` - Start autonomous coding loop (if needed)

## Getting Help

- Read `.cub/agent.md` for build/run/test instructions
- Read `@specs/*` for detailed specifications (if present)
- Use `bd show <task-id>` for task-specific context
"""

    return content


def generate_claude_md(project_dir: Path, config: CubConfig) -> str:
    """
    Generate CLAUDE.md with Claude Code-specific workflow instructions.

    Creates instructions tailored for Claude Code, including references to
    AGENTS.md for the core workflow plus Claude-specific features like
    plan mode integration.

    The generated file includes:
    - Reference to AGENTS.md for core workflow
    - Plan mode instructions (save plans to plans/ directory)
    - Claude Code-specific tips and best practices

    Args:
        project_dir: Path to the project root directory
        config: CubConfig instance with project configuration

    Returns:
        Complete CLAUDE.md content as a string

    Example:
        >>> config = load_config()
        >>> content = generate_claude_md(Path.cwd(), config)
        >>> Path("CLAUDE.md").write_text(content)
    """
    # Read project name from config or use directory name
    project_name = project_dir.name

    content = f"""# Claude Code Instructions

This project uses **cub** for task management and autonomous coding workflows.

## Core Workflow

**See AGENTS.md** for complete workflow instructions on:
- Finding and claiming tasks
- Completing work and closing tasks
- Logging sessions
- Escape hatch for signaling when stuck

This file contains **Claude Code-specific** additions.

Note: Build/test instructions are in `.cub/agent.md` (generated by `cub stage`).

## Plan Mode Integration

When using Claude Code's plan mode to create implementation plans:

### Save Plans to plans/ Directory

After creating a plan in plan mode, save it to:
```
plans/<descriptive-name>/plan.md
```

Example structure:
```
plans/
├── authentication-system/
│   └── plan.md
├── api-refactor/
│   └── plan.md
└── dashboard-ui/
    └── plan.md
```

### Plan File Format

Your plan file should include:
- **Summary**: What you're implementing and why
- **Approach**: Technical strategy and key decisions
- **Steps**: Ordered list of implementation tasks
- **Files**: Which files will be created/modified
- **Tests**: Testing strategy
- **Risks**: Potential issues and mitigations

Example:
```markdown
# Authentication System Implementation

## Summary
Implement JWT-based authentication with refresh tokens.

## Approach
- Use PyJWT library for token generation/validation
- Store refresh tokens in Redis with expiration
- Add middleware for route protection

## Steps
1. Install and configure PyJWT
2. Create auth service with login/logout/refresh endpoints
3. Add authentication middleware
4. Write integration tests
5. Update API documentation

## Files
- src/cub/core/auth/service.py (new)
- src/cub/core/auth/middleware.py (new)
- tests/test_auth.py (new)
- requirements.txt (modified)

## Tests
- Unit tests for token generation/validation
- Integration tests for login/logout flow
- Security tests for invalid/expired tokens

## Risks
- Token secret management (use environment variables)
- Redis availability (add graceful degradation)
```

## Claude Code Best Practices

### Before Starting Work
1. Read `AGENTS.md` for the workflow
2. Check `.cub/agent.md` for build/test commands
3. Run `bd ready` to see available tasks
4. Claim your task: `bd update <id> --status in_progress`

### During Work
- Use plan mode for complex features
- Save plans to `plans/<name>/plan.md`
- Commit frequently with conventional commit format
- Run tests before considering work done

### After Completing Work
- Run all quality checks (tests, linting, type checking)
- Close the task: `bd close <id> -r "what you did"`
- Optional: Log your session with `cub log`

### If You Get Stuck
Use the escape hatch signal (see AGENTS.md):
```xml
<stuck>Clear description of the blocker preventing progress</stuck>
```

## Project: {project_name}

For project-specific context:
- **Build/Run/Test**: See `.cub/agent.md`
- **Specifications**: See `@specs/*` (if present)
- **Task Details**: Use `bd show <task-id>`
"""

    return content


__all__ = [
    "generate_agents_md",
    "generate_claude_md",
    "ESCAPE_HATCH_SECTION",
]

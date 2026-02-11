# Contributing to Cub

This guide explains how to extend cub with new AI harnesses, task backends, and other features.

## ⚠️ Alpha Notice

Cub is in alpha development. Contribution guidelines, architecture, and APIs may change. Please open issues for feature discussions before starting major work.

## Architecture Overview

Cub is a Python CLI built on Typer with pluggable backends for tasks and AI harnesses. Since v0.26+, cub uses a layered service architecture to separate business logic from interface concerns.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           cub (Python CLI)                               │
│                        Typer CLI Application                             │
├──────────────────────────────────────────────────────────────────────────┤
│                     Service Layer (core/services/)                        │
│  RunService │ LaunchService │ LedgerService │ StatusService              │
│  SuggestionService │ (stateless orchestrators, typed I/O)                │
├──────────────────────────────────────────────────────────────────────────┤
│                        Core Domain (Python)                               │
├──────────────────┬─────────────────┬───────────────────────────────────┤
│  cub.core.tasks  │ cub.core.harness │  cub.core.config                  │
│  (Backend        │ (Harness         │  (Configuration)                  │
│   Protocol)      │  Protocol)       │                                   │
├──────────────────┼─────────────────┼───────────────────────────────────┤
│ beads │jsonl    │ claude │ codex   │  gemini │ opencode               │
│ json  │         │                  │                                    │
└──────────────────┴─────────────────┴───────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                     Optional Features (Experimental)                      │
├──────────────────────────────────────────────────────────────────────────┤
│ - Planning Pipeline (orient, architect, itemize)                         │
│ - Dashboard (Kanban visualization across 8 workflow stages)              │
│ - Task State Sync (cub-sync branch persistence)                          │
│ - Symbiotic Workflow (hooks bridge direct sessions with ledger)          │
│ - Tool Runtime (pluggable HTTP, CLI, MCP adapters)                       │
│ - Suggestions Engine (smart recommendations for next actions)            │
└──────────────────────────────────────────────────────────────────────────┘
```

The service layer (`core/services/`) contains stateless orchestrators that compose domain operations into clean APIs. Services accept typed inputs, return typed outputs, and never call Rich, print(), or sys.exit(). This enables multiple interfaces (CLI, skills, API) to share core functionality. New features should add service methods first, then interface implementations.

## Development Setup

```bash
# Install with development dependencies
uv sync

# Or with pip
pip install -e ".[dev]"

# Activate virtual environment
source .venv/bin/activate
```

## Testing

```bash
# Python tests (primary)
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/cub --cov-report=html

# Type checking
mypy src/cub

# Linting
ruff check src/ tests/

# Bash tests (for delegated commands)
bats tests/
```

## Adding a New AI Harness

Harnesses are pluggable backends that wrap AI coding CLIs. Implement the `HarnessBackend` protocol.

### 1. Create Backend Module

Create `src/cub/core/harness/myharness.py`:

```python
"""MyHarness backend implementation."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cub.core.models import Task

class MyHarnessBackend:
    """MyHarness AI coding assistant backend."""

    name = "myharness"

    def is_available(self) -> bool:
        """Check if myharness CLI is installed."""
        try:
            subprocess.run(
                ["myharness", "--version"],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_version(self) -> str:
        """Get myharness version string."""
        result = subprocess.run(
            ["myharness", "--version"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or "unknown"

    def invoke(
        self,
        system_prompt: str,
        task_prompt: str,
        *,
        debug: bool = False,
        model: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Invoke myharness with the given prompts."""
        combined_prompt = f"{system_prompt}\n\n---\n\n{task_prompt}"

        cmd = ["myharness", "run", "--auto"]
        if model:
            cmd.extend(["--model", model])

        return subprocess.run(
            cmd,
            input=combined_prompt,
            capture_output=True,
            text=True,
        )

    def invoke_streaming(
        self,
        system_prompt: str,
        task_prompt: str,
        *,
        debug: bool = False,
        model: str | None = None,
    ) -> subprocess.Popen[str]:
        """Invoke myharness with streaming output."""
        combined_prompt = f"{system_prompt}\n\n---\n\n{task_prompt}"

        cmd = ["myharness", "run", "--auto", "--stream"]
        if model:
            cmd.extend(["--model", model])

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        proc.stdin.write(combined_prompt)
        proc.stdin.close()
        return proc
```

### 2. Register the Backend

Edit `src/cub/core/harness/__init__.py`:

```python
from cub.core.harness.myharness import MyHarnessBackend

HARNESS_BACKENDS = {
    "claude": ClaudeBackend,
    "codex": CodexBackend,
    "gemini": GeminiBackend,
    "opencode": OpenCodeBackend,
    "myharness": MyHarnessBackend,  # Add your backend
}
```

### 3. Add Auto-Detection

If your harness should be auto-detected, update `detect_harness()` in `src/cub/core/harness/backend.py`:

```python
def detect_harness() -> str | None:
    """Auto-detect available harness."""
    for name, backend_cls in HARNESS_BACKENDS.items():
        backend = backend_cls()
        if backend.is_available():
            return name
    return None
```

### 4. Document Environment Variables

Add to README.md:
- `MYHARNESS_FLAGS` - Extra flags for your harness
- `MYHARNESS_MODEL` - Default model override

## Adding a New Task Backend

Task backends manage the work queue. Implement the `TaskBackend` protocol.

### 1. Create Backend Module

Create `src/cub/core/tasks/mybackend.py`:

```python
"""MyBackend task management implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cub.core.models import Task

class MyTaskBackend:
    """MyBackend task management."""

    name = "mybackend"

    def __init__(self, project_dir: Path | None = None) -> None:
        self.project_dir = project_dir or Path.cwd()

    def is_available(self) -> bool:
        """Check if mybackend CLI is installed."""
        # Implementation

    def is_initialized(self) -> bool:
        """Check if mybackend is initialized in project."""
        return (self.project_dir / ".mybackend" / "config").exists()

    def get_ready_tasks(
        self,
        *,
        epic: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """Get tasks ready to work on (open, unblocked)."""
        # Implementation

    def get_task(self, task_id: str) -> Task | None:
        """Get a single task by ID."""
        # Implementation

    def update_status(self, task_id: str, status: str) -> None:
        """Update task status."""
        # Implementation

    def add_note(self, task_id: str, note: str) -> None:
        """Add a note to a task."""
        # Implementation

    def create_task(self, task_data: dict) -> str:
        """Create a new task, return ID."""
        # Implementation

    def get_counts(self) -> dict[str, int]:
        """Get task counts by status."""
        # Implementation

    def all_complete(self) -> bool:
        """Check if all tasks are closed."""
        # Implementation
```

### 2. Register the Backend

Edit `src/cub/core/tasks/__init__.py`:

```python
from cub.core.tasks.mybackend import MyTaskBackend

TASK_BACKENDS = {
    "beads": BeadsBackend,
    "json": JsonBackend,
    "mybackend": MyTaskBackend,  # Add your backend
}
```

### 3. Support Model Labels

Tasks with `model:X` labels trigger automatic model selection. Include labels in your task output:

```python
def get_ready_tasks(self, ...) -> list[Task]:
    # ... fetch tasks ...
    return [
        Task(
            id="task-123",
            title="Quick fix",
            labels=["phase-1", "model:haiku"],
            # ...
        )
    ]
```

## Adding a New CLI Command

### Native Python Command

1. Create module in `src/cub/cli/`:

```python
# src/cub/cli/mycommand.py
"""My command implementation."""

import typer

app = typer.Typer(help="My command description")

@app.command()
def run(
    option: str = typer.Option(None, help="An option"),
) -> None:
    """Run my command."""
    # Implementation
```

2. Register in `src/cub/cli/__init__.py`:

```python
from cub.cli import mycommand

app.add_typer(mycommand.app, name="mycommand", rich_help_panel=PANEL_KEY)
```

### Delegated Bash Command

For commands still in Bash:

1. Implement in `src/cub/bash/cub`:

```bash
cmd_mycommand() {
    # Implementation
}
```

2. Add delegation in `src/cub/cli/delegated.py`:

```python
def mycommand(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """My command description."""
    _delegate("mycommand", args or [], ctx)
```

3. Register in `src/cub/cli/__init__.py`:

```python
app.command(name="mycommand", rich_help_panel=PANEL_TASKS)(delegated.mycommand)
```

4. Add to `bash_commands` set in `src/cub/core/bash_delegate.py`:

```python
bash_commands = {
    # ... existing commands ...
    "mycommand",
}
```

## Extension Points

Beyond harnesses and task backends, cub has several other extension points:

### Tool Runtime (`core/tools/`)

The tool runtime supports pluggable adapters for executing external tools:
- **HTTP adapters** - Call REST APIs
- **CLI adapters** - Execute command-line tools
- **MCP adapters** - Connect to MCP stdio servers

Implement the `ToolAdapter` protocol in `core/tools/adapter.py` and register in `core/tools/registry.py`.

### Dashboard (`core/dashboard/`)

The dashboard system supports custom parsers for new data sources and custom view configurations. Add parsers to `core/dashboard/sync/parsers/` and view configs to `.cub/views/*.yaml`.

### Suggestions Engine (`core/suggestions/`)

The recommendation engine can be extended with new data sources and ranking strategies. See `core/suggestions/sources.py` for data source interfaces and `core/suggestions/ranking.py` for ranking algorithms.

## Documentation

Documentation lives in `docs-src/` using MkDocs Material. To build and preview:

```bash
cd docs-src
pip install -r requirements.txt  # or: pip install mkdocs-material mkdocs-minify-plugin
mkdocs serve                     # Preview at http://localhost:8000
```

Content is in `docs-src/content/`. Follow existing page patterns for new pages.
The site deploys automatically from the `main` branch.

## Project Templates

Templates in `src/cub/templates/` are copied to projects during `cub init`:

| File | Purpose |
|------|---------|
| `runloop.md` | System prompt for autonomous loop (installed to `.cub/runloop.md`) |
| `agent.md` | Project-specific instructions (agent-editable, installed to `.cub/agent.md`) |

Templates support backend-specific customization via sed substitution during init.

## Code Style

- **Python**: Use `ruff` for formatting and linting, `mypy` for type checking
- **Bash**: Follow existing patterns, use `log_*` functions for output
- **Types**: Use explicit types everywhere (strict mypy)
- **Imports**: Use absolute imports from `cub.core`, not relative imports
- **Protocols**: Use `typing.Protocol` for interfaces, not ABC

## Pull Request Guidelines

1. **Run all checks before submitting:**
   ```bash
   pytest tests/ -v
   mypy src/cub
   ruff check src/ tests/
   ```

2. **Update documentation:**
   - `CONTRIBUTING.md` for architecture changes
   - `README.md` for user-facing features
   - `docs/ALPHA-NOTES.md` if adding experimental features
   - Docstrings for new functions/classes

3. **Add tests:**
   - pytest for Python code
   - Include test coverage for new backends/harnesses

4. **Mark experimental features:**
   - Use `[EXPERIMENTAL]` tags in README.md
   - Document in `docs/ALPHA-NOTES.md`
   - Include clear stability warnings

5. **Maintain backwards compatibility:**
   - Existing task/harness backends must continue working
   - Deprecate features gradually with warnings

6. **Keep PRs focused:** One feature or fix per PR

## Questions?

Open an issue on GitHub for discussion.

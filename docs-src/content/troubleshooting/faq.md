---
title: FAQ
description: Frequently asked questions about Cub installation, usage, configuration, and more.
---

# Frequently Asked Questions

Answers to commonly asked questions about Cub.

---

## Installation

??? question "What are the system requirements for Cub?"

    Cub requires:

    - **Python 3.10+** - Required for the Python CLI
    - **At least one AI harness** - Claude Code, Codex, Gemini, or OpenCode
    - **Git** - For version control integration
    - **jq** - For JSON processing (in bash components)

    Optional:

    - **Docker** - For sandbox mode
    - **Beads CLI** - For beads task backend

??? question "Which AI harness should I use?"

    **Claude Code is recommended** for most users because it supports:

    - All Cub features (streaming, token tracking, system prompts)
    - Best integration with `cub plan`
    - Active development and support

    See the [Harnesses comparison](../guide/harnesses/index.md) for a full capability matrix.

??? question "Can I use Cub without npm/Node.js?"

    Yes! The Python version of Cub can be installed with:

    ```bash
    # Using pipx (recommended)
    pipx install cub-cli

    # Or using uv
    uv tool install cub-cli

    # Or using pip
    pip install cub-cli
    ```

    However, most AI harnesses (Claude Code, Codex, Gemini) are installed via npm. You only need npm for harness installation, not for running Cub itself.

??? question "How do I install Cub globally?"

    Use the one-liner installer:

    ```bash
    curl -LsSf https://docs.cub.tools/install.sh | bash
    ```

    Or install via pipx for isolated installation:

    ```bash
    pipx install cub-cli
    ```

    Then set up global configuration:

    ```bash
    cub init --global
    ```

---

## Usage

??? question "What's the difference between `cub plan` and `cub run`?"

    **`cub plan`** - Planning phase (work *ahead* of execution)

    - Converts vague ideas into structured tasks
    - Runs orient, architect, itemize, and stage phases
    - Requires human review and refinement
    - Creates agent-ready task specifications

    **`cub run`** - Execution phase (autonomous operation)

    - Executes prepared tasks with an AI harness
    - Runs autonomously without human intervention
    - Tracks progress, handles errors, manages budget
    - Updates task status as work completes

    The workflow is: **Plan** (human-in-loop) -> **Run** (autonomous)

??? question "How do I run just one task?"

    Use the `--once` flag:

    ```bash
    cub run --once
    ```

    This runs a single iteration and exits. Useful for testing or when you want to review after each task.

??? question "Can I run Cub in the background?"

    Yes! Use nohup or screen/tmux:

    ```bash
    # With nohup
    nohup cub run &> cub.log &

    # With screen
    screen -S cub
    cub run
    # Ctrl+A, D to detach

    # With tmux
    tmux new -s cub
    cub run
    # Ctrl+B, D to detach
    ```

    Monitor progress with:

    ```bash
    cub status
    # Or
    cub monitor
    ```

??? question "How do I stop Cub gracefully?"

    Press **Ctrl+C** once for a graceful shutdown. Cub will:

    1. Finish the current operation
    2. Save state
    3. Exit cleanly

    Press **Ctrl+C twice** for immediate termination (may lose current task progress).

??? question "What happens if Cub crashes mid-task?"

    Cub is designed to be resumable:

    1. Task status remains unchanged (still "in_progress")
    2. Git state is preserved (uncommitted changes may exist)
    3. Running `cub run` again will resume from where it left off

    Check status after a crash:

    ```bash
    git status
    cub status
    ```

---

## Configuration

??? question "Where are Cub's configuration files?"

    Cub uses a layered configuration system:

    | Location | Purpose |
    |----------|---------|
    | `~/.config/cub/config.json` | Global defaults |
    | `.cub.json` | Project-specific settings |
    | `.cub/` directory | Project state, logs, artifacts |

    Priority: CLI flags > environment variables > project config > global config > defaults

??? question "How do I set a default harness?"

    In your global config (`~/.config/cub/config.json`):

    ```json
    {
      "harness": {
        "priority": ["claude", "opencode", "codex", "gemini"]
      }
    }
    ```

    Or set per-project in `.cub.json`.

??? question "How do I increase the budget limit?"

    Via CLI:

    ```bash
    cub run --budget 5000000
    ```

    Or in config:

    ```json
    {
      "budget": {
        "limit": 5000000,
        "warn_at": 80
      }
    }
    ```

??? question "How do I disable clean state checks?"

    In `.cub.json`:

    ```json
    {
      "clean_state": {
        "require_commit": false,
        "require_tests": false
      }
    }
    ```

    !!! warning
        Disabling these checks can lead to lost work or inconsistent state. Use with caution.

---

## Task Backends

??? question "What's the difference between beads and JSON backends?"

    | Feature | Beads | JSON |
    |---------|-------|------|
    | Storage | `.beads/issues.jsonl` | `prd.json` |
    | CLI | Full `bd` CLI | Read-only |
    | Sync | GitHub Issues sync | Manual |
    | Dependencies | Built-in | Basic |
    | Recommended | Yes (active) | Legacy |

    **Beads** is the recommended backend for new projects. It provides a full CLI for task management and syncs with GitHub Issues.

??? question "How do I switch from JSON to beads backend?"

    Run the migration:

    ```bash
    # Preview changes
    cub --migrate-to-beads-dry-run

    # Execute migration
    cub --migrate-to-beads
    ```

    This converts your `prd.json` tasks to `.beads/issues.jsonl`.

??? question "How do I create a new task?"

    With beads backend:

    ```bash
    bd create "Task title" --desc "Detailed description"
    ```

    With JSON backend, edit `prd.json` manually:

    ```json
    {
      "tasks": [
        {
          "id": "new-task-1",
          "title": "New task",
          "description": "What to do",
          "status": "open"
        }
      ]
    }
    ```

??? question "How do I close a task manually?"

    With beads:

    ```bash
    bd close <task-id> -r "Completed successfully"
    ```

    Or use the Cub CLI:

    ```bash
    cub close-task <task-id> --reason "Done"
    ```

---

## Harnesses

??? question "Why does Cub prefer Claude Code?"

    Claude Code has the most complete feature support:

    - **Streaming output** - See progress in real-time
    - **Token reporting** - Accurate budget tracking
    - **System prompts** - Separate instructions from tasks
    - **JSON output** - Reliable response parsing
    - **Model selection** - Choose models per task

    Other harnesses work but may lack some features.

??? question "Can I use multiple harnesses?"

    Yes! Configure a priority order:

    ```json
    {
      "harness": {
        "priority": ["claude", "opencode", "codex"]
      }
    }
    ```

    Cub uses the first available harness. You can also select per-task with labels:

    ```bash
    bd label <task-id> harness:codex
    ```

??? question "How do I select a model for a specific task?"

    Add a model label to the task:

    ```bash
    bd label <task-id> model:haiku
    ```

    When the task runs, Cub passes the model to the harness (if supported).

---

## Git Integration

??? question "Does Cub commit changes automatically?"

    By default, **no**. Cub runs tasks but doesn't automatically commit. The AI harness may commit as part of its work (Claude Code often does).

    You can configure hooks to commit after tasks:

    ```json
    {
      "hooks": {
        "post_task": ["git add . && git commit -m 'Task complete'"]
      }
    }
    ```

??? question "How does branch management work?"

    Cub can bind branches to epics:

    ```bash
    # Create and bind branch to epic
    cub branch my-epic

    # List bindings
    cub branches

    # Create PR when done
    cub pr my-epic
    ```

    See [Git Integration](../guide/git/index.md) for details.

??? question "What are worktrees and when should I use them?"

    Git worktrees allow multiple checkouts of the same repo. Cub uses them for:

    - **Parallel execution** - Run multiple tasks simultaneously
    - **Isolation** - Each task works in its own directory

    ```bash
    # Run 3 tasks in parallel with worktrees
    cub run --parallel 3
    ```

    See [Worktrees](../guide/git/worktrees.md) for details.

---

## Advanced Features

??? question "What is sandbox mode?"

    Sandbox mode runs tasks in Docker containers for complete isolation:

    ```bash
    cub run --sandbox
    ```

    Benefits:

    - Untrusted code can't affect your system
    - Reproducible environment
    - Network isolation (optional)

    See [Sandbox Mode](../guide/advanced/sandbox.md) for details.

??? question "How do I run tasks in parallel?"

    Use the `--parallel` flag:

    ```bash
    cub run --parallel 3
    ```

    Each task runs in its own git worktree. Tasks must be independent (no shared dependencies).

    See [Parallel Execution](../guide/advanced/parallel.md) for details.

??? question "What are hooks and how do I use them?"

    Hooks run custom scripts at key points:

    - `pre_run` - Before session starts
    - `post_run` - After session ends
    - `pre_task` - Before each task
    - `post_task` - After each task

    Configure in `.cub.json`:

    ```json
    {
      "hooks": {
        "post_task": ["./scripts/notify.sh"]
      }
    }
    ```

    See [Hooks System](../guide/hooks/index.md) for details.

---

## Troubleshooting

??? question "How do I debug Cub issues?"

    1. **Enable debug mode**:
       ```bash
       cub run --debug --once
       ```

    2. **Run diagnostics**:
       ```bash
       cub doctor
       ```

    3. **Check logs**:
       ```bash
       tail -100 .cub/logs/session-*.jsonl | jq .
       ```

??? question "Why is Cub slow?"

    Common causes:

    - **Large context** - Big files or many tasks slow down the AI
    - **Network latency** - Check your connection
    - **Rate limiting** - Use `--once` and space out runs
    - **Heavy tests** - Consider `require_tests: false` for drafts

    Enable debug mode to see timing:
    ```bash
    cub run --debug --once
    ```

??? question "How do I report a bug?"

    1. Gather diagnostic info:
       ```bash
       cub doctor > doctor.txt
       cub run --debug --once 2>&1 | tee debug.log
       ```

    2. [Open an issue](https://github.com/lavallee/cub/issues/new) with:
       - Error message
       - Doctor output
       - Debug logs
       - Steps to reproduce
       - Your environment (OS, Python version, harness)

---

## Migration & Upgrading

??? question "How do I upgrade Cub?"

    ```bash
    # If installed via one-liner
    cub upgrade

    # If installed via pipx
    pipx upgrade cub-cli

    # If installed via pip
    pip install --upgrade cub-cli
    ```

??? question "Are there breaking changes between versions?"

    Check the [Changelog](../changelog.md) and [Upgrading Guide](../getting-started/upgrading.md) for breaking changes and migration instructions.

??? question "Can I use Cub with an existing project?"

    Yes! Initialize Cub in any project:

    ```bash
    cd my-existing-project
    cub init
    ```

    Then create tasks and run:

    ```bash
    cub plan  # Or manually create tasks
    cub run
    ```

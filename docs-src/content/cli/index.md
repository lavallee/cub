---
title: CLI Reference
description: Complete reference for all Cub CLI commands, options, and environment variables.
---

# CLI Reference

Cub provides a comprehensive command-line interface for managing autonomous AI coding sessions. This reference covers all available commands, their options, and usage patterns.

---

## Command Overview

Commands are organized into logical groups based on their function:

### Key Commands

The primary commands for everyday use:

| Command | Description |
|---------|-------------|
| [`cub run`](run.md) | Execute the autonomous task loop |
| [`cub plan`](plan.md) | Run the vision-to-tasks plan flow |
| [`cub init`](init.md) | Initialize cub in a project |
| [`cub new`](new.md) | Create a new project directory |

### Status Commands

Commands for monitoring and inspecting runs:

| Command | Description |
|---------|-------------|
| [`cub status`](status.md) | Show task progress and statistics |
| [`cub monitor`](monitor.md) | Display live dashboard for active runs |
| [`cub artifacts`](artifacts.md) | View task output artifacts |

### Task Commands

Commands for working with individual tasks:

| Command | Description |
|---------|-------------|
| [`cub interview`](interview.md) | Deep dive on task specifications |
| [`cub explain-task`](explain-task.md) | Show detailed task information |
| [`cub close-task`](close-task.md) | Close a task (for agent use) |

### Epic Commands

Commands for managing epics and branches:

| Command | Description |
|---------|-------------|
| [`cub branch`](branch.md) | Create and bind branch to epic |
| [`cub branches`](branches.md) | List and manage branch-epic bindings |
| [`cub pr`](pr.md) | Create pull request for epic |
| [`cub worktree`](worktree.md) | Manage git worktrees |
| [`cub merge`](merge.md) | Merge epic branches |

### Install Commands

Commands for managing your Cub installation:

| Command | Description |
|---------|-------------|
| [`cub doctor`](doctor.md) | Diagnose and fix configuration issues |
| [`cub upgrade`](upgrade.md) | Upgrade cub to newer version |
| [`cub uninstall`](uninstall.md) | Remove cub installation |

### Capture Commands

Commands for managing idea captures:

| Command | Description |
|---------|-------------|
| [`cub capture`](capture.md) | Record a new idea or observation |
| [`cub captures`](captures.md) | List and manage captures |
| [`cub organize-captures`](organize-captures.md) | Organize captures into tasks |
| [`cub investigate`](investigate.md) | Deep-dive research on a capture |

---

## Global Options

These options are available on all commands:

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug output |
| `--help`, `-h` | Show help for command |
| `--version` | Show cub version |

### Debug Mode

Enable verbose logging with the `--debug` flag:

```bash
cub run --debug
cub status --debug
```

Debug mode outputs additional information:

- Configuration loading details
- Harness detection and version
- Task backend initialization
- File paths and session IDs

---

## Command Notation

Throughout this reference, commands use the following notation:

| Notation | Meaning |
|----------|---------|
| `<required>` | Required argument |
| `[optional]` | Optional argument |
| `--flag` | Boolean flag |
| `--option VALUE` | Option with value |
| `--option=VALUE` | Alternative syntax |
| `-f` | Short form of flag |
| `command \| alt` | Either command works |

### Examples

```bash
# Required argument
cub run --task <task-id>

# Optional arguments
cub monitor [session-id]

# Multiple options
cub run --harness claude --once --stream
```

---

## Environment Variables

Cub respects several environment variables for configuration:

### Core Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CUB_DEBUG` | Enable debug mode | `false` |
| `CUB_BACKEND` | Task backend (`beads`, `json`) | auto-detect |
| `CUB_HARNESS` | Default harness to use | auto-detect |
| `CUB_PROJECT_DIR` | Project directory | current directory |

### Budget Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CUB_BUDGET` | Maximum budget in USD | from config |
| `CUB_BUDGET_TOKENS` | Maximum token budget | from config |
| `CUB_MAX_ITERATIONS` | Maximum loop iterations | `100` |

### Harness Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | API key for Claude |
| `OPENAI_API_KEY` | API key for Codex/GPT |
| `GOOGLE_API_KEY` | API key for Gemini |

### Path Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CUB_CONFIG_DIR` | Configuration directory | `~/.config/cub` |
| `CUB_DATA_DIR` | Data directory | `~/.local/share/cub` |
| `CUB_CACHE_DIR` | Cache directory | `~/.cache/cub` |
| `CUB_BASH_PATH` | Path to bash cub script | bundled |

### Example Usage

```bash
# Run with specific harness
CUB_HARNESS=claude cub run

# Set budget limits
CUB_BUDGET=10.00 CUB_MAX_ITERATIONS=50 cub run

# Use different config directory
CUB_CONFIG_DIR=/custom/path cub init --global

# Enable debug mode via environment
CUB_DEBUG=true cub status
```

---

## Exit Codes

Cub commands return meaningful exit codes:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Usage error (invalid arguments) |
| `130` | Interrupted (Ctrl+C) |

### Scripting Example

```bash
#!/bin/bash
cub run --once

case $? in
    0) echo "Task completed successfully" ;;
    1) echo "Task failed or error occurred" ;;
    130) echo "Interrupted by user" ;;
esac
```

---

## Configuration Precedence

When the same setting is available in multiple places, Cub uses this precedence (highest to lowest):

1. **Command-line flags** - `cub run --harness claude`
2. **Environment variables** - `CUB_HARNESS=claude`
3. **Project config** - `.cub.json` or `.cub/config.json`
4. **Global config** - `~/.config/cub/config.json`
5. **Built-in defaults**

### Example

```bash
# CLI flag takes precedence over everything
CUB_HARNESS=codex cub run --harness claude
# Uses claude (CLI flag wins)
```

---

## Shell Completion

Enable tab completion for your shell:

=== "Bash"

    ```bash
    # Add to ~/.bashrc
    eval "$(_CUB_COMPLETE=bash_source cub)"
    ```

=== "Zsh"

    ```bash
    # Add to ~/.zshrc
    eval "$(_CUB_COMPLETE=zsh_source cub)"
    ```

=== "Fish"

    ```bash
    # Add to ~/.config/fish/completions/cub.fish
    _CUB_COMPLETE=fish_source cub | source
    ```

---

## Getting Help

Every command supports the `--help` flag:

```bash
cub --help           # General help
cub run --help       # Help for run command
cub plan --help      # Help for plan command
```

For troubleshooting, see:

- [Common Issues](../troubleshooting/common.md)
- [Error Reference](../troubleshooting/errors.md)
- [FAQ](../troubleshooting/faq.md)

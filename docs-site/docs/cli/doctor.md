---
title: cub doctor
description: Diagnose and fix configuration issues with your cub installation and project setup.
---

# cub doctor

Diagnose and optionally fix common cub issues, configuration problems, and project setup.

## Synopsis

```bash
cub doctor [OPTIONS]
```

## Description

The `cub doctor` command performs a comprehensive health check of your cub installation and project configuration. It checks for:

- **System Requirements**: Verifies required tools (bash, git, jq) are installed and accessible
- **AI Harnesses**: Checks which AI coding assistants (Claude, Codex, Gemini, OpenCode) are available
- **Optional Tools**: Reports on recommended tools (beads, docker, tmux, pipx)
- **Configuration**: Validates JSON syntax and checks for deprecated options in config files
- **Project Structure**: Verifies task backends, prompt files, and directory layout
- **Git State**: Categorizes uncommitted files and identifies cleanup opportunities
- **Task State**: Detects tasks stuck in "in_progress" status
- **Recommendations**: Suggests improvements for build commands, hooks, and project setup

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--verbose` | | Show detailed diagnostic information including file lists |
| `--fix` | | Automatically fix detected issues where safe |
| `--dry-run` | | Show what `--fix` would do without making changes |
| `--help` | `-h` | Show help message and exit |

## What It Checks

### System Requirements

The doctor verifies these required tools:

| Tool | Required | Purpose |
|------|----------|---------|
| Bash 3.2+ | Yes | Shell execution |
| git | Yes | Version control operations |
| jq | Yes | JSON parsing and manipulation |

### AI Harnesses

At least one AI harness is required. The doctor checks for:

- **claude** - Claude Code CLI
- **codex** - OpenAI Codex CLI
- **gemini** - Google Gemini CLI
- **opencode** - OpenCode CLI

### Optional Tools

These enhance cub functionality but are not required:

| Tool | Purpose |
|------|---------|
| beads (bd) | Advanced task management backend |
| docker | Sandbox mode for isolated execution |
| tmux | Dashboard mode for multi-panel display |
| pipx | Self-upgrade functionality |

### Configuration Files

The doctor validates:

- **Global config**: `~/.config/cub/config.json`
- **Project config**: `.cub.json`

It checks for:

- Valid JSON syntax
- Deprecated configuration options
- Missing required fields

### Project Structure

Verifies proper setup of:

- Task backend (`.beads/` directory or `prd.json`)
- Prompt file (`.cub/prompt.md`)
- Agent file (`.cub/agent.md`)
- `.cub/` directory
- Symlinks for new layout projects
- `.gitignore` patterns

### Git State

Categorizes uncommitted files into actionable groups:

| Category | Description | Action |
|----------|-------------|--------|
| Session files | `progress.txt`, `fix_plan.md` | Safe to commit with `--fix` |
| Source code | `.py`, `.js`, `.ts`, etc. | Review before committing |
| Cruft | `.bak`, `.tmp`, `.DS_Store` | Safe to clean |
| Config files | Configuration changes | Review carefully |
| Cub artifacts | `.beads/`, `.cub/` | Safe to commit with `--fix` |

## Reading the Output

The doctor uses status indicators to communicate findings:

| Indicator | Meaning |
|-----------|---------|
| `[OK]` (green) | Check passed, no issues |
| `[!!]` (yellow) | Warning, may need attention |
| `[--]` (blue) | Informational, optional item |
| `[XX]` (red) | Error, requires action |

## Fix Actions

When you run `cub doctor --fix`, it will:

1. **Commit session files** with message "chore: commit session files"
2. **Commit cub artifacts** (`.beads/`, `.cub/` changes)
3. **Report files needing manual review** (source code, config files)
4. **Suggest `.gitignore` patterns** for cruft files

The `--dry-run` flag shows what would be fixed without making changes.

## Fixing Common Issues

### No AI harness found

Install at least one supported harness:

```bash
# Claude Code (recommended)
# Visit: https://console.anthropic.com

# Or install Codex
npm install -g @openai/codex

# Or Gemini
pip install google-generativeai
```

### jq not installed

```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# Fedora/RHEL
sudo dnf install jq
```

### No task backend found

Initialize your project with a task backend:

```bash
# Using beads (recommended)
bd init

# Or use JSON backend
cub init
```

### Tasks stuck in progress

Reset stuck tasks manually:

```bash
# With beads
bd update <task-id> --status open

# Or check task status
cub status
```

### Missing prompt.md or agent.md

Re-run project initialization:

```bash
cub init
```

### Configuration has deprecated options

Update your config files to use current option names. The doctor output shows the deprecated option and its replacement.

## Examples

### Basic diagnostics

```bash
cub doctor
```

Output:
```
System Requirements:
[OK] Bash v5.2
[OK] git v2.43.0
[OK] jq v1.7

AI Harnesses:
[OK] claude - v1.0.5

Optional Tools:
[OK] beads (bd) - v0.8.0
[--] docker not installed (optional, for 'cub run --sandbox')
[OK] tmux - v3.4

Configuration Files:
[OK] Global config valid JSON (~/.config/cub/config.json)
[OK] Project config valid JSON (.cub.json)

Project Structure:
[OK] .beads/ directory found (12 tasks)
[OK] prompt.md found (new layout)
[OK] agent.md found (new layout)

Git State:
[OK] Working directory clean

Task State:
[OK] No tasks stuck in progress

Recommendations:
[OK] No recommendations at this time

[OK] No issues found
```

### Detailed verbose output

```bash
cub doctor --verbose
```

Shows file-by-file breakdown of issues.

### Preview fixes

```bash
cub doctor --dry-run
```

Output:
```
Fix Mode:
[--] Would commit 3 session files
[--] Would commit cub artifacts
```

### Auto-fix safe issues

```bash
cub doctor --fix
```

Commits session files and cub artifacts automatically.

## Related Commands

- [`cub init`](init.md) - Initialize cub in a project
- [`cub status`](status.md) - Check task progress
- [`cub upgrade`](upgrade.md) - Upgrade cub to newer version
- [`cub status`](status.md) - Check task and project status

## See Also

- [Getting Started](../getting-started/quickstart.md) - Initial setup guide
- [Configuration](../guide/configuration/index.md) - Configuration options
- [Troubleshooting](../troubleshooting/index.md) - Common issues and solutions

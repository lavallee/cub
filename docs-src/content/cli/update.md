---
title: cub update
description: Update project templates and Claude Code skills to the latest versions.
---

# cub update

Update project templates and Claude Code skills from the installed cub package.

## Synopsis

```bash
cub update [OPTIONS]
```

## Description

The `cub update` command updates the `.cub/` directory files and `.claude/commands/` skills in your project to match the versions bundled with your cub installation.

This is different from `cub system-upgrade`, which upgrades cub itself. Use `cub update` after upgrading cub to get the latest templates and skills in your project.

By default, only files that haven't been locally modified are updated. Modified files are skipped to preserve your customizations.

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--dry-run` | `-n` | Show what would be updated without making changes |
| `--force` | `-f` | Overwrite all files, including modified ones |
| `--skills-only` | `-s` | Only update Claude Code skills, not .cub templates |
| `--templates-only` | `-t` | Only update .cub templates, not skills |
| `--help` | | Show help message and exit |

## What Gets Updated

### .cub/ Templates

Files in the `.cub/` directory:

| File | Description |
|------|-------------|
| `prompt.md` | System prompt template |
| `agent.md` | Build/run instructions for AI |
| `progress.txt` | Progress tracking |
| `fix_plan.md` | Issue tracking |
| `guardrails.md` | Project constraints |
| `README.md` | Quick reference guide |

### Claude Code Skills

Files in `.claude/commands/`:

| File | Description |
|------|-------------|
| `cub:architect.md` | Technical architecture skill |
| `cub:plan.md` | Task decomposition skill |
| `cub:triage.md` | Requirements refinement skill |
| `cub:spec.md` | Feature specification skill |

## Examples

### Preview changes

```bash
cub update --dry-run
```

Output:
```
Files to Update
┌─────────────────────────────┬────────┐
│ File                        │ Status │
├─────────────────────────────┼────────┤
│ .claude/commands/cub:spec.md│ new    │
│ .cub/prompt.md              │ update │
└─────────────────────────────┴────────┘

Run without --dry-run to apply changes
```

### Update unmodified files

```bash
cub update
```

Output:
```
Updated 2 file(s)

Skipped 3 modified file(s):
  .cub/agent.md
  .cub/guardrails.md
  .cub/README.md

Use --force to overwrite modified files
```

### Force update all files

```bash
cub update --force
```

Overwrites all files, including those you've customized.

### Update only skills

```bash
cub update --skills-only
```

Only updates files in `.claude/commands/`, leaving `.cub/` untouched.

### Update only templates

```bash
cub update --templates-only
```

Only updates files in `.cub/`, leaving `.claude/commands/` untouched.

## Workflow

A typical upgrade workflow:

```bash
# 1. Upgrade cub itself
cub system-upgrade

# 2. Update project templates/skills
cub update --dry-run  # Preview changes
cub update            # Apply updates
```

## Handling Modified Files

When a file has been locally modified:

- **Default behavior**: Skip the file and show a warning
- **With --force**: Overwrite with the new version (loses your changes)

To preserve modifications while getting updates:

1. Back up your modified files
2. Run `cub update --force`
3. Manually merge your changes back

## Related Commands

- [`cub system-upgrade`](system-upgrade.md) - Upgrade cub installation
- [`cub init`](init.md) - Initialize cub in a project
- [`cub doctor`](doctor.md) - Diagnose configuration issues

## See Also

- [Configuration](../guide/configuration/index.md) - Customizing templates
- [Skills Reference](../guide/skills/index.md) - Claude Code skills

---
title: cub uninstall
description: Remove cub from your system and optionally clean up configuration files.
---

# cub uninstall

Remove cub from your system and optionally clean up configuration files.

## Synopsis

```bash
cub uninstall [OPTIONS]
```

## Description

The `cub uninstall` command removes cub from your system. It automatically detects how cub was installed (pipx, pip, or editable mode) and uses the appropriate uninstall method.

By default, only the cub package is removed. Configuration files and data directories are preserved unless you specify `--clean`.

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--clean` | `-c` | Also remove configuration files and data directories |
| `--force` | `-f` | Skip confirmation prompts |
| `--dry-run` | `-n` | Show what would be done without making changes |
| `--help` | `-h` | Show help message and exit |

## What Gets Removed

### Package Uninstall

The basic uninstall removes:

- The `cub` command-line tool
- Python package files from site-packages (or pipx venv)
- Command aliases and shell integrations

### With --clean Flag

When `--clean` is specified, also removes:

| Path | Description |
|------|-------------|
| `~/.config/cub/` | Global configuration directory |
| `~/.local/share/cub/` | Data directory (captures, logs) |
| `~/.cub/` | Legacy configuration directory |

### What Is NOT Removed

The uninstall does not remove:

- Project-level `.cub.json` files
- Project-level `.cub/` directories
- Project-level `captures/` directories
- `.beads/` task data
- Any files in your repositories

## Confirmation

By default, the command asks for confirmation before proceeding:

```
Actions to perform:
  - Run: pipx uninstall cub

Proceed with uninstall? [y/N]:
```

Use `--force` to skip this confirmation.

## Examples

### Basic uninstall

```bash
cub uninstall
```

Output:
```
cub v0.26.3
Installed via: pipx

Actions to perform:
  - Run: pipx uninstall cub

Proceed with uninstall? [y/N]: y

Uninstalling with pipx...
Package uninstalled successfully

Uninstall complete!
```

### Preview what would be removed

```bash
cub uninstall --dry-run
```

Output:
```
cub v0.26.3
Installed via: pip

Actions to perform:
  - Run: pip uninstall cub

Dry run - no changes made
```

### Uninstall with configuration cleanup

```bash
cub uninstall --clean
```

Output:
```
cub v0.26.3
Installed via: pipx

Actions to perform:
  - Run: pipx uninstall cub
  - Remove configuration directories:
    - /home/user/.config/cub
    - /home/user/.local/share/cub

Proceed with uninstall? [y/N]: y

Uninstalling with pipx...
Package uninstalled successfully

Removing configuration directories...
  Removed: /home/user/.config/cub
  Removed: /home/user/.local/share/cub

Uninstall complete!
```

### Force uninstall without prompts

```bash
cub uninstall --force
```

Skips the confirmation prompt. Use with caution.

### Full cleanup without prompts

```bash
cub uninstall --clean --force
```

Removes everything without asking.

## Editable Installations

If cub was installed in editable mode (for development):

```
Editable install detected
For editable installs, simply remove the source directory
or run: pip uninstall cub
```

For editable installs, you can either:

1. Run `pip uninstall cub` directly
2. Remove the source directory
3. Use `cub uninstall --force` to proceed anyway

## Manual Cleanup Steps

If the automatic uninstall fails or you need to clean up manually:

### Remove the package

```bash
# If installed with pipx
pipx uninstall cub

# If installed with pip
pip uninstall cub
```

### Remove configuration files

```bash
# Remove config directory
rm -rf ~/.config/cub

# Remove data directory
rm -rf ~/.local/share/cub

# Remove legacy config
rm -rf ~/.cub
```

### Verify removal

```bash
# Check if cub is still available
which cub
# Should return nothing or "cub not found"

# Try running cub
cub --version
# Should fail with "command not found"
```

## Reinstalling After Uninstall

To reinstall cub after uninstalling:

```bash
# With pipx (recommended)
pipx install cub

# With pip
pip install cub

# Or using the install script
curl -LsSf https://docs.cub.tools/install.sh | bash
```

If you used `--clean`, you'll need to re-run global setup:

```bash
cub init --global
```

## Related Commands

- [`cub system-upgrade`](system-upgrade.md) - Upgrade cub installation
- [`cub doctor`](doctor.md) - Diagnose installation issues
- [`cub init`](init.md) - Initialize configuration after reinstall

## See Also

- [Installation Guide](../getting-started/install.md) - Reinstallation instructions
- [Configuration](../guide/configuration/index.md) - Understanding config files

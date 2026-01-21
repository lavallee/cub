---
title: cub system-upgrade
description: Upgrade cub to a newer version or reinstall from local source.
---

# cub system-upgrade

Upgrade cub to a newer version or reinstall from local source for development.

## Synopsis

```bash
cub system-upgrade [OPTIONS]
```

## Description

The `cub system-upgrade` command updates your cub installation to a newer version. It automatically detects how cub was installed (pipx, pip, or editable mode) and uses the appropriate upgrade method.

The command supports several workflows:

- **Upgrade to latest**: Default behavior, upgrades to the newest release
- **Install specific version**: Pin to a particular version with `--version`
- **Local development**: Install from a local repository with `--local`
- **Editable mode**: Install for development with live code changes using `--editable`

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--local` | `-l` | Install from current directory (must be a cub repository) |
| `--check` | `-c` | Check for updates without installing |
| `--force` | `-f` | Force reinstall even if same version |
| `--version VERSION` | `-v` | Install specific version (e.g., `0.23.3`) |
| `--editable` | `-e` | Install in editable/development mode (implies `--local`) |
| `--help` | `-h` | Show help message and exit |

## Installation Methods

The upgrade command detects how cub was originally installed:

| Method | Detection | Upgrade Command |
|--------|-----------|-----------------|
| pipx | `pipx list` contains cub | `pipx upgrade cub` |
| pip | cub importable from site-packages | `pip install --upgrade cub` |
| editable | cub not in site-packages | Prompts to use `--local` |

### pipx Installation

If you installed cub with pipx (recommended), upgrades use:

```bash
pipx upgrade cub
# Or with --force:
pipx install cub --force
```

### pip Installation

For pip installations:

```bash
pip install --upgrade cub
# Or with --force:
pip install --upgrade --force-reinstall cub
```

### Editable Installation

Editable installs are typically development setups. For these:

1. The command prompts you to use `--local` or `git pull`
2. Changes to the source code take effect immediately
3. No reinstall needed for most changes

## Version Checking

Check your current version:

```bash
cub version
# Output: cub version 0.26.3
```

Check available versions:

```bash
pip index versions cub
```

## Examples

### Upgrade to latest release

```bash
cub system-upgrade
```

Output:
```
cub v0.26.2
Installed via: pipx

Upgrading to latest version...
Upgrade complete!
Updated: v0.26.2 -> v0.26.3
```

### Check for updates

```bash
cub system-upgrade --check
```

Shows whether updates are available without installing.

### Install specific version

```bash
cub system-upgrade --version 0.25.0
```

Useful for testing or pinning to a known-good version.

### Force reinstall

```bash
cub system-upgrade --force
```

Reinstalls even if already at the latest version. Useful for repairing broken installations.

### Install from local repository

For developers working on cub:

```bash
# Clone the repo
git clone https://github.com/lavallee/cub.git
cd cub

# Install from local source
cub system-upgrade --local
```

### Install in editable mode

For active cub development where you want changes to take effect immediately:

```bash
cd /path/to/cub
cub system-upgrade --editable
```

This runs `pip install -e .` which links the package to your source directory.

### Force local reinstall

```bash
cd /path/to/cub
cub system-upgrade --local --force
```

Reinstalls from local even if versions match.

## Troubleshooting

### "Current directory is not a cub repository"

When using `--local`, you must run from a directory containing cub source code:

```bash
# Verify it's a cub repository
ls pyproject.toml src/cub/

# Should see:
# pyproject.toml
# src/cub/
```

### Editable install detected

If you see:

```
Editable install detected - use --local to update
Or pull latest changes: git pull
```

Your cub is installed in development mode. Either:

1. Pull latest changes: `git pull`
2. Reinstall with: `cub system-upgrade --local`

### Version mismatch after upgrade

If the version doesn't change after upgrade:

1. Check if the correct pip/pipx is in your PATH
2. Try `cub system-upgrade --force`
3. Verify with `which cub` and `cub version`

### Permission denied

If you get permission errors:

```bash
# With pipx (recommended)
pipx upgrade cub

# With pip using user install
pip install --user --upgrade cub
```

## Related Commands

- `cub --version` - Show current version
- [`cub doctor`](doctor.md) - Diagnose installation issues
- [`cub uninstall`](uninstall.md) - Remove cub from your system

## See Also

- [Installation Guide](../getting-started/install.md) - Initial installation
- [Upgrading Guide](../getting-started/upgrading.md) - Detailed upgrade information
- [Contributing](../contributing/index.md) - Development setup

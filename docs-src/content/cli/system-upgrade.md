---
title: cub system-upgrade
description: Upgrade cub to a newer version with multiple installation strategies.
---

# cub system-upgrade

Upgrade your cub installation to a newer version, or check for available updates.

---

## Synopsis

```bash
cub system-upgrade [OPTIONS]
```

---

## Description

The `system-upgrade` command manages cub version upgrades. It supports multiple installation strategies:

- **Remote install**: Download and install the latest release from the repository
- **Local install**: Install from a local clone of the cub repository
- **Editable install**: Install in development mode with live source changes
- **Version pinning**: Install a specific version

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--local` | `-l` | Install from current directory (must be a cub repository) |
| `--check` | `-c` | Check for updates without installing |
| `--force` | `-f` | Force reinstall even if same version |
| `--version TEXT` | `-v` | Install specific version (e.g., `0.23.3`) |
| `--editable` | `-e` | Install in editable/development mode (implies `--local`) |
| `--help` | `-h` | Show help message and exit |

---

## Examples

### Check for Updates

```bash
# See if a newer version is available
cub system-upgrade --check
```

### Standard Upgrade

```bash
# Upgrade to latest version
cub system-upgrade
```

### Install Specific Version

```bash
# Pin to a specific release
cub system-upgrade --version 0.28.0
```

### Developer Install

```bash
# Install from local repo in editable mode
cd ~/clawdbot/cub
cub system-upgrade --editable
```

### Force Reinstall

```bash
# Reinstall current version (useful for fixing corrupted installs)
cub system-upgrade --force
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Upgrade successful (or already up to date) |
| `1` | Upgrade failed |

---

## Related Commands

- [`cub version`](version.md) - Show current version
- [`cub doctor`](doctor.md) - Diagnose installation issues

---

## See Also

- [Installation Guide](../getting-started/install.md) - Complete installation instructions
- [Upgrading Guide](../getting-started/upgrading.md) - Migration notes between versions

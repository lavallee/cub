---
title: cub map
description: Generate an AI-digestible project map with structure analysis and code intelligence.
---

# cub map

Generate a project map that provides an AI-digestible overview of the codebase, including tech stacks, build commands, module boundaries, and important symbols.

---

## Synopsis

```bash
cub map [PROJECT_DIR] [OPTIONS]
```

---

## Description

The `map` command analyzes your project structure and generates a concise map at `.cub/map.md`. This map is referenced by AI agents (via `@.cub/map.md`) to understand the codebase without reading every file.

The map includes:

- Tech stack detection and build commands
- Directory structure with depth control
- Key files and entry points
- Important symbols ranked by PageRank analysis
- Optionally, ledger statistics

This command is typically called automatically by `cub init` and `cub update`, but can be run standalone to regenerate the map.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Arguments

| Argument | Description |
|----------|-------------|
| `PROJECT_DIR` | Project directory to analyze (default: current directory) |

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output TEXT` | `-o` | Output file path (default: `.cub/map.md`) |
| `--token-budget INTEGER` | `-t` | Maximum token budget for the map (default: `4096`) |
| `--max-depth INTEGER` | `-d` | Maximum directory tree depth (default: `4`) |
| `--include-ledger` | `-l` | Include ledger statistics in the map |
| `--force` | `-f` | Overwrite existing map file |
| `--debug` | | Show debug output |
| `--help` | `-h` | Show help message and exit |

---

## Examples

```bash
# Generate map at default location
cub map

# Custom output path
cub map --output mymap.md

# Larger token budget for bigger projects
cub map --token-budget 8192

# Include ledger stats
cub map --include-ledger

# Overwrite existing map
cub map --force
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Map generated successfully |
| `1` | Error during generation |

---

## Related Commands

- [`cub init`](../init.md) - Generates map automatically during initialization
- [`cub doctor`](../doctor.md) - Verify map file exists and is current

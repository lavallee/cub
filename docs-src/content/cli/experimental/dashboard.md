---
title: cub dashboard
description: Launch a project Kanban dashboard with web-based visualization.
---

# cub dashboard

Launch a web-based Kanban dashboard that visualizes project state across 8 workflow stages.

---

## Synopsis

```bash
cub dashboard [OPTIONS] [COMMAND]
```

---

## Description

The `dashboard` command aggregates data from multiple sources (specs, plans, tasks, ledger, changelog) and presents a unified Kanban board in your browser. Entities flow through stages from CAPTURES through RELEASED.

The dashboard runs a local FastAPI server and opens your browser automatically.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--port INTEGER` | `-p` | Port to run the server on (default: `8080`) |
| `--no-browser` | | Don't open browser automatically |
| `--no-sync` | | Skip initial data sync |
| `--help` | `-h` | Show help message and exit |

---

## Subcommands

### sync

Sync project data to the dashboard database without starting the server.

```bash
cub dashboard sync
```

### export

Export the current board data as JSON.

```bash
cub dashboard export
```

### views

List available dashboard view configurations.

```bash
cub dashboard views
```

### init

Initialize the dashboard with example view configurations.

```bash
cub dashboard init
```

---

## Examples

```bash
# Launch dashboard on default port
cub dashboard

# Use a different port
cub dashboard --port 3000

# Sync data without launching the server
cub dashboard sync

# Export board state for scripting
cub dashboard export > board.json
```

---

## Related Commands

- [`cub status`](../status.md) - Terminal-based status view
- [`cub monitor`](../monitor.md) - Live run monitoring

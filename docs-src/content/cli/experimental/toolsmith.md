---
title: cub toolsmith
description: Discover, catalog, and adopt tools from external sources.
---

# cub toolsmith

Discover tools from external sources, search the catalog, and adopt tools for your project.

---

## Synopsis

```bash
cub toolsmith [COMMAND]
```

---

## Description

The `toolsmith` command manages tool discovery and cataloging. It syncs tool definitions from external sources (MCP servers, API directories, local scripts) into a searchable catalog, and lets you adopt tools for use in your project.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Subcommands

### sync

Sync tools from external sources into the tool catalog.

```bash
cub toolsmith sync
```

### search

Search for tools by name, description, or capability.

```bash
cub toolsmith search <query>
```

### adopt

Adopt a tool for use in this project.

```bash
cub toolsmith adopt <tool-name>
```

### run

Run an adopted tool (experimental).

```bash
cub toolsmith run <tool-name> [ARGS]
```

### adopted

List tools adopted for this project.

```bash
cub toolsmith adopted
```

### stats

Show statistics about the tool catalog.

```bash
cub toolsmith stats
```

---

## Examples

```bash
# Sync catalog from external sources
cub toolsmith sync

# Search for tools
cub toolsmith search "github"

# Adopt a tool for your project
cub toolsmith adopt github-issues

# See what you've adopted
cub toolsmith adopted
```

---

## Related Commands

- [`cub tools`](tools.md) - Execute adopted tools

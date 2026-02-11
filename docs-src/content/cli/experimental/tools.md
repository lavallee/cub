---
title: cub tools
description: Manage and execute tools via the unified tool runtime.
---

# cub tools

Manage, inspect, and execute tools through cub's unified tool runtime with pluggable adapters (HTTP, CLI, MCP).

---

## Synopsis

```bash
cub tools [COMMAND]
```

---

## Description

The `tools` command provides access to cub's unified tool runtime. Tools are external capabilities (APIs, CLI commands, MCP servers) that agents can invoke during task execution. The tool runtime handles discovery, approval, execution, and metrics tracking.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Subcommands

### list

List all available tool adapters and their status.

```bash
cub tools list
```

### check

Check if a specific tool is ready to execute.

```bash
cub tools check <tool-name>
```

### run

Execute a tool with the specified adapter.

```bash
cub tools run <adapter> <tool-name> [ARGS]
```

### artifacts

List execution artifacts from previous tool runs.

```bash
cub tools artifacts
```

### stats

View tool effectiveness metrics (execution count, success rate, latency).

```bash
cub tools stats
```

### configure

Configure the freedom dial and manage tool approvals.

```bash
cub tools configure
```

---

## Examples

```bash
# See what tools are available
cub tools list

# Check if a specific tool works
cub tools check github-api

# View execution statistics
cub tools stats
```

---

## Related Commands

- [`cub toolsmith`](toolsmith.md) - Discover and catalog new tools
- [`cub run`](../run.md) - Tools are invoked during task execution

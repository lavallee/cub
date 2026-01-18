---
title: Getting Started
description: Everything you need to get Cub installed and running your first autonomous coding session.
---

# Getting Started

Welcome to Cub! This section will help you go from zero to running your first autonomous coding session.

## What You'll Learn

<div class="feature-grid" markdown>

<div class="feature-card" markdown>

#### [Installation](install.md)

Get Cub installed using our one-liner installer, pipx, uv, or from source. Verify your setup and configure global settings.

</div>

<div class="feature-card" markdown>

#### [Quick Start](quickstart.md)

A 5-minute guide to initializing a project, creating tasks, and running your first autonomous loop.

</div>

<div class="feature-card" markdown>

#### [Core Concepts](concepts.md)

Understand the "prep and run" workflow, task backends, harnesses, and how all the pieces fit together.

</div>

<div class="feature-card" markdown>

#### [Upgrading](upgrading.md)

Moving from an older version? Migration guides and breaking changes you should know about.

</div>

</div>

---

## The 60-Second Overview

**Cub** wraps AI coding CLIs (Claude Code, Codex, Gemini) to provide a reliable "set and forget" loop for autonomous coding sessions.

### The Problem

You want to use AI coding agents, but:

- **Too hands-on**: Sitting in an IDE, approving every tool call
- **Too hands-off**: Vague instructions, hoping the agent figures it out

### The Solution

Cub helps you work *ahead* of execution so you can be more hands-off *during* execution:

1. **Prep** - Turn your ideas into structured, agent-sized tasks
2. **Run** - Let Cub execute tasks autonomously

```bash
# Install
curl -LsSf https://install.cub.tools | bash

# Setup
cub init --global
cd my-project && cub init

# Prep your work
cub prep

# Let it run
cub run
```

---

## Prerequisites

Before installing Cub, make sure you have:

| Requirement | Notes |
|-------------|-------|
| **Python 3.10+** | Required. Check with `python3 --version` |
| **At least one harness** | Claude Code, Codex, Gemini, or OpenCode |

!!! info "Harness Installation"
    Cub doesn't include AI harnesses - you need to install at least one separately. [Claude Code](https://github.com/anthropics/claude-code) is recommended for both `cub prep` (required) and `cub run`.

---

## Next Steps

Ready to dive in?

1. **[Install Cub](install.md)** - Get Cub on your system
2. **[Quick Start](quickstart.md)** - Run your first session
3. **[Core Concepts](concepts.md)** - Understand how it all works

Or jump straight to the [User Guide](../guide/index.md) if you want comprehensive coverage of all features.

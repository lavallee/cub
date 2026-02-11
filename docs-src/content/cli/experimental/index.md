---
title: Experimental Commands
description: CLI commands that are functional but not yet part of the mainline workflow.
---

# Experimental Commands

These commands are real, functional parts of cub that you can use today. They are marked "experimental" because their interfaces may change, they may have rough edges, or they haven't been through the stabilization process that mainline commands have.

!!! note "What experimental means"
    Experimental does not mean broken. It means: the command works, but we reserve the right to change flags, subcommand names, or behavior in future releases without a deprecation cycle.

---

## Available Experimental Commands

| Command | Description |
|---------|-------------|
| [`cub dashboard`](dashboard.md) | Launch project Kanban dashboard with web UI |
| [`cub tools`](tools.md) | Manage and execute tools via the unified tool runtime |
| [`cub toolsmith`](toolsmith.md) | Discover, catalog, and adopt tools |
| [`cub workflow`](workflow.md) | Manage post-completion workflow stages |
| [`cub sandbox`](sandbox.md) | Manage Docker sandboxes for isolated execution |
| [`cub audit`](audit.md) | Run code health audits |
| [`cub guardrails`](guardrails.md) | Display and manage institutional memory |
| [`cub checkpoints`](checkpoints.md) | Manage review/approval gates |
| [`cub triage`](triage.md) | Refine requirements through interactive questions |
| [`cub import`](import.md) | Import tasks from external sources |
| [`cub map`](map.md) | Generate a project map with structure analysis |
| [`cub learn`](../learn.md) | Extract patterns and lessons from ledger |
| [`cub retro`](../retro.md) | Generate retrospective reports |
| [`cub suggest`](../suggest.md) | Smart recommendations for next actions |
| [`cub verify`](../verify.md) | Verify cub data integrity |
| [`cub release`](../release.md) | Mark plans as released and update changelog |

---

## Promotion Path

Experimental commands are promoted to mainline when they meet these criteria:

1. **Stable interface** — flags and subcommands haven't changed in 2+ releases
2. **Test coverage** — meets the moderate tier (60%+) in STABILITY.md
3. **Documentation** — complete CLI reference page with examples
4. **User adoption** — at least one project uses the command regularly

---
title: cub guardrails
description: Display and manage institutional memory that guides autonomous execution.
---

# cub guardrails

Display and manage guardrails — documented constraints, patterns, and best practices shown to AI agents before each run.

---

## Synopsis

```bash
cub guardrails [OPTIONS]
```

---

## Description

Guardrails are institutional memory: rules and patterns that agents should follow during autonomous execution. They are injected into the system prompt so the AI harness is aware of project-specific constraints.

This command is delegated to the bash implementation.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Examples

```bash
# Show all guardrails
cub guardrails

# Add a new guardrail
cub guardrails --add "Always run tests before committing"

# Remove a guardrail
cub guardrails --remove <id>
```

---

## Related Commands

- [`cub run`](../run.md) - Guardrails are injected during execution
- [`cub init`](../init.md) - Initialize project with default guardrails

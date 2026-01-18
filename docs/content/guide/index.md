# User Guide

The User Guide provides comprehensive documentation for using Cub effectively. Whether you are setting up your first autonomous coding session or optimizing complex workflows, these guides will help you get the most out of Cub.

## Guide Sections

<div class="grid cards" markdown>

-   :material-cog: **Configuration**

    ---

    Learn how to configure Cub for your environment and projects. Covers config files, environment variables, and precedence rules.

    [:octicons-arrow-right-24: Configuration](configuration/index.md)

-   :material-clipboard-list: **Task Management**

    ---

    Understand how Cub manages tasks using different backends. Learn about task states, dependencies, and filtering.

    [:octicons-arrow-right-24: Task Management](tasks/index.md)

-   :material-sync: **The Run Loop**

    ---

    Dive into Cub's core execution loop. Learn how tasks are selected, executed, and completed.

    [:octicons-arrow-right-24: Run Loop](run-loop/index.md)

-   :material-magic-staff: **Prep Pipeline**

    ---

    Transform visions into executable tasks. Use triage, architect, plan, and bootstrap to prepare your work.

    [:octicons-arrow-right-24: Prep Pipeline](prep-pipeline/index.md)

-   :material-robot: **AI Harnesses**

    ---

    Configure and use different AI assistants: Claude Code, OpenAI Codex, Google Gemini, and OpenCode.

    [:octicons-arrow-right-24: AI Harnesses](harnesses/index.md)

-   :material-source-branch: **Git Integration**

    ---

    Manage branches, create pull requests, and use worktrees for parallel development.

    [:octicons-arrow-right-24: Git Integration](git/index.md)

-   :material-hook: **Hooks System**

    ---

    Extend Cub with custom scripts that run at key points in the task lifecycle.

    [:octicons-arrow-right-24: Hooks System](hooks/index.md)

-   :material-shield-check: **Budget & Guardrails**

    ---

    Control costs with token budgets and prevent runaway loops with iteration limits.

    [:octicons-arrow-right-24: Budget & Guardrails](budget/index.md)

-   :material-rocket-launch: **Advanced Topics**

    ---

    Explore sandbox mode, parallel execution, captures, and audit logging.

    [:octicons-arrow-right-24: Advanced](advanced/index.md)

</div>

## Quick Links

| Topic | Description |
|-------|-------------|
| [Configuration Reference](configuration/reference.md) | Complete reference for all config options |
| [Environment Variables](configuration/env-vars.md) | All supported environment variables |
| [Beads Backend](tasks/beads.md) | Primary task management backend |
| [Claude Code Harness](harnesses/claude.md) | Using Claude Code with Cub |
| [Hook Examples](hooks/examples.md) | Ready-to-use hook scripts |

## Common Workflows

### Starting a New Project

1. Initialize Cub globally: `cub init --global`
2. Create project config: `cub init` in your project
3. Prepare tasks: `cub prep` to run the vision-to-tasks pipeline
4. Execute: `cub run` to start autonomous execution

### Daily Development

```bash
# Check what's ready to run
cub status --ready

# Run a single task for testing
cub run --once

# Run with live output
cub run --stream

# Monitor progress in another terminal
cub monitor
```

### CI/CD Integration

```bash
# Deterministic execution for CI
export CUB_BUDGET=2000000
export CUB_MAX_ITERATIONS=50
cub run --harness claude --require-clean
```

## Getting Help

- **Troubleshooting**: See the [Troubleshooting Guide](../troubleshooting/index.md) for common issues
- **CLI Reference**: See the [CLI Reference](../cli/index.md) for command details
- **Contributing**: See [Contributing](../contributing/index.md) to help improve Cub

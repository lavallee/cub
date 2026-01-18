# Configuration

Cub uses a layered configuration system that allows you to set defaults globally, override them per-project, and further customize via environment variables and CLI flags.

## Configuration Precedence

Configuration is loaded and merged in the following order, with later sources overriding earlier ones:

```mermaid
flowchart LR
    A[Defaults] --> B[Global Config]
    B --> C[Project Config]
    C --> D[Environment Variables]
    D --> E[CLI Flags]

    style E fill:#4CAF50,color:white
    style D fill:#8BC34A
    style C fill:#CDDC39
    style B fill:#FFEB3B
    style A fill:#FFC107
```

| Priority | Source | Location | Use Case |
|----------|--------|----------|----------|
| 1 (Lowest) | Hardcoded defaults | Built into Cub | Sensible starting point |
| 2 | Global config | `~/.config/cub/config.json` | User preferences |
| 3 | Project config | `.cub.json` in project root | Project-specific settings |
| 4 | Environment variables | Shell environment | Session overrides, CI/CD |
| 5 (Highest) | CLI flags | Command line | One-time overrides |

## Quick Setup

### Global Configuration

Set up your user-wide defaults:

```bash
cub init --global
```

This creates `~/.config/cub/config.json` with sensible defaults:

```json
{
  "harness": {
    "default": "auto",
    "priority": ["claude", "gemini", "codex", "opencode"]
  },
  "budget": {
    "default": 1000000,
    "warn_at": 0.8
  },
  "loop": {
    "max_iterations": 100
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": false
  },
  "hooks": {
    "enabled": true
  }
}
```

### Project Configuration

Create `.cub.json` in your project root to override global settings:

```bash
cd my-project
cub init
```

Or create manually:

```json
{
  "budget": {
    "default": 500000
  },
  "loop": {
    "max_iterations": 50
  },
  "clean_state": {
    "require_tests": true
  }
}
```

!!! tip "Partial Overrides"
    Project config only needs to include the settings you want to change. Unspecified settings fall through to global config or defaults.

## Directory Structure

Cub follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) for configuration and data:

```
~/.config/cub/
+-- config.json              # Global configuration
+-- hooks/                   # Global hook directories
    +-- pre-loop.d/
    +-- pre-task.d/
    +-- post-task.d/
    +-- on-error.d/
    +-- post-loop.d/

~/.local/share/cub/
+-- logs/                    # Session logs
    +-- {project}/
        +-- {session}.jsonl  # YYYYMMDD-HHMMSS format

~/.cache/cub/              # Cache directory

.cub.json                  # Project-level config (in project root)
.cub/hooks/                # Project-specific hooks (in project root)
```

## Configuration Sections

Cub configuration is organized into these sections:

| Section | Purpose |
|---------|---------|
| [`harness`](reference.md#harness-configuration) | AI assistant selection and priority |
| [`budget`](reference.md#budget-configuration) | Token budget and warning thresholds |
| [`loop`](reference.md#loop-configuration) | Execution loop limits |
| [`clean_state`](reference.md#clean-state-configuration) | Git commit and test requirements |
| [`task`](reference.md#task-configuration) | Task lifecycle behavior |
| [`hooks`](reference.md#hooks-configuration) | Hook system settings |
| [`guardrails`](reference.md#guardrails-configuration) | Safety limits and secret redaction |

## Next Steps

<div class="grid cards" markdown>

-   :material-book-open-variant: **Full Reference**

    ---

    Complete documentation of all configuration options with types, defaults, and examples.

    [:octicons-arrow-right-24: Reference](reference.md)

-   :material-console: **Environment Variables**

    ---

    All environment variables for runtime configuration and CI/CD integration.

    [:octicons-arrow-right-24: Environment Variables](env-vars.md)

-   :material-code-json: **Examples**

    ---

    Ready-to-use configuration examples for different scenarios.

    [:octicons-arrow-right-24: Examples](examples.md)

</div>

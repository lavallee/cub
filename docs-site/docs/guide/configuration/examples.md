# Configuration Examples

Ready-to-use configuration examples for common scenarios.

## Development Setup

A relaxed configuration for local development and testing:

```json title=".cub.json"
{
  "harness": {
    "default": "auto",
    "priority": ["claude", "gemini", "codex"]
  },
  "budget": {
    "default": 100000,
    "warn_at": 0.9
  },
  "loop": {
    "max_iterations": 20
  },
  "clean_state": {
    "require_commit": false,
    "require_tests": false,
    "auto_commit": true
  },
  "task": {
    "auto_close": true
  },
  "hooks": {
    "enabled": true,
    "fail_fast": false
  },
  "guardrails": {
    "max_task_iterations": 2,
    "max_run_iterations": 20
  }
}
```

**Characteristics:**

- Low token budget (100k) to limit costs during testing
- No commit or test requirements for rapid iteration
- Fewer iterations to fail fast on issues
- Auto-commit and auto-close enabled for convenience

**Usage:**

```bash
# Run with streaming to see output
cub run --stream

# Single task for quick testing
cub run --once
```

---

## Production Setup

A strict configuration for production-quality work:

```json title=".cub.json"
{
  "harness": {
    "default": "claude",
    "priority": ["claude", "codex"]
  },
  "budget": {
    "default": 5000000,
    "warn_at": 0.75
  },
  "loop": {
    "max_iterations": 200
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": true,
    "auto_commit": false
  },
  "task": {
    "auto_close": false
  },
  "hooks": {
    "enabled": true,
    "fail_fast": true
  },
  "guardrails": {
    "max_task_iterations": 5,
    "max_run_iterations": 100,
    "iteration_warning_threshold": 0.8,
    "secret_patterns": [
      "api[_-]?key",
      "password",
      "token",
      "secret",
      "authorization",
      "credentials",
      "private_key",
      "aws_secret",
      "webhook_url"
    ]
  }
}
```

**Characteristics:**

- High token budget (5M) for complex work
- Tests required before commits
- No auto-commit or auto-close (explicit agent action required)
- Hooks fail fast to catch issues early
- Extended secret patterns for security

**Usage:**

```bash
# Full production run
cub run

# Monitor in another terminal
cub monitor
```

---

## CI/CD Integration

Minimal, deterministic configuration for automated pipelines:

```json title=".cub.json"
{
  "harness": {
    "default": "claude"
  },
  "budget": {
    "default": 2000000
  },
  "loop": {
    "max_iterations": 50
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": true
  },
  "hooks": {
    "enabled": false
  }
}
```

**Characteristics:**

- Fixed harness (no auto-detection)
- Moderate budget with clear limits
- Strict clean state requirements
- Hooks disabled to avoid interactive prompts

**GitHub Actions Example:**

```yaml title=".github/workflows/cub.yml"
name: Cub Autonomous Coding

on:
  workflow_dispatch:
    inputs:
      epic:
        description: 'Epic ID to target'
        required: true

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Cub
        run: pip install cub-cli

      - name: Install Claude Code
        run: npm install -g @anthropic-ai/claude-code

      - name: Run Cub
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          CUB_EPIC: ${{ inputs.epic }}
          CUB_BUDGET: 2000000
          CUB_MAX_ITERATIONS: 50
        run: cub run

      - name: Create PR
        if: success()
        run: |
          git push origin HEAD
          gh pr create --fill
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Per-Model Overrides

Use environment variables to adjust settings based on model:

### Fast Tasks with Haiku

```bash
export CUB_MODEL=haiku
export CUB_BUDGET=50000
export CUB_MAX_TASK_ITERATIONS=2

cub run --label quick
```

### Complex Tasks with Opus

```bash
export CUB_MODEL=opus
export CUB_BUDGET=500000
export CUB_MAX_TASK_ITERATIONS=5

cub run --label complex
```

### Standard Tasks with Sonnet

```bash
export CUB_MODEL=sonnet
export CUB_BUDGET=200000

cub run
```

### Shell Script for Model Selection

```bash title="run-with-model.sh"
#!/bin/bash

case "$1" in
  quick)
    export CUB_MODEL=haiku
    export CUB_BUDGET=50000
    LABEL="--label quick"
    ;;
  complex)
    export CUB_MODEL=opus
    export CUB_BUDGET=500000
    LABEL="--label complex"
    ;;
  *)
    export CUB_MODEL=sonnet
    export CUB_BUDGET=200000
    LABEL=""
    ;;
esac

cub run $LABEL "${@:2}"
```

Usage:

```bash
./run-with-model.sh quick --once
./run-with-model.sh complex
./run-with-model.sh standard --epic phase-1
```

---

## Team Configuration

A balanced configuration for team use:

```json title=".cub.json"
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
    "require_tests": false,
    "auto_commit": true
  },
  "task": {
    "auto_close": true
  },
  "hooks": {
    "enabled": true,
    "fail_fast": false
  },
  "guardrails": {
    "max_task_iterations": 3,
    "max_run_iterations": 50
  }
}
```

**Global User Overrides** (`~/.config/cub/config.json`):

Each team member can override settings in their global config:

=== "Developer A (prefers Claude)"

    ```json
    {
      "harness": {
        "default": "claude"
      },
      "budget": {
        "default": 500000
      }
    }
    ```

=== "Developer B (prefers Gemini)"

    ```json
    {
      "harness": {
        "default": "gemini"
      },
      "budget": {
        "default": 750000
      }
    }
    ```

=== "Developer C (strict mode)"

    ```json
    {
      "clean_state": {
        "require_tests": true
      },
      "hooks": {
        "fail_fast": true
      }
    }
    ```

---

## Monorepo Setup

Configuration for a monorepo with multiple projects:

```json title=".cub.json (root)"
{
  "harness": {
    "default": "auto"
  },
  "budget": {
    "default": 2000000
  },
  "hooks": {
    "enabled": true
  }
}
```

Each subproject can have its own `.cub.json`:

```json title="packages/api/.cub.json"
{
  "clean_state": {
    "require_tests": true
  },
  "guardrails": {
    "max_task_iterations": 5
  }
}
```

```json title="packages/frontend/.cub.json"
{
  "clean_state": {
    "require_tests": false
  },
  "budget": {
    "default": 500000
  }
}
```

Run from subproject directory:

```bash
cd packages/api
cub run
```

---

## Minimal Configuration

The absolute minimum configuration (relies on defaults):

```json title=".cub.json"
{}
```

This uses all defaults:

- Auto harness selection
- 1M token budget
- 100 max iterations
- Commit required, tests not required
- Auto-commit and auto-close enabled
- Hooks enabled, fail-fast disabled

---

## Full Configuration Template

A complete template with all options:

```json title=".cub.json"
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
    "require_tests": false,
    "auto_commit": true
  },
  "task": {
    "auto_close": true
  },
  "hooks": {
    "enabled": true,
    "fail_fast": false
  },
  "guardrails": {
    "max_task_iterations": 3,
    "max_run_iterations": 50,
    "iteration_warning_threshold": 0.8,
    "secret_patterns": [
      "api[_-]?key",
      "password",
      "token",
      "secret",
      "authorization",
      "credentials"
    ]
  }
}
```

Copy this template and modify as needed for your project.

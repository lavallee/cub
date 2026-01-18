---
title: Troubleshooting
description: Diagnostic tools, common issues, and solutions for Cub problems.
---

# Troubleshooting

Having trouble with Cub? This section covers diagnostic tools, common issues, and detailed error references.

## Quick Links

<div class="grid cards" markdown>

-   :material-frequently-asked-questions: **FAQ**

    ---

    Answers to commonly asked questions about Cub installation, usage, and configuration.

    [:octicons-arrow-right-24: Read the FAQ](faq.md)

-   :material-alert-circle-outline: **Common Issues**

    ---

    Solutions to frequent problems with installation, harnesses, tasks, and git.

    [:octicons-arrow-right-24: Common Issues](common.md)

-   :material-format-list-numbered: **Error Reference**

    ---

    Complete list of error messages with causes and solutions.

    [:octicons-arrow-right-24: Error Reference](errors.md)

</div>

---

## Diagnostic Tools

Cub includes several built-in tools to help diagnose issues.

### The Doctor Command

The `cub doctor` command runs comprehensive diagnostics on your system:

```bash
cub doctor
```

It checks:

| Category | What It Checks |
|----------|----------------|
| **System** | Bash version, required tools (jq, git) |
| **Harnesses** | Availability of claude, codex, gemini, opencode |
| **Configuration** | JSON validity, deprecated options |
| **Project Structure** | prd.json or .beads/, agent.md, prompt.md |
| **Symlinks** | Correct targets in legacy layout |
| **Git State** | Uncommitted changes, branches, merges |
| **Tasks** | State validation, stuck tasks, recommendations |

Example output:

```
[OK] System checks passed
[OK] Configuration valid
[OK] Harness: claude available
[XX] Harness: codex not found
[OK] Task backend: beads
[OK] Git state: clean
```

### Debug Logging

Enable verbose output to see exactly what Cub is doing:

```bash
cub run --debug
```

Debug output includes:

- Configuration loading steps
- Harness invocation details
- Task selection logic
- API calls and responses
- File operations

### Log Files

Structured logs are saved in `.cub/logs/`:

```bash
# List log files
ls -la .cub/logs/

# Watch live logs
tail -f .cub/logs/session-*.jsonl

# Parse with jq
jq . .cub/logs/session-*.jsonl | head -100
```

Each log entry contains:

```json
{
  "timestamp": "2026-01-17T14:30:22Z",
  "event_type": "task_end",
  "task_id": "cub-042",
  "task_title": "Add user authentication",
  "duration_sec": 145,
  "exit_code": 0
}
```

### Task Artifacts

Examine output from completed tasks:

```bash
# List all artifacts
cub artifacts

# View specific task artifacts
cub artifacts cub-042

# Browse artifact directory
ls -la .cub/artifacts/
```

---

## Getting Help

If the troubleshooting guides don't solve your issue:

### 1. Run Diagnostics

Collect diagnostic information:

```bash
# Run doctor and save output
cub doctor > doctor-output.txt

# Capture recent logs
cp .cub/logs/session-*.jsonl logs-for-support/
```

### 2. Enable Debug Mode

Reproduce the issue with debug output:

```bash
cub run --debug --once 2>&1 | tee debug-output.txt
```

### 3. Check Known Issues

Search existing issues on GitHub:

- [Open Issues](https://github.com/lavallee/cub/issues)
- [Closed Issues](https://github.com/lavallee/cub/issues?q=is%3Aissue+is%3Aclosed)

### 4. Report a Bug

If you've found a new issue, [open a bug report](https://github.com/lavallee/cub/issues/new) with:

- Output from `cub doctor`
- Debug logs from reproduction
- Steps to reproduce the issue
- Expected vs actual behavior
- Your environment (OS, Python version, harness version)

---

## Quick Fixes

Before diving into detailed troubleshooting, try these quick fixes:

??? tip "Harness not found"
    ```bash
    # Check which harnesses are installed
    which claude codex gemini opencode

    # Install Claude Code (recommended)
    npm install -g @anthropic-ai/claude-code
    ```

??? tip "Task file errors"
    ```bash
    # Validate JSON syntax
    jq . prd.json

    # Or if using beads
    bd list
    ```

??? tip "Permission denied"
    ```bash
    # Make scripts executable
    chmod +x cub cub-init
    ```

??? tip "Git state issues"
    ```bash
    # Check current state
    git status

    # Commit or stash changes
    git add . && git commit -m "WIP"
    # Or: git stash
    ```

??? tip "Configuration problems"
    ```bash
    # Validate project config
    jq . .cub.json

    # Validate global config
    jq . ~/.config/cub/config.json
    ```

---

## Next Steps

- **[Common Issues](common.md)** - Detailed solutions to frequent problems
- **[Error Reference](errors.md)** - Complete error message lookup
- **[FAQ](faq.md)** - Answers to common questions

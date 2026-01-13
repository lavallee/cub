# Contributing to Curb

This guide explains how to extend curb with new AI harnesses, task backends, and other features.

## Architecture Overview

Curb uses a modular architecture with abstraction layers:

```
┌──────────────────────────────────────────────────────────┐
│                         curb                              │
│                   (main loop logic)                       │
├────────────────────┬─────────────────────────────────────┤
│   lib/harness.sh   │   lib/tasks.sh                      │
│  (AI CLI wrapper)  │  (task backend)                     │
├────────────────────┼─────────────────────────────────────┤
│ claude │   codex   │  lib/beads.sh  │  json (inline)     │
└────────────────────┴─────────────────────────────────────┘

Infrastructure libraries:
├── lib/xdg.sh      - XDG Base Directory paths
├── lib/config.sh   - Configuration loading (global + project)
└── lib/logger.sh   - Structured JSONL logging
```

## Adding a New AI Harness

To add support for a new AI coding CLI (e.g., Cursor, Aider, Continue):

### 1. Edit `lib/harness.sh`

Add detection logic:

```bash
harness_detect() {
    # ... existing code ...

    # Add your harness to auto-detect (after codex)
    elif command -v myharness >/dev/null 2>&1; then
        _HARNESS="myharness"
    fi
}
```

### 2. Add Invocation Functions

```bash
# ============================================================================
# MyHarness Backend
# ============================================================================

myharness_invoke() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # Combine prompts as needed for your harness
    local combined_prompt="${system_prompt}

---

${task_prompt}"

    local flags="--your-auto-mode-flag"
    [[ -n "${MYHARNESS_FLAGS:-}" ]] && flags="$flags $MYHARNESS_FLAGS"

    echo "$combined_prompt" | myharness run $flags
}

myharness_invoke_streaming() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # If your harness supports JSON streaming, parse it
    # Otherwise, fall back to regular invocation
    myharness_invoke "$system_prompt" "$task_prompt" "$debug"
}
```

### 3. Wire Up the Unified Interface

Add cases to `harness_invoke` and `harness_invoke_streaming`:

```bash
harness_invoke() {
    # ... existing code ...

    case "$harness" in
        # ... existing cases ...
        myharness)
            myharness_invoke "$system_prompt" "$task_prompt" "$debug"
            ;;
    esac
}
```

### 4. Add Version Check

```bash
harness_version() {
    case "$harness" in
        # ... existing cases ...
        myharness)
            myharness --version 2>&1 || echo "unknown"
            ;;
    esac
}
```

### 5. Document Environment Variables

Add to README.md and `--help` output:
- `MYHARNESS_FLAGS` - Extra flags for your harness

## Adding a New Task Backend

To add a new task management system (e.g., Linear, Jira, custom API):

### 1. Create Backend Wrapper (Optional)

If your backend needs complex logic, create `lib/mybackend.sh`:

```bash
#!/usr/bin/env bash
# lib/mybackend.sh - MyBackend task management wrapper

mybackend_available() {
    command -v mybackend-cli >/dev/null 2>&1
}

mybackend_initialized() {
    local project_dir="${1:-.}"
    [[ -f "${project_dir}/.mybackend/config" ]]
}

mybackend_get_ready_tasks() {
    mybackend-cli list --status=open --unblocked --json
}

mybackend_get_task() {
    local task_id="$1"
    mybackend-cli show "$task_id" --json
}

mybackend_update_task_status() {
    local task_id="$1"
    local new_status="$2"
    mybackend-cli update "$task_id" --status="$new_status"
}

# ... other required functions
```

### 2. Edit `lib/tasks.sh`

Source your wrapper:

```bash
if [[ -f "${CUB_LIB_DIR}/mybackend.sh" ]]; then
    source "${CUB_LIB_DIR}/mybackend.sh"
fi
```

Add detection:

```bash
detect_backend() {
    # ... existing code ...

    # Add to auto-detect
    if mybackend_available && mybackend_initialized "$project_dir"; then
        _TASK_BACKEND="mybackend"
    fi
}
```

### 3. Implement Required Functions

Each backend must implement these functions:

| Function | Purpose |
|----------|---------|
| `get_ready_tasks(prd, epic, label)` | Return JSON array of unblocked, open tasks (with optional filters) |
| `get_in_progress_task(prd, epic, label)` | Get in-progress task (with optional filters) |
| `get_task(id)` | Get single task by ID |
| `is_task_ready(prd, id)` | Check if task is unblocked |
| `update_task_status(prd, id, status)` | Change task status |
| `add_task_note(prd, id, note)` | Append note to task |
| `create_task(prd, json)` | Create new task |
| `get_task_counts(prd)` | Return counts by status |
| `get_remaining_count(prd)` | Count of non-closed tasks |
| `all_tasks_complete(prd)` | Check if all tasks closed |
| `get_blocked_tasks(prd)` | Return blocked tasks |

Task JSON should include a `labels` array for filtering and model selection.

### 4. Wire Up Unified Interface

Add cases to each function in `lib/tasks.sh`:

```bash
get_ready_tasks() {
    local prd="$1"
    local epic="${2:-}"
    local label="${3:-}"

    case "$(get_backend)" in
        # ... existing cases ...
        mybackend)
            mybackend_get_ready_tasks "$epic" "$label"
            ;;
    esac
}
```

### 5. Support Model Labels

Tasks with `model:X` labels (e.g., `model:haiku`, `model:sonnet`) trigger automatic model selection. The main loop extracts this label and sets `CUB_MODEL` before invoking the harness. Your backend should include labels in the task JSON output:

```json
{
  "id": "task-123",
  "title": "Quick fix",
  "labels": ["phase-1", "model:haiku"]
}
```

## Project File Templates

Templates in `templates/` are copied to projects during `curb-init`:

### PROMPT.md

The system prompt sent with every iteration. Should include:
- Context file references (@AGENT.md, @specs/*, etc.)
- Workflow instructions
- Critical rules
- Completion signal format

### AGENT.md

Project-specific instructions. Updated by the agent as it learns.

## Testing Changes

### Run Test Suite

```bash
# Run all tests (requires bats)
bats tests/

# Run specific test file
bats tests/config.bats
bats tests/logger.bats
bats tests/xdg.bats
```

### Test Harness Invocation

```bash
cub --test
```

### Debug Mode

```bash
cub --debug --once
```

Shows full prompts, timing, and saves prompts to temp files.

### Dump Prompts

```bash
cub --dump-prompt
```

Saves system and task prompts to files for manual testing.

### Test with Filters

```bash
# Test epic filtering
cub --epic my-epic-id --ready

# Test label filtering
cub --label phase-1 --status

# Test combined filters
cub --epic curb-1gq --label phase-1 --once --debug
```

## Code Style

- Use `log_info`, `log_success`, `log_warn`, `log_error`, `log_debug` for output
- Keep functions focused and documented
- Follow existing patterns in the codebase
- Test with both harnesses and backends

## Pull Request Guidelines

1. Describe what your change does and why
2. Test with multiple harnesses if applicable
3. Update README.md and `--help` output
4. Add environment variable documentation

## Questions?

Open an issue on GitHub for discussion.

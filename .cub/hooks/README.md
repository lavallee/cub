# Cub Hook Scripts

This directory contains hook scripts for auto-capturing artifacts when running harnesses directly (Claude Code, Codex, OpenCode) instead of via `cub run`.

## Overview

When you run Claude Code or other harnesses directly, these hooks automatically:
- Track file writes to `plans/` directory
- Log session start/end events
- Capture artifacts to `.cub/ledger/forensics/`
- Maintain records roughly equivalent to `cub run`

## Installation

### For Claude Code

Copy or symlink these hooks to your Claude Code hooks directory:

```bash
# Global installation (all projects)
mkdir -p ~/.claude/hooks
cp .cub/hooks/*.sh ~/.claude/hooks/

# Or symlink for automatic updates
ln -sf "$(pwd)/.cub/hooks"/*.sh ~/.claude/hooks/

# Project-specific installation
mkdir -p .claude/hooks
cp .cub/hooks/*.sh .claude/hooks/
```

Then configure hooks in `.claude/settings.json` or `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.cub/hooks/post-tool-use.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.cub/hooks/stop.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.cub/hooks/session-start.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/.cub/hooks/session-end.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### For Other Harnesses

Hooks can be adapted for other harnesses that support similar hook mechanisms.
Check the harness documentation for hook installation instructions.

## Available Hooks

### post-tool-use.sh

Captures file writes, especially to `plans/` directory.

**Triggers:** After Write, Edit, or NotebookEdit tool execution
**Captures:** File paths, timestamps
**Logs to:** `.cub/ledger/forensics/{session_id}.jsonl`

### stop.sh

Finalizes session and captures artifacts when Claude finishes responding.

**Triggers:** When Claude completes a response
**Captures:** Session end timestamp, transcript path
**Logs to:** `.cub/ledger/forensics/{session_id}.jsonl`

### session-start.sh

Initializes session tracking when Claude Code starts or resumes.

**Triggers:** Session startup, resume, or clear
**Captures:** Session start timestamp
**Logs to:** `.cub/ledger/forensics/{session_id}.jsonl`

**Note:** Only available in Claude Code TypeScript SDK, not Python SDK.

### session-end.sh

Finalizes session when Claude Code terminates.

**Triggers:** Session logout, clear, or exit
**Captures:** Session end timestamp, reason
**Logs to:** `.cub/ledger/forensics/{session_id}.jsonl`

**Note:** Only available in Claude Code TypeScript SDK, not Python SDK.

## Forensic Logs

Hooks write to `.cub/ledger/forensics/{session_id}.jsonl` in JSONL format:

```json
{"event": "session_start", "timestamp": "2026-01-26T20:30:00Z"}
{"event": "plan_write", "file_path": "plans/plan.md", "timestamp": "2026-01-26T20:35:00Z"}
{"event": "session_finalize", "transcript_path": "/path/to/transcript", "timestamp": "2026-01-26T20:45:00Z"}
```

These logs can be processed later to reconstruct work done in direct sessions.

## Behavior

- **Non-blocking:** Hooks never block Claude Code execution
- **Defensive:** Malformed inputs are skipped, not crashed
- **Conditional:** Only run if cub is installed and `.cub/config.yml` exists
- **Silent:** Failures are logged but don't interrupt workflow

## Testing

Test hooks locally:

```bash
# Test PostToolUse hook
echo '{
  "hook_event_name": "PostToolUse",
  "session_id": "test-123",
  "tool_name": "Write",
  "tool_input": {"file_path": "plans/plan.md"},
  "cwd": "'$(pwd)'"
}' | .cub/hooks/post-tool-use.sh

# Check forensic log
cat .cub/ledger/forensics/test-123.jsonl
```

## Troubleshooting

### Hooks not running

1. Check that scripts are executable: `chmod +x .cub/hooks/*.sh`
2. Verify `.claude/settings.json` or `.claude/settings.local.json` has hooks configured
3. Check Claude Code verbose output (Ctrl+O) for hook execution logs

### No forensic logs created

1. Ensure `.cub/config.yml` exists (run `cub init` if needed)
2. Check that cub is in PATH: `which cub`
3. Verify Python module can be imported: `python3 -m cub.core.harness.hooks --help`

### Hook timeouts

If hooks timeout, increase the timeout in settings.json:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "...",
            "timeout": 30  // Increased from 10
          }
        ]
      }
    ]
  }
}
```

## Further Reading

- [Claude Code Hooks Documentation](.cub/docs/claude-code-hooks.md)
- [Ledger System](../../src/cub/core/ledger/)
- [Hook Handlers](../../src/cub/core/harness/hooks.py)

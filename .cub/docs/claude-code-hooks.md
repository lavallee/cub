# Claude Code Hooks Research

**Task:** cub-r6s.4
**Date:** 2026-01-26
**Purpose:** Document Claude Code's hook system to inform artifact capture strategy for direct sessions

## Executive Summary

Claude Code exposes a comprehensive hooks system for intercepting agent behavior at key execution points. Hooks can be configured in settings files (JSON), plugins, or directly in skills/agents using frontmatter. This system enables artifact capture, validation, logging, and custom automation.

**Key Findings:**
- ✅ Can detect session start/end via `SessionStart` and `SessionEnd` hooks
- ✅ Can capture tool usage via `PreToolUse` and `PostToolUse` hooks
- ⚠️ Cannot directly capture plan content (no dedicated hook event)
- ✅ Can capture transcript via `transcript_path` field in all hook inputs
- ✅ Hooks receive JSON via stdin and respond via JSON to stdout

## Available Hook Events

Claude Code provides 12 lifecycle hook events covering the full agent execution cycle:

| Hook Event | When It Fires | Available In |
|------------|---------------|--------------|
| `SessionStart` | Session begins or resumes | CLI + SDK (TypeScript only) |
| `UserPromptSubmit` | User submits a prompt | CLI + SDK |
| `PreToolUse` | Before tool execution | CLI + SDK |
| `PermissionRequest` | When permission dialog appears | CLI + SDK (TypeScript only) |
| `PostToolUse` | After tool succeeds | CLI + SDK |
| `PostToolUseFailure` | After tool fails | CLI + SDK (TypeScript only) |
| `SubagentStart` | When spawning a subagent | CLI + SDK (TypeScript only) |
| `SubagentStop` | When subagent finishes | CLI + SDK |
| `Stop` | Claude finishes responding | CLI + SDK |
| `PreCompact` | Before context compaction | CLI + SDK |
| `SessionEnd` | Session terminates | CLI + SDK (TypeScript only) |
| `Notification` | Claude Code sends notifications | CLI + SDK (TypeScript only) |
| `Setup` | Init/maintenance flags | CLI only |

### CLI vs. SDK Availability

**CLI-only hooks:**
- `Setup` - Runs with `--init`, `--init-only`, or `--maintenance` flags

**SDK-only hooks (TypeScript):**
- `SessionStart`, `SessionEnd` - Not in Python SDK due to setup limitations
- `PermissionRequest`, `PostToolUseFailure`, `SubagentStart`, `Notification` - Not in Python SDK

**Available in both:**
- `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `SubagentStop`, `Stop`, `PreCompact`

## Hook Configuration Methods

### 1. Settings Files (JSON)

Hooks are configured in settings files with three levels of precedence:

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",
        "hooks": [
          {
            "type": "command",
            "command": "your-command-here",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

**Settings file locations:**
- `~/.claude/settings.json` - User settings
- `.claude/settings.json` - Project settings
- `.claude/settings.local.json` - Local project settings (not committed)
- Managed policy settings (enterprise)

**Configuration fields:**
- `matcher`: Regex pattern for tool names (case-sensitive)
  - Simple strings: `Write` matches only Write tool
  - Regex: `Edit|Write` or `Notebook.*`
  - `*` or empty string matches all tools
  - Only applies to tool-based hooks (PreToolUse, PostToolUse, PermissionRequest)
- `type`: `"command"` (bash) or `"prompt"` (LLM-based evaluation)
- `command`: Bash command to execute (for type: "command")
- `prompt`: Prompt for LLM (for type: "prompt")
- `timeout`: Execution timeout in seconds (default: 60)

### 2. Plugin Hooks

Plugins provide hooks in `hooks/hooks.json` that merge with user/project hooks:

```json
{
  "description": "Automatic code formatting",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Plugin environment variables:**
- `${CLAUDE_PLUGIN_ROOT}`: Absolute path to plugin directory
- `${CLAUDE_PROJECT_DIR}`: Project root directory

### 3. Component-Scoped Hooks (Skills/Agents)

Hooks can be defined in skill/agent frontmatter with scoped lifecycle:

```yaml
---
name: secure-operations
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/security-check.sh"
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/run-linter.sh"
---
```

**Supported events:** `PreToolUse`, `PostToolUse`, `Stop`
**Additional option for skills:** `once: true` - Run hook only once per session

## Hook Input/Output Protocol

### Input Structure (via stdin)

All hooks receive JSON via stdin with common and event-specific fields:

```json
{
  // Common fields (all hooks)
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../session.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",

  // Event-specific fields
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm test",
    "description": "Run tests",
    "timeout": 120000
  },
  "tool_use_id": "toolu_01ABC123..."
}
```

#### Common Input Fields

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Current session identifier |
| `transcript_path` | string | Path to conversation JSON |
| `cwd` | string | Current working directory |
| `permission_mode` | string | `"default"`, `"plan"`, `"acceptEdits"`, `"dontAsk"`, or `"bypassPermissions"` |
| `hook_event_name` | string | Hook type (PreToolUse, PostToolUse, etc.) |

#### Event-Specific Input Fields

**PreToolUse, PostToolUse, PermissionRequest:**
- `tool_name`: Name of the tool
- `tool_input`: Tool arguments (schema varies by tool)
- `tool_use_id`: Unique identifier

**PostToolUse additional:**
- `tool_response`: Result from tool execution

**Stop, SubagentStop:**
- `stop_hook_active`: `true` if already continuing from stop hook (prevents infinite loops)

**SubagentStop:**
- `agent_id`: Subagent identifier
- `agent_transcript_path`: Path to subagent's transcript (in `subagents/` folder)

**SessionStart:**
- `source`: `"startup"`, `"resume"`, `"clear"`, or `"compact"`
- `model`: Model identifier (e.g., `"claude-sonnet-4-20250514"`)
- `agent_type`: Agent name (if started with `claude --agent <name>`)

**SessionEnd:**
- `reason`: `"clear"`, `"logout"`, `"prompt_input_exit"`, or `"other"`

**UserPromptSubmit:**
- `prompt`: The user's prompt text

**PreCompact:**
- `trigger`: `"manual"` or `"auto"`
- `custom_instructions`: Custom instructions from `/compact`

**Setup:**
- `trigger`: `"init"` or `"maintenance"`

### Output Structure (via stdout)

Hooks communicate via exit codes and optional JSON stdout:

#### Simple: Exit Code Method

- **Exit 0**: Success
  - `stdout` shown to user in verbose mode (Ctrl+O)
  - For `UserPromptSubmit` and `SessionStart`: stdout added to context
  - JSON in stdout parsed for structured control
- **Exit 2**: Blocking error
  - `stderr` used as error message and fed to Claude
  - Format: `[command]: {stderr}`
  - JSON in stdout **not processed**
- **Other exit codes**: Non-blocking error
  - `stderr` shown in verbose mode
  - Execution continues

#### Advanced: JSON Output (exit code 0 only)

```json
{
  // Common fields
  "continue": true,
  "stopReason": "string",
  "suppressOutput": true,
  "systemMessage": "string",

  // Hook-specific output
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Auto-approved",
    "updatedInput": {
      "command": "modified-command"
    },
    "additionalContext": "Extra context for Claude"
  }
}
```

**Common JSON fields:**
| Field | Type | Description |
|-------|------|-------------|
| `continue` | boolean | Whether Claude should continue (default: true) |
| `stopReason` | string | Message when continue=false (shown to user, not Claude) |
| `suppressOutput` | boolean | Hide stdout from transcript (default: false) |
| `systemMessage` | string | Message shown to user |

**hookSpecificOutput fields:**

| Field | Type | Hooks | Description |
|-------|------|-------|-------------|
| `hookEventName` | string | All | Required. Must match input `hook_event_name` |
| `permissionDecision` | `"allow"` \| `"deny"` \| `"ask"` | PreToolUse | Control tool execution |
| `permissionDecisionReason` | string | PreToolUse | Explanation for decision |
| `updatedInput` | object | PreToolUse | Modified tool input |
| `additionalContext` | string | PreToolUse, PostToolUse, UserPromptSubmit, SessionStart, Setup | Context added to conversation |
| `decision` | `"block"` \| undefined | PostToolUse, Stop, SubagentStop, UserPromptSubmit | Block operation |
| `reason` | string | PostToolUse, Stop, SubagentStop, UserPromptSubmit | Explanation (required for block) |

#### PermissionRequest Decision (TypeScript SDK)

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow",
      "updatedInput": {
        "command": "npm run lint"
      }
    }
  }
}
```

For `"deny"` behavior, can include `"message"` and `"interrupt"` (boolean).

## Prompt-Based Hooks

In addition to bash commands, Claude Code supports LLM-based hooks for intelligent decisions:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Evaluate if Claude should stop: $ARGUMENTS. Check if all tasks complete.",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**How it works:**
1. Hook input + prompt sent to Haiku
2. LLM responds with JSON: `{"ok": true|false, "reason": "..."}`
3. `ok: true` allows, `ok: false` prevents action

**Use `$ARGUMENTS` placeholder** for hook input JSON (auto-appended if omitted).

**Supported for all hooks**, most useful for:
- `Stop`: Intelligent continuation decisions
- `SubagentStop`: Evaluate task completion
- `UserPromptSubmit`: Validate prompts
- `PreToolUse`: Context-aware permissions

## Environment Variables

**Available in all hooks:**
- `CLAUDE_PROJECT_DIR`: Absolute path to project root
- `CLAUDE_CODE_REMOTE`: `"true"` if remote/web, empty if local CLI

**SessionStart and Setup hooks only:**
- `CLAUDE_ENV_FILE`: Path to persist environment variables

Example persisting env vars:
```bash
#!/bin/bash
if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo 'export NODE_ENV=production' >> "$CLAUDE_ENV_FILE"
  echo 'export API_KEY=secret' >> "$CLAUDE_ENV_FILE"
fi
exit 0
```

## Matchers and Tool Names

**Common built-in tools:**
- `Task` - Subagent tasks
- `Bash` - Shell commands
- `Glob`, `Grep` - File operations
- `Read`, `Write`, `Edit` - File I/O
- `WebFetch`, `WebSearch` - Web operations

**MCP tools:** Pattern `mcp__<server>__<action>`
- Example: `mcp__memory__create_entities`, `mcp__github__search_repositories`
- Matcher: `mcp__memory__.*` or `mcp__.*__write.*`

**Matcher rules:**
- Only apply to tool-based hooks (PreToolUse, PostToolUse, PostToolUseFailure, PermissionRequest)
- Lifecycle hooks (Stop, SessionStart, SessionEnd, Notification, etc.) **ignore matchers**
- Case-sensitive regex matching
- `*` or empty string matches all tools

## Key Capabilities for Artifact Capture

### ✅ Can Detect Session Start/End

**SessionStart hook** provides:
- Session ID
- Transcript path
- Session source (startup, resume, clear, compact)
- Model identifier
- Agent type (if custom agent)

**SessionEnd hook** provides:
- Termination reason
- Final transcript path

**Use case:** Initialize ledger capture on session start, finalize on session end.

### ✅ Can Capture Tool Usage

**PreToolUse hook** captures:
- Tool name
- Tool input parameters
- Tool use ID (for correlation)

**PostToolUse hook** captures:
- Tool name
- Tool input
- Tool response
- Success/failure status

**Use case:** Log all tool calls to `.cub/ledger` for forensic reconstruction.

### ✅ Can Access Transcript

All hooks receive `transcript_path` field pointing to JSONL conversation file.

**Format:** Each line is a JSON message with:
- `type`: `"input"` (user) or `"output"` (Claude)
- `content`: Message content (blocks)
- `timestamp`: ISO 8601

**Use case:** Parse transcript to extract task context, decisions, and artifacts.

### ⚠️ Cannot Directly Capture Plan Content

**No dedicated hook for plan mode.** However:
- Can detect plan mode via `permission_mode: "plan"` in hook input
- Can capture plan-related tool calls (Read, Write during planning)
- Can extract plan from transcript by filtering for plan-mode messages

**Workaround:** Parse transcript for plan artifacts or intercept Write tool calls during plan mode.

### ✅ Can Inject Context

**SessionStart and UserPromptSubmit hooks** can add context to conversation:
- SessionStart: Load project state, TODOs, recent changes
- UserPromptSubmit: Inject current time, environment info

**Use case:** Inject `.cub/ledger` summary into session context for continuity.

## Security Considerations

**⚠️ Hooks execute arbitrary commands** on the system. Key safeguards:

1. **Delayed activation:** Direct edits to hooks in settings files don't take effect immediately
2. **Review required:** Changes require review in `/hooks` menu
3. **Snapshot at startup:** Claude Code captures hook snapshot at startup, uses throughout session
4. **Timeout protection:** 60-second default timeout (configurable)

**Best practices:**
- Validate and sanitize inputs
- Quote shell variables: `"$VAR"` not `$VAR`
- Block path traversal: Check for `..`
- Use absolute paths
- Skip sensitive files (`.env`, `.git/`)

## Hook Execution Details

- **Parallelization:** All matching hooks run in parallel
- **Deduplication:** Identical commands auto-deduplicated
- **Timeout:** 60s default, configurable per hook
- **Output routing:**
  - PreToolUse/PermissionRequest/PostToolUse/Stop/SubagentStop: Progress in verbose mode (Ctrl+O)
  - Notification/SessionEnd: Debug logs only (`--debug`)
  - UserPromptSubmit/SessionStart/Setup: stdout added to context

## Agent SDK Hooks (Python/TypeScript)

The Claude Agent SDK provides programmatic hooks for harness execution:

### Python SDK Hook Events

```python
class HookEvent(str, Enum):
    PRE_TASK = "pre_task"
    POST_TASK = "post_task"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    ON_ERROR = "on_error"
    ON_MESSAGE = "on_message"
```

### TypeScript SDK Hook Events

Includes Python events plus:
- `SessionStart`, `SessionEnd`
- `PermissionRequest`
- `PostToolUseFailure`
- `SubagentStart`, `SubagentStop`
- `Notification`

### Hook Handler Type

```python
HookHandler = Callable[[HookContext], Awaitable[HookResult | None]]

@dataclass
class HookContext:
    event: HookEvent
    task_id: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: str | None = None
    message_content: str | None = None
    message_role: str | None = None
    error: Exception | None = None
    metadata: dict[str, Any] = ...

@dataclass
class HookResult:
    block: bool = False
    reason: str | None = None
    modified_input: dict[str, Any] | None = None
```

### Example: Protect .env Files

```python
async def protect_env_files(input_data, tool_use_id, context):
    file_path = input_data['tool_input'].get('file_path', '')
    if file_path.endswith('.env'):
        return {
            'hookSpecificOutput': {
                'hookEventName': input_data['hook_event_name'],
                'permissionDecision': 'deny',
                'permissionDecisionReason': 'Cannot modify .env files'
            }
        }
    return {}

options = ClaudeAgentOptions(
    hooks={
        'PreToolUse': [HookMatcher(matcher='Write|Edit', hooks=[protect_env_files])]
    }
)
```

## Recommendations for Cub Integration

### Strategy: Hybrid Approach

**For `cub run` (controlled environment):**
- Use existing cub workflow hooks (already implemented)
- Continue current ledger capture via harness integration

**For direct sessions (Claude Code/Codex/OpenCode):**
- Implement hook handlers in `.claude/settings.json` (project-level)
- Generated by `cub init` to capture artifacts equivalent to `cub run`

### Proposed Hook Handlers

**1. SessionStart Hook** - Initialize ledger
```bash
#!/bin/bash
# .claude/hooks/session-start.sh
cub hooks session-start --session-id "$session_id" --transcript "$transcript_path"
```

**2. PostToolUse Hook** - Log tool calls
```bash
#!/bin/bash
# .claude/hooks/post-tool-use.sh
cub hooks tool-capture --session-id "$session_id" < /dev/stdin
```

**3. SessionEnd Hook** - Finalize artifacts
```bash
#!/bin/bash
# .claude/hooks/session-end.sh
cub hooks session-end --session-id "$session_id" --reason "$reason"
```

**4. Stop Hook** - Capture task completions
```bash
#!/bin/bash
# .claude/hooks/stop.sh
cub hooks stop --session-id "$session_id" --transcript "$transcript_path"
```

### Hook Configuration Template

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-start.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-tool-use.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/stop.sh",
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
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-end.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### Implementation Steps

1. **`cub init` enhancement:**
   - Generate `.claude/settings.json` with hook configuration
   - Create `.claude/hooks/` directory with handler scripts
   - Mark scripts executable

2. **Hook handler commands:**
   - Add `cub hooks session-start` - Initialize ledger entry
   - Add `cub hooks tool-capture` - Log tool call from stdin
   - Add `cub hooks stop` - Mark iteration complete
   - Add `cub hooks session-end` - Finalize artifacts

3. **Ledger format alignment:**
   - Ensure direct session ledger entries match `cub run` format
   - Include: session_id, timestamp, tool_name, tool_input, tool_response

4. **AGENTS.md instructions:**
   - Document that hooks auto-capture artifacts
   - Instruct agents to run `cub commit` for task completions
   - Explain ledger viewing with `cub status`

## Constraints and Limitations

### CLI-Only Hooks

Some hooks are only available in Claude Code CLI, not in the Agent SDK:
- `Setup` - Requires CLI flags (`--init`, `--maintenance`)

### SDK-Only Hooks (TypeScript)

Not available in Python SDK:
- `SessionStart`, `SessionEnd`
- `PermissionRequest`
- `PostToolUseFailure`
- `SubagentStart`
- `Notification`

### No Direct Plan Capture

- No hook specifically fires for plan mode entry/exit
- Must infer from `permission_mode: "plan"` or transcript parsing

### Hook Execution Environment

- Hooks run in current directory (not necessarily project root)
- Use `$CLAUDE_PROJECT_DIR` for project-relative paths
- 60-second default timeout (may need increase for slow operations)

### Remote vs. Local

- `CLAUDE_CODE_REMOTE` indicates web vs. CLI environment
- May need different logic for remote sessions (no local file access)

## References

**Official Documentation:**
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Agent SDK Hooks](https://platform.claude.com/docs/en/agent-sdk/hooks)
- [Claude Code Hooks Guide](https://claude.com/blog/how-to-configure-hooks)

**Additional Resources:**
- [Hooks in Cursor and Claude Code Guide](https://mlearning.substack.com/p/hooks-in-cursor-and-claude-code-a-step-by-step-guide)
- [Claude Code Hook Control Flow](https://stevekinney.com/courses/ai-development/claude-code-hook-control-flow)
- [GitHub: claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery)

---

**Next Steps:** Implement hook handlers in task cub-r6s.5

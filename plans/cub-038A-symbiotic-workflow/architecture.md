# Architecture Design: Symbiotic Workflow

**Date:** 2026-01-28
**Mindset:** Production
**Scale:** Personal
**Status:** Approved

---

## Technical Summary

The system adds an observation layer between Claude Code (or any harness) and cub's existing task/ledger infrastructure. When someone works directly in a harness, lightweight hooks observe what's happening -- file writes, task commands, git commits -- and feed events into the same ledger and task systems that `cub run` uses. The key architectural move is decoupling `LedgerIntegration` from the run loop so it can be driven by either the run loop or hook events, using the same code paths.

The hook layer is a three-tier pipeline: shell fast-path filter, Python event handler, and ledger/task integration. The shell layer keeps latency low for the 90% of tool uses that aren't relevant. The Python layer handles event classification and forensics. The integration layer writes to the same ledger and task backend that `cub run` uses.

The JSON task backend becomes the primary backend, with branch binding added and beads running alongside in "both" mode during migration. `cub init` gains the ability to install Claude Code hook configuration, making the symbiotic workflow opt-in but frictionless.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing codebase |
| Hook fast-path | POSIX shell (bash) | Minimizes latency; no Python startup for irrelevant events |
| Data models | Pydantic v2 | Existing pattern for all models |
| Task storage | JSON (`.cub/tasks.json`) | Drop-in for beads, version-controlled, portable |
| Forensics | JSONL (`.cub/ledger/forensics/`) | Append-only, one file per session |
| Ledger | JSON + JSONL index | Existing layout, no changes |
| CLI | Typer | Existing framework |
| Testing | pytest + pytest-mock | Existing framework |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER'S WORKFLOW                              │
│                                                                 │
│   ┌─────────────┐              ┌──────────────────┐            │
│   │  cub run    │              │  Claude Code     │            │
│   │  (automated)│              │  (interactive)   │            │
│   └──────┬──────┘              └────────┬─────────┘            │
│          │                              │                       │
│          │                     ┌────────▼─────────┐            │
│          │                     │  Hook Pipeline   │            │
│          │                     │  ┌─────────────┐ │            │
│          │                     │  │ Shell Filter │ │            │
│          │                     │  │ (fast path)  │ │            │
│          │                     │  └──────┬──────┘ │            │
│          │                     │  ┌──────▼──────┐ │            │
│          │                     │  │ Python Hndlr│ │            │
│          │                     │  │ (classify)  │ │            │
│          │                     │  └──────┬──────┘ │            │
│          │                     └─────────┼────────┘            │
│          │                               │                      │
│   ┌──────▼───────────────────────────────▼──────┐              │
│   │          SessionLedgerIntegration           │              │
│   │     (decoupled, works from either path)     │              │
│   └──────┬──────────────────────────────┬───────┘              │
│          │                              │                       │
│   ┌──────▼──────┐              ┌────────▼───────┐              │
│   │ Task Backend│              │ Ledger Writer  │              │
│   │ (JSON)      │              │ (by-task, etc) │              │
│   └─────────────┘              └────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Hook Shell Filter (`.cub/scripts/hooks/cub-hook.sh`)
- **Purpose:** Fast-path gate preventing Python startup for irrelevant events
- **Responsibilities:**
  - Read JSON from stdin, extract `tool_name` and `hook_event_name`
  - Check `CUB_RUN_ACTIVE` env var -- if set, exit 0 (double-tracking prevention)
  - For PostToolUse: filter by tool name and file path relevance
  - For Bash: filter by command pattern (cub, git commit, git add)
  - Pipe stdin to Python handler only when relevant
- **Dependencies:** None (pure shell; optional `jq` for faster parsing)
- **Interface:** Called by Claude Code via `.claude/settings.json`

### 2. Hook Python Handlers (`cub.core.harness.hooks`)
- **Purpose:** Classify events, maintain session state, write forensics, trigger ledger integration
- **Responsibilities:**
  - SessionStart: create session record, return project context as `additionalContext`
  - PostToolUse: classify file writes, detect task/git commands, append forensics
  - Stop: synthesize session summary, create/update ledger entry
  - PreCompact: checkpoint session state (compaction == new session)
  - UserPromptSubmit: detect task ID patterns, inject task context
- **Dependencies:** `cub.core.tasks.backend`, `cub.core.ledger.session_integration`, `cub.core.config`
- **Interface:** `handle_hook_event(event_type, payload) -> HookEventResult`

### 3. Session Ledger Integration (`cub.core.ledger.session_integration`)
- **Purpose:** Bridge hook events to the ledger, working with partial information
- **Responsibilities:**
  - Accept events incrementally (file write, task claim, git commit)
  - On session finalize: synthesize `LedgerEntry` from accumulated events
  - Support lazy association (task ID may arrive mid-session)
  - Parse transcript for token/cost enrichment
  - Delegate to `LedgerWriter` for persistence
- **Dependencies:** `cub.core.ledger.writer`, `cub.core.ledger.models`
- **Interface:**
  ```python
  class SessionLedgerIntegration:
      def on_session_start(self, session_id: str, cwd: str) -> None
      def on_file_write(self, session_id: str, file_path: str, tool_name: str) -> None
      def on_task_claim(self, session_id: str, task_id: str) -> None
      def on_task_close(self, session_id: str, task_id: str, reason: str | None) -> None
      def on_git_commit(self, session_id: str, commit_hash: str, message: str) -> None
      def on_session_end(self, session_id: str, transcript_path: str | None) -> LedgerEntry | None
      def enrich_from_transcript(self, session_id: str, transcript_path: str) -> None
  ```

### 4. JSON Task Backend -- Branch Binding
- **Purpose:** Close the critical gap (`bind_branch()` currently returns False)
- **Responsibilities:**
  - Store branch bindings in `.cub/branches.json`
  - Support get/add/remove binding operations
  - Integrate with `cub branch` and `cub pr` commands
- **Dependencies:** None (self-contained JSON file)
- **Interface:** Same `bind_branch()` protocol method, now functional

### 5. Hook Configuration Installer (`cub.core.hooks.installer`)
- **Purpose:** Install/update Claude Code hook configuration
- **Responsibilities:**
  - Read existing `.claude/settings.json` without clobbering
  - Merge cub hook entries into `hooks` section
  - Install shell script to `.cub/scripts/hooks/cub-hook.sh`
  - Called by `cub init` and validated by `cub doctor`
- **Dependencies:** `cub.core.config`
- **Interface:**
  ```python
  def install_hooks(project_dir: Path, *, force: bool = False) -> HookInstallResult
  def validate_hooks(project_dir: Path) -> list[HookIssue]
  def uninstall_hooks(project_dir: Path) -> None
  ```

### 6. Enhanced Instructions Generation
- **Purpose:** Guide direct session workflow via AGENTS.md / CLAUDE.md
- **Responsibilities:**
  - Replace `bd` commands with `cub task` commands
  - Add task claiming guidance at session start
  - Add plan capture and session close guidance
- **Dependencies:** `cub.core.config`
- **Interface:** Same `generate_agents_md()` / `generate_claude_md()` functions, updated content

## Data Model

### Session Forensics (`.cub/ledger/forensics/{session_id}.jsonl`)
```
{"event": "session_start", "timestamp": "...", "cwd": "/path"}
{"event": "file_write", "timestamp": "...", "file_path": "plans/foo/plan.md", "tool": "Write", "category": "plan"}
{"event": "task_claim", "timestamp": "...", "task_id": "cub-042"}
{"event": "git_commit", "timestamp": "...", "hash": "abc123", "message": "implement feature"}
{"event": "task_close", "timestamp": "...", "task_id": "cub-042", "reason": "implemented"}
{"event": "session_end", "timestamp": "...", "transcript_path": "/path/to/transcript.jsonl"}
```

### Branch Bindings (`.cub/branches.json`)
```json
{
  "bindings": [
    {
      "epic_id": "cub-abc",
      "branch_name": "feature/symbiotic",
      "base_branch": "main",
      "created_at": "2026-01-28T12:00:00Z"
    }
  ]
}
```

### Claude Code Hook Configuration (`.claude/settings.json` additions)
```json
{
  "hooks": {
    "SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": ".cub/scripts/hooks/cub-hook.sh SessionStart", "timeout": 10}]}],
    "PostToolUse": [
      {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": ".cub/scripts/hooks/cub-hook.sh PostToolUse", "timeout": 5}]},
      {"matcher": "Bash", "hooks": [{"type": "command", "command": ".cub/scripts/hooks/cub-hook.sh PostToolUse", "timeout": 5}]}
    ],
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": ".cub/scripts/hooks/cub-hook.sh Stop", "timeout": 15}]}],
    "PreCompact": [{"matcher": "", "hooks": [{"type": "command", "command": ".cub/scripts/hooks/cub-hook.sh PreCompact", "timeout": 10}]}],
    "UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": ".cub/scripts/hooks/cub-hook.sh UserPromptSubmit", "timeout": 5}]}]
  }
}
```

## Implementation Phases

### Phase 1: Foundation -- Hook Pipeline and Session Forensics
**Goal:** Events from direct Claude Code sessions are observed and recorded.
- Implement `cub-hook.sh` shell filter script
- Enhance `cub.core.harness.hooks` to write forensics JSONL
- Add `CUB_RUN_ACTIVE` env var to Claude harness backends
- Create `cub.core.hooks.installer` for hook config management
- Add hook installation to `cub init` flow
- Tests for shell filter, Python handlers, installer

### Phase 2: Session Ledger Integration
**Goal:** Direct session work produces real ledger entries.
- Implement `SessionLedgerIntegration` class
- Connect hook handlers to session integration
- Stop handler synthesizes `LedgerEntry` from session events
- Transcript parsing for token/cost enrichment
- Update `cub session done` to use `SessionLedgerIntegration`
- Tests for session integration, ledger entry creation

### Phase 3: Task Backend and Instructions
**Goal:** JSON backend is full drop-in; instructions guide direct sessions.
- Add branch binding to JSON backend
- Update AGENTS.md generation (cub task commands instead of bd)
- Add `cub task` CLI subcommand (ready, claim, close, create)
- SessionStart hook injects project context as `additionalContext`
- UserPromptSubmit hook detects task IDs
- Tests for backend parity, instruction generation

### Phase 4: Reconciliation and Polish
**Goal:** Edge cases handled, manual recovery available, end-to-end validation.
- Implement `cub reconcile` command
- `cub doctor` validates hook installation
- Integration tests simulating direct sessions
- Documentation updates

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Shell JSON parsing fragile | M | M | jq with grep/sed fallback; test malformed input |
| Python startup latency on PostToolUse | M | L | Shell filter skips 90%+ of events |
| Forensics JSONL unbounded growth | L | M | Session-scoped files; reconcile archives old ones |
| `.claude/settings.json` conflicts | M | M | Defensive merge; doctor validates; explicit opt-in |
| Transcript format changes | M | L | Defensive parsing; enrichment is best-effort |
| JSON backend drift from beads | H | L | "Both" mode parallel execution; integration tests |

## Dependencies

### External
- Claude Code hooks API (stable)
- `jq` (optional, shell fast-path optimization)

### Internal
- `cub.core.ledger.writer` -- used as-is
- `cub.core.ledger.models` -- used as-is
- `cub.core.tasks.backend` -- protocol unchanged, JSON backend enhanced
- `cub.core.config` -- may add `symbiotic` config section

## Security Considerations

- Hook scripts run with user's permissions (no escalation)
- Forensics logs contain file paths and command text (same sensitivity as git history)
- Transcript parsing reads local files only
- Hook installer validates JSON before modifying `.claude/settings.json`
- No secrets or credentials in hook configuration

## Future Considerations

- Multi-harness hooks when other platforms support them
- Plan format translation (`cub translate plan`)
- Dashboard consuming forensics and session ledger data
- Real-time cost tracking if hooks gain token data
- Auto-task creation from conversation analysis

---

**Next Step:** Run `cub itemize` to generate implementation tasks.

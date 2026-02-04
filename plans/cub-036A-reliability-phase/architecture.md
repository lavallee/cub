# Architecture Design: Reliability Phase (0.30 Alpha)

**Date:** 2026-01-26
**Mindset:** Production
**Scale:** Personal
**Status:** Approved

---

## Technical Summary

The reliability phase adds three capabilities to cub's existing run loop infrastructure:

1. **E4 (Core Loop Hardening):** Strengthen existing signal/error handling to ensure artifacts are always preserved. The foundation is solid—this is primarily testing and edge case fixes.

2. **E5 (Circuit Breaker):** Add timeout monitoring to harness execution. A `CircuitBreaker` component wraps harness invocation with asyncio timeout, tripping after configurable inactivity period.

3. **E6 (Symbiotic Workflow):** Two-pronged approach: (a) CLAUDE.md/AGENTS.md instructions guide agents to call `cub` commands, (b) harness hooks capture artifacts automatically when available.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing codebase; match statements, type unions |
| CLI Framework | Typer | Existing pattern; type-safe CLI |
| Config/Models | Pydantic v2 | Existing pattern; validation and serialization |
| Async | asyncio | Existing pattern; timeout support via `asyncio.wait_for` |
| Testing | pytest + pytest-timeout | Existing pattern; timeout prevents hung tests |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           cub run                                    │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │ RunLoop      │───▶│ CircuitBreaker│───▶│ Harness      │          │
│  │ (run.py)     │    │ (NEW)        │    │ Backend      │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                   │                    │                   │
│         ▼                   ▼                    ▼                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │ StatusWriter │    │ ActivityMonitor│   │ HarnessHooks │          │
│  │ (existing)   │    │ (NEW)        │    │ (NEW)        │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                                        │                   │
│         ▼                                        ▼                   │
│  ┌──────────────────────────────────────────────────────┐          │
│  │                    .cub/ledger/                       │          │
│  │  (unified audit trail - cub run AND direct sessions)  │          │
│  └──────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      Direct Harness Session                          │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │ Claude Code  │───▶│ CLAUDE.md    │───▶│ cub commands │          │
│  │ / Codex      │    │ Instructions │    │ (NEW)        │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                                        │                   │
│         ▼                                        ▼                   │
│  ┌──────────────┐                        ┌──────────────┐          │
│  │ Harness Hooks│───────────────────────▶│ .cub/ledger/ │          │
│  │ (if avail)   │                        │              │          │
│  └──────────────┘                        └──────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### CircuitBreaker (NEW)
**Location:** `src/cub/core/circuit_breaker.py`

- **Purpose:** Wrap harness execution with timeout monitoring
- **Responsibilities:**
  - Track last activity timestamp
  - Trip breaker after `timeout_minutes` of inactivity
  - Provide clear error message when tripped
  - Support graceful cancellation
- **Dependencies:** asyncio, config
- **Interface:**
  ```python
  class CircuitBreaker:
      def __init__(self, timeout_minutes: int, enabled: bool = True)
      async def execute(self, coro: Coroutine) -> T
      def record_activity(self) -> None
      def is_tripped(self) -> bool
  ```

### CircuitBreakerConfig (NEW)
**Location:** `src/cub/core/config/models.py`

- **Purpose:** Configuration for circuit breaker
- **Responsibilities:**
  - Define timeout duration
  - Enable/disable circuit breaker
- **Dependencies:** Pydantic
- **Interface:**
  ```python
  class CircuitBreakerConfig(BaseModel):
      enabled: bool = True
      timeout_minutes: int = 30
  ```

### DirectSessionCommands (NEW)
**Location:** `src/cub/cli/session.py`

- **Purpose:** Commands for direct harness sessions to record work
- **Responsibilities:**
  - `cub log <message>` — Add entry to session log
  - `cub done <task-id> [--reason]` — Mark task complete, add ledger entry
  - `cub wip <task-id>` — Mark task in-progress
- **Dependencies:** LedgerWriter, TaskBackend
- **Interface:** Typer CLI commands

### InstructionGenerator (NEW)
**Location:** `src/cub/core/instructions.py`

- **Purpose:** Generate CLAUDE.md and AGENTS.md with cub workflow instructions
- **Responsibilities:**
  - Generate harness-agnostic AGENTS.md
  - Generate Claude-specific CLAUDE.md additions
  - Include direct session workflow instructions
  - Include "giving up" escape hatch language
- **Dependencies:** Config, templates
- **Interface:**
  ```python
  def generate_agents_md(project_dir: Path, config: CubConfig) -> str
  def generate_claude_md(project_dir: Path, config: CubConfig) -> str
  ```

### HarnessHooks (NEW)
**Location:** `src/cub/core/harness/hooks.py`

- **Purpose:** Capture artifacts from harness hook events
- **Responsibilities:**
  - Parse Claude Code hook payloads
  - Extract plan content from ExitPlanMode
  - Capture session start/end events
  - Write to ledger on relevant events
- **Dependencies:** LedgerWriter, JSON parsing
- **Interface:**
  ```python
  def handle_hook_event(event_type: str, payload: dict) -> None
  ```

## Data Model

### CircuitBreakerConfig
```
enabled: bool = True          # Whether circuit breaker is active
timeout_minutes: int = 30     # Minutes of inactivity before trip
```

### CubConfig Addition
```python
class CubConfig(BaseModel):
    # ... existing fields ...
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()
```

### LedgerEntry Extension
```
source: Literal["cub_run", "direct_session"] = "cub_run"
session_type: str | None = None  # "claude", "codex", "opencode"
```

### Relationships
- CubConfig → CircuitBreakerConfig: composition (1:1)
- LedgerEntry → source: discriminator for audit trail origin
- RunLoop → CircuitBreaker: uses for timeout monitoring

## APIs / Interfaces

### CLI Commands (NEW)
- **Type:** Typer CLI
- **Purpose:** Direct session tracking
- **Key Commands:**
  - `cub log <message>`: Log session activity
  - `cub done <task-id> [--reason]`: Complete task with ledger entry
  - `cub wip <task-id>`: Mark task in-progress

### CircuitBreaker API
- **Type:** Internal Python
- **Purpose:** Timeout monitoring
- **Key Methods:**
  - `execute(coro)`: Run coroutine with timeout
  - `record_activity()`: Reset timeout timer
  - `is_tripped()`: Check if breaker has tripped

### InstructionGenerator API
- **Type:** Internal Python
- **Purpose:** Generate instruction files
- **Key Methods:**
  - `generate_agents_md()`: Create AGENTS.md content
  - `generate_claude_md()`: Create CLAUDE.md content

## Implementation Phases

### Phase 1: E4 - Core Loop Hardening
**Goal:** Verify and strengthen existing exit handling

- Audit all exit paths in `run.py`—document current behavior
- Add integration tests for: Ctrl+C, SIGTERM, budget exhaustion, iteration limit, task failure
- Ensure `StatusWriter.write_run_artifact()` called on ALL exit paths
- Add `pytest-timeout` to prevent test hangs
- Manual testing protocol for Marc

### Phase 2: E5 - Circuit Breaker
**Goal:** Time-based hang detection

- Add `CircuitBreakerConfig` to config models
- Implement `CircuitBreaker` class with asyncio timeout
- Integrate into harness invocation in `run.py`
- Add `--no-circuit-breaker` CLI flag
- Add prompt-level "giving up" instruction to task template
- Tests for timeout scenarios

### Phase 3: E6 - Symbiotic Workflow
**Goal:** Unified audit trail for direct sessions

- Create `cub log`, `cub done`, `cub wip` commands
- Implement `InstructionGenerator` for CLAUDE.md/AGENTS.md
- Update `cub init` to generate AGENTS.md at root
- Research Claude Code hooks—document available events
- Implement hook handlers for artifact capture (if hooks reliable)
- Manual testing: Marc runs direct Claude Code session, verifies ledger

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Harness subprocess doesn't expose activity | H | M | Fall back to wall-clock timeout only; activity detection is enhancement |
| Claude Code hooks change between versions | M | M | Version-check hooks; fall back to CLAUDE.md instructions |
| asyncio timeout doesn't cancel subprocess cleanly | M | L | Use `process.terminate()` then `kill()` with grace period |
| Direct session commands add friction | M | M | Keep commands minimal; test with Marc; iterate on UX |

## Dependencies

### External
- **Claude Code CLI:** Hook system for artifact capture
- **Codex CLI:** AGENTS.md compatibility
- **OpenCode CLI:** AGENTS.md compatibility

### Internal
- `src/cub/core/ledger/` — Ledger writer for unified audit trail
- `src/cub/core/config/` — Config models for circuit breaker
- `src/cub/cli/run.py` — Run loop integration point
- `src/cub/utils/hooks.py` — Existing hook framework

## Security Considerations

- Circuit breaker timeout is configurable but has sensible default (30 min)
- Direct session commands write to local `.cub/` only—no remote calls
- Hook payloads are parsed defensively (malformed input → skip, don't crash)

## Future Considerations

- **Semantic stagnation detection:** Analyze output for repeated errors, same-file loops (deferred per orient)
- **MCP integration:** Expose cub commands via MCP server for richer integration (deferred)
- **Cost tracking in direct mode:** Capture token usage from harness if reported (P2)

---

**Next Step:** Run `cub itemize` to generate implementation tasks.

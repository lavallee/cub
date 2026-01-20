# Architecture Design: Harness Abstraction

**Date:** 2026-01-19
**Mindset:** Production
**Scale:** Product (1,000+ users)
**Status:** Approved

---

## Technical Summary

The harness abstraction evolves the current synchronous Protocol-based design to an async-first architecture that leverages the Claude Agent SDK for rich features (hooks, custom tools, streaming) while preserving shell-out harnesses as fallbacks.

The key insight is that the Claude Agent SDK is **async-only** and provides `query()` for simple usage and `ClaudeSDKClient` for stateful, hook-enabled sessions. We build a new `AsyncHarnessBackend` Protocol that mirrors these capabilities, with graceful degradation for harnesses that don't support all features.

The architecture maintains backward compatibility by:
1. Renaming current harnesses to `*-legacy` (e.g., `claude-legacy`)
2. Creating new SDK-based harnesses with the original names
3. Providing a migration path via `--harness claude-legacy`

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing requirement; match statements and type unions |
| Async | anyio | Claude SDK uses anyio; provides asyncio/trio compatibility |
| SDK | claude-agent-sdk | Official Anthropic SDK for agentic Claude |
| HTTP | httpx (if needed) | Async-native HTTP client for direct API calls |
| Validation | Pydantic v2 | Existing; used for all models |
| Testing | pytest-asyncio | Async test support for new harnesses |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           cub run (async)                           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    HarnessSelector                            │  │
│  │  - select_harness(task, requirements) -> AsyncHarnessBackend  │  │
│  │  - detect_harness(priority) -> str                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                │                                    │
│         ┌──────────────────────┼──────────────────────┐            │
│         ▼                      ▼                      ▼            │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐      │
│  │ ClaudeSDK   │       │ ShellOut    │       │ OpenAI      │      │
│  │ Harness     │       │ Harness     │       │ Harness     │      │
│  │             │       │             │       │ (future)    │      │
│  │ • hooks ✓   │       │ • hooks ✗   │       │ • hooks ✗   │      │
│  │ • tools ✓   │       │ • tools ✗   │       │ • tools ✗   │      │
│  │ • stream ✓  │       │ • stream ✓  │       │ • stream ✓  │      │
│  └──────┬──────┘       └──────┬──────┘       └──────┬──────┘      │
│         │                     │                     │              │
│         ▼                     ▼                     ▼              │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐      │
│  │ Claude      │       │ claude CLI  │       │ OpenAI API  │      │
│  │ Agent SDK   │       │ codex CLI   │       │ (future)    │      │
│  │ (in-proc)   │       │ opencode    │       │             │      │
│  └─────────────┘       └─────────────┘       └─────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### AsyncHarnessBackend Protocol

- **Purpose:** Define the async interface all harnesses must implement
- **Responsibilities:**
  - Async task execution (`run_task`, `stream_task`)
  - Feature detection (`supports_feature`)
  - Hook registration (optional)
  - Custom tool registration (optional)
- **Dependencies:** Pydantic models, HarnessCapabilities
- **Interface:**

```python
@runtime_checkable
class AsyncHarnessBackend(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def capabilities(self) -> HarnessCapabilities: ...

    def is_available(self) -> bool: ...

    async def run_task(self, task: TaskInput) -> TaskResult: ...

    async def stream_task(
        self,
        task: TaskInput,
        callback: Callable[[str], None] | None = None
    ) -> TaskResult: ...

    def supports_feature(self, feature: HarnessFeature) -> bool: ...

    # Optional methods with default implementations
    def register_hook(
        self,
        event: HookEvent,
        handler: HookHandler
    ) -> None: ...

    def register_tool(self, tool: ToolDefinition) -> None: ...
```

### ClaudeSDKHarness

- **Purpose:** Full-featured Claude harness using Claude Agent SDK
- **Responsibilities:**
  - Execute tasks via `claude_agent_sdk.query()`
  - Register and execute hooks (PreToolUse, PostToolUse)
  - Register custom MCP tools via `@tool` decorator
  - Stream messages in real-time
  - Track token usage and costs
- **Dependencies:** claude-agent-sdk, Claude Code CLI
- **Interface:** Implements `AsyncHarnessBackend`

### ShellOutHarness

- **Purpose:** Generic shell-out harness for any CLI
- **Responsibilities:**
  - Execute tasks via `asyncio.subprocess`
  - Parse JSON/JSONL output
  - Stream stdout in real-time
  - Estimate token usage when not available
- **Dependencies:** asyncio.subprocess
- **Interface:** Implements `AsyncHarnessBackend`

**Variants:**
- `claude-legacy`: Current Claude shell-out (renamed)
- `codex`: OpenAI Codex CLI
- `opencode`: OpenCode CLI
- `gemini`: Google Gemini CLI (deferred)

### HarnessCapabilities (Extended)

- **Purpose:** Feature matrix for capability negotiation
- **Responsibilities:** Describe what each harness supports
- **Dependencies:** Pydantic BaseModel
- **Interface:**

```python
class HarnessCapabilities(BaseModel):
    # Existing
    streaming: bool = False
    token_reporting: bool = False
    system_prompt: bool = False
    auto_mode: bool = False
    json_output: bool = False
    model_selection: bool = False

    # New
    hooks: bool = False              # PreToolUse/PostToolUse hooks
    custom_tools: bool = False       # In-process MCP tools
    sessions: bool = False           # Stateful sessions
    session_forking: bool = False    # Can fork sessions
    subagents: bool = False          # Can spawn subagents
```

### HarnessFeature Enum

- **Purpose:** Standard feature flags for `supports_feature()`
- **Responsibilities:** Type-safe feature queries
- **Interface:**

```python
class HarnessFeature(str, Enum):
    HOOKS = "hooks"
    CUSTOM_TOOLS = "custom_tools"
    STREAMING = "streaming"
    SESSIONS = "sessions"
    SESSION_FORKING = "session_forking"
    SUBAGENTS = "subagents"
    COST_TRACKING = "cost_tracking"
    FILE_TRACKING = "file_tracking"
```

### Hook System

- **Purpose:** Event interception for circuit breakers, guardrails, etc.
- **Responsibilities:**
  - Define hook events (PRE_TASK, PRE_TOOL_USE, etc.)
  - Execute hooks at appropriate points
  - Allow hooks to block or modify behavior
- **Dependencies:** Claude SDK hook integration
- **Interface:**

```python
class HookEvent(str, Enum):
    PRE_TASK = "pre_task"
    POST_TASK = "post_task"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    ON_ERROR = "on_error"
    ON_MESSAGE = "on_message"

HookHandler = Callable[[HookContext], Awaitable[HookResult | None]]

@dataclass
class HookContext:
    event: HookEvent
    task: TaskInput
    tool_use: ToolUse | None = None
    message: Message | None = None
    error: Exception | None = None

@dataclass
class HookResult:
    block: bool = False
    reason: str | None = None
    modified_input: dict | None = None
```

## Data Model

### TaskInput

```python
class TaskInput(BaseModel):
    """Input for a harness task execution."""
    prompt: str
    system_prompt: str | None = None
    working_dir: Path | None = None
    max_turns: int = 100
    timeout_seconds: int | None = None
    auto_approve_edits: bool = False
    auto_approve_bash: bool = False
    task_id: str | None = None
    epic_id: str | None = None
    model: str | None = None
```

### TaskResult (Extended)

```python
class TaskResult(BaseModel):
    """Result of a harness task execution."""
    success: bool
    output: str
    messages: list[Message] = []
    usage: TokenUsage
    duration_seconds: float
    exit_code: int
    error: str | None = None
    files_changed: list[str] = []
    files_created: list[str] = []
    metadata: dict[str, Any] = {}
```

### Message

```python
class Message(BaseModel):
    """A message from the LLM."""
    role: Literal["assistant", "user", "system", "tool_result"]
    content: str
    tool_uses: list[ToolUse] = []
    metadata: dict[str, Any] = {}
```

### ToolUse

```python
class ToolUse(BaseModel):
    """A tool invocation."""
    tool_id: str
    tool_name: str
    input_data: dict[str, Any]
```

### Relationships

- `TaskInput` → `TaskResult`: One input produces one result
- `TaskResult` → `Message`: Result contains zero or more messages
- `Message` → `ToolUse`: Message may contain tool uses
- `HookContext` → `TaskInput`: Hooks receive task context
- `HookContext` → `ToolUse`: PRE/POST_TOOL_USE hooks receive tool info

## APIs / Interfaces

### Harness Registry API

- **Type:** Internal Python API
- **Purpose:** Register and retrieve harness backends
- **Key Methods:**
  - `register_backend(name: str)`: Decorator to register a backend class
  - `get_backend(name: str | None) -> AsyncHarnessBackend`: Get by name or auto-detect
  - `detect_harness(priority: list[str]) -> str | None`: Auto-detection
  - `list_available_backends() -> list[str]`: List installed backends

### AsyncHarnessBackend API

- **Type:** Internal Python Protocol
- **Purpose:** Execute tasks on LLM providers
- **Key Methods:**
  - `run_task(task: TaskInput) -> TaskResult`: Blocking async execution
  - `stream_task(task: TaskInput, callback) -> TaskResult`: Streaming execution
  - `supports_feature(feature: HarnessFeature) -> bool`: Feature detection
  - `register_hook(event: HookEvent, handler: HookHandler)`: Register hook
  - `register_tool(tool: ToolDefinition)`: Register custom tool

### CLI Harness Selection

- **Type:** CLI flags
- **Purpose:** User harness selection
- **Key Options:**
  - `--harness claude`: Use Claude SDK harness (default)
  - `--harness claude-legacy`: Use legacy shell-out harness
  - `--harness codex`: Use Codex CLI
  - `--harness opencode`: Use OpenCode CLI

## Implementation Phases

### Phase 1: Core Async Infrastructure
**Goal:** Establish async foundation without breaking existing code

- Create `AsyncHarnessBackend` Protocol in `src/cub/core/harness/async_backend.py`
- Add `HarnessFeature` enum to `src/cub/core/harness/models.py`
- Extend `HarnessCapabilities` with new fields (hooks, custom_tools, etc.)
- Create `TaskInput` model (distinct from beads Task)
- Extend `TaskResult` with messages, files_changed, files_created
- Add `anyio` and `pytest-asyncio` to dependencies
- Add async wrapper to `cub run` entry point

### Phase 2: Claude SDK Harness
**Goal:** Implement full-featured Claude harness with SDK

- Add `claude-agent-sdk` to dependencies
- Create `src/cub/core/harness/claude_sdk.py`
- Implement `ClaudeSDKHarness`:
  - `run_task()` using `query()`
  - `stream_task()` using `query()` with message iteration
  - Map cub options to `ClaudeAgentOptions`
- Parse SDK messages into `Message` models
- Extract token usage from SDK response
- Register as `claude` backend

### Phase 3: Legacy Harness Migration
**Goal:** Preserve existing harnesses under new names

- Rename `ClaudeBackend` to `ClaudeLegacyBackend` in `claude.py`
- Re-register as `claude-legacy`
- Create async wrapper for sync `invoke()` methods using `asyncio.to_thread()`
- Migrate `CodexBackend`, `OpenCodeBackend` to async wrappers
- Ensure all legacy harnesses implement `AsyncHarnessBackend`
- Add deprecation warning when using legacy harnesses

### Phase 4: Hook System
**Goal:** Enable circuit breaker and guardrails via hooks

- Define `HookEvent`, `HookContext`, `HookResult` in `models.py`
- Add `HookHandler` type alias
- Implement hook registry in `ClaudeSDKHarness`:
  - `register_hook(event, handler)`
  - `_execute_hooks(event, context)` internal method
- Map cub hooks to SDK's `PreToolUse`/`PostToolUse`:
  - `HookMatcher` for tool-specific hooks
  - Permission decision translation
- Add no-op hook methods to legacy harnesses
- Document hook API for downstream features

### Phase 5: CLI Integration & Testing
**Goal:** Update CLI and ensure comprehensive test coverage

- Update `cub run` to call async harness methods
- Add `--harness claude-legacy` flag documentation
- Update harness detection priority: claude (SDK) → claude-legacy → others
- Add integration tests for Claude SDK harness
- Add unit tests for hook system
- Update feature matrix documentation
- Add migration guide for users

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Claude SDK instability | High | Medium | Fallback to `claude-legacy` shell-out; wrap SDK calls in try/except with graceful degradation |
| Async migration breaks callers | Medium | Medium | Phase 1 adds wrapper without changing caller behavior; incremental migration |
| Node.js dependency via SDK | Medium | High | SDK requires Node 18+; document in prerequisites, detect at runtime and warn |
| Hook overhead impacts latency | Low | Low | Hooks are async, non-blocking; add benchmarks to measure overhead |
| OpenAI SDK not agentic | Low | High | Accept limited functionality for non-Claude providers; document feature matrix |

## Dependencies

### External (New)

- `claude-agent-sdk`: Anthropic's official SDK for agentic Claude
  - Provides: `query()`, `ClaudeSDKClient`, hooks, custom tools
  - Requires: Node.js 18+, Python 3.10+
- `anyio`: Async compatibility layer
  - Already used by claude-agent-sdk
  - Provides: asyncio/trio compatibility
- `pytest-asyncio`: Async test support
  - Provides: `@pytest.mark.asyncio` decorator

### Internal (Existing)

- `src/cub/core/harness/backend.py`: Current sync harness registry
- `src/cub/core/harness/models.py`: HarnessCapabilities, TokenUsage, HarnessResult
- `src/cub/core/harness/claude.py`: Current Claude shell-out (becomes claude-legacy)
- `src/cub/cli/run.py`: Main execution loop (needs async wrapper)
- `src/cub/core/config/models.py`: HarnessConfig

## Security Considerations

- **API keys**: Continue using environment variables (`ANTHROPIC_API_KEY`); SDK handles internally; never log keys
- **Tool permissions**: Claude SDK respects `permission_mode`; map cub's `auto_approve_edits`/`auto_approve_bash` flags
- **Command execution**: `PreToolUse` hooks can block dangerous commands; implement allowlist/denylist patterns
- **Audit logging**: `POST_TASK` and `POST_TOOL_USE` hooks can log all tool uses for compliance
- **Secrets in output**: Continue using existing secret redaction in logging

## Future Considerations

- **OpenAI SDK harness**: When/if OpenAI provides agentic SDK with tool use, add `OpenAISDKHarness`
- **Multi-model orchestration**: `HarnessSelector` could route tasks to best-fit provider based on requirements
- **Cost optimization**: Track costs per harness, suggest cheaper alternatives for simple tasks
- **Session management**: Claude SDK supports sessions; could enable conversation continuity across tasks
- **A/B testing**: Run same task on multiple harnesses, compare results for quality evaluation
- **Provider health monitoring**: Track rate limits, errors, latency; auto-switch if degraded

---

**Next Step:** Run `cub plan` to generate implementation tasks.

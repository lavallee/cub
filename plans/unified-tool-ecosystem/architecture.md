# Architecture Design: Unified Tool Ecosystem

**Date:** 2026-01-24
**Mindset:** Production
**Scale:** Product (single-user, 1000s of open source users)
**Status:** Approved

---

## Technical Summary

The Unified Tool Ecosystem extends cub's existing toolsmith foundation with a **generic execution runtime**, **JSON-based registry**, and **learning loop**. The architecture follows cub's established patterns: Protocol-based plugins, registry with decorator registration, and layered service architecture.

The system separates **discovery** (catalog of known tools) from **execution** (registry of approved tools). The catalog remains SQLite-based for efficient sync/search. The registry uses JSON for portability and human readability. Adoption bridges the two: moving a tool from "known" to "runnable."

The execution runtime uses a pluggable adapter pattern. Each adapter (HTTP, CLI, MCP stdio) implements a common Protocol. The existing brave-search HTTP implementation becomes the first concrete adapter. New adapters slot in without changing consumer code.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing codebase requirement |
| Data Models | Pydantic v2 | Established pattern, validation, serialization |
| CLI | Typer + Rich | Existing pattern, type-safe, good UX |
| Catalog Storage | SQLite (existing) | Efficient for sync/search operations |
| Registry Storage | JSON files | Portable, human-readable, git-friendly |
| HTTP Client | httpx | Already used in toolsmith, async-capable |
| Process Management | subprocess | Standard library, sufficient for spawn-per-call |
| MCP Protocol | JSON-RPC over stdio | MCP standard, simple process model |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLI Layer (Typer)                                │
│   cub tools list | describe | adopt | run | stats                       │
│   cub toolsmith sync | search | stats (existing)                        │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────────┐
│                      Service Layer                                       │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────────┐  │
│  │ ToolsmithService│  │  RegistryService │  │   ExecutionService     │  │
│  │ (discovery)     │  │  (approved tools)│  │   (run tools)          │  │
│  └────────┬────────┘  └────────┬─────────┘  └───────────┬────────────┘  │
│           │                    │                        │               │
└───────────┼────────────────────┼────────────────────────┼───────────────┘
            │                    │                        │
┌───────────▼────────┐  ┌────────▼─────────┐  ┌──────────▼──────────────┐
│  Catalog (SQLite)  │  │ Registry (JSON)  │  │   Adapter Layer         │
│  .cub/toolsmith/   │  │ ~/.config/cub/   │  │  ┌─────────────────┐    │
│  catalog.db        │  │   tools/         │  │  │ ToolAdapter     │    │
│                    │  │ .cub/tools/      │  │  │ (Protocol)      │    │
│  - Tool metadata   │  │                  │  │  └────────┬────────┘    │
│  - Source sync     │  │  - registry.json │  │           │             │
│  - Search index    │  │  - approvals.json│  │  ┌───────┴────────┐    │
│                    │  │  - metrics.json  │  │  │                │    │
└────────────────────┘  └──────────────────┘  │  ▼                ▼    │
                                              │ HTTPAdapter  CLIAdapter │
                                              │      │            │     │
                                              │      ▼            ▼     │
                                              │ MCPStdioAdapter (P1)    │
                                              └─────────────────────────┘
                                                        │
                                              ┌─────────▼─────────┐
                                              │   Learning Loop   │
                                              │   metrics.json    │
                                              │   - success_rate  │
                                              │   - avg_duration  │
                                              │   - error_patterns│
                                              └───────────────────┘
```

## Components

### 1. ToolAdapter (Protocol)

**Purpose:** Abstract interface for tool execution backends

**Responsibilities:**
- Execute tool actions with parameters
- Return structured results (success/failure, output, timing)
- Check tool availability/readiness
- Handle timeouts and errors consistently

**Dependencies:** None (pure protocol)

**Interface:**
```python
@runtime_checkable
class ToolAdapter(Protocol):
    """Protocol for tool execution adapters."""

    @property
    def adapter_type(self) -> str:
        """Adapter type identifier (http, cli, mcp_stdio)."""
        ...

    def execute(
        self,
        tool_id: str,
        action: str,
        params: dict[str, Any],
        timeout: float = 30.0,
    ) -> ToolResult:
        """Execute a tool action and return structured result."""
        ...

    def is_available(self, tool_config: ToolConfig) -> bool:
        """Check if tool is ready to execute (deps installed, auth present)."""
        ...
```

### 2. HTTPAdapter

**Purpose:** Execute tools via REST APIs (existing brave-search pattern)

**Responsibilities:**
- Make HTTP requests with auth headers
- Parse JSON responses
- Handle rate limits and retries
- Map tool config to HTTP request

**Dependencies:** httpx, ToolConfig

**Interface:** Implements `ToolAdapter` protocol

### 3. CLIAdapter

**Purpose:** Execute tools via subprocess (shell commands)

**Responsibilities:**
- Build command line from tool config and params
- Execute subprocess with timeout
- Capture stdout/stderr
- Parse output (JSON if structured, text otherwise)
- Handle exit codes

**Dependencies:** subprocess (stdlib), ToolConfig

**Interface:** Implements `ToolAdapter` protocol

### 4. MCPStdioAdapter (P1)

**Purpose:** Execute MCP servers via stdio JSON-RPC

**Responsibilities:**
- Spawn MCP server process
- Send JSON-RPC request via stdin
- Read JSON-RPC response from stdout
- Kill process after response or timeout
- Handle MCP protocol errors

**Dependencies:** subprocess, json (stdlib), ToolConfig

**Interface:** Implements `ToolAdapter` protocol

**Design Notes:**
- Spawn-per-call model (no persistent servers in v1)
- Process killed after timeout (default 30s)
- Stderr captured for debugging
- Future: connection pooling if performance requires

### 5. Registry (JSON Storage)

**Purpose:** Track tools approved for execution

**Responsibilities:**
- Load/merge user + project registries
- Store tool configurations (how to invoke)
- Track approval metadata (when, by whom, version)
- Provide capability-based lookup

**Dependencies:** Pydantic models, pathlib

**Storage Locations:**
- User: `~/.config/cub/tools/registry.json`
- Project: `.cub/tools/registry.json`
- Resolution: Project overrides User

**Schema:**
```python
class ToolConfig(BaseModel):
    """Configuration for an approved tool."""
    id: str                      # e.g., "brave-search"
    name: str                    # Human-readable name
    adapter_type: AdapterType    # http | cli | mcp_stdio
    capabilities: list[str]      # ["web_search", "current_events"]

    # Adapter-specific config
    http_config: HTTPConfig | None = None
    cli_config: CLIConfig | None = None
    mcp_config: MCPConfig | None = None

    # Auth requirements
    auth: AuthConfig | None = None

    # Approval metadata
    adopted_at: datetime
    adopted_from: str            # catalog source
    version_hash: str | None     # For re-approval detection

class Registry(BaseModel):
    """Tool registry with approved tools."""
    version: str = "1.0.0"
    tools: dict[str, ToolConfig] = {}
```

### 6. RegistryService

**Purpose:** Business logic for registry operations

**Responsibilities:**
- Load and merge user/project registries
- Add/remove tools from registry
- Find tools by capability
- Check approval status
- Detect version changes requiring re-approval

**Dependencies:** Registry model, RegistryStore

**Interface:**
```python
class RegistryService:
    def load(self) -> Registry:
        """Load merged registry (project over user)."""

    def adopt(self, tool: Tool, config: ToolConfig) -> ToolConfig:
        """Add tool to project registry."""

    def find_by_capability(self, capability: str) -> list[ToolConfig]:
        """Find tools that provide a capability."""

    def is_approved(self, tool_id: str) -> bool:
        """Check if tool is approved for execution."""

    def needs_reapproval(self, tool_id: str) -> bool:
        """Check if tool version changed since approval."""
```

### 7. ExecutionService

**Purpose:** Orchestrate tool execution with adapters

**Responsibilities:**
- Select appropriate adapter for tool
- Execute with timeout and error handling
- Record metrics (success/failure, duration)
- Write artifacts to `.cub/toolsmith/runs/`
- Return unified ToolResult

**Dependencies:** ToolAdapter implementations, RegistryService, MetricsStore

**Interface:**
```python
class ExecutionService:
    def execute(
        self,
        tool_id: str,
        action: str = "default",
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> ToolResult:
        """Execute a registered tool."""

    def check_ready(self, tool_id: str) -> ReadinessCheck:
        """Check if tool is ready (auth, deps)."""
```

### 8. Learning Loop (MetricsStore)

**Purpose:** Track tool effectiveness over time

**Responsibilities:**
- Record execution outcomes (success/failure)
- Track timing statistics
- Identify error patterns
- Surface degraded tools
- Provide data for tool selection scoring

**Dependencies:** Pydantic models, JSON storage

**Storage:** `.cub/tools/metrics.json` (project-level)

**Schema:**
```python
class ToolMetrics(BaseModel):
    """Execution metrics for a tool."""
    tool_id: str
    invocations: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: int = 0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    last_error: str | None = None
    error_counts: dict[str, int] = {}  # error_type -> count

    @property
    def success_rate(self) -> float:
        if self.invocations == 0:
            return 0.0
        return self.successes / self.invocations

    @property
    def avg_duration_ms(self) -> float:
        if self.successes == 0:
            return 0.0
        return self.total_duration_ms / self.successes
```

### 9. ToolResult (Unified Result Model)

**Purpose:** Consistent result structure across all adapters

**Responsibilities:**
- Capture success/failure status
- Store structured output and markdown summary
- Record timing and resource usage
- Preserve error details

**Schema:**
```python
class ToolResult(BaseModel):
    """Result from tool execution."""
    tool_id: str
    action: str
    success: bool

    # Output
    output: Any                    # Structured data (JSON-serializable)
    output_markdown: str | None    # Human-readable summary

    # Timing
    started_at: datetime
    duration_ms: int

    # Resource usage (optional)
    tokens_used: int | None = None

    # Error details (if failed)
    error: str | None = None
    error_type: str | None = None  # For categorization

    # Metadata
    adapter_type: str
    artifact_path: Path | None = None
```

## Data Model

### Entity Relationships

```
Catalog (SQLite)                    Registry (JSON)
┌─────────────┐                    ┌──────────────┐
│    Tool     │                    │  ToolConfig  │
│ (discovered)│────adoption───────▶│  (approved)  │
└─────────────┘                    └──────────────┘
      │                                   │
      │                                   │
      ▼                                   ▼
┌─────────────┐                    ┌──────────────┐
│   Source    │                    │  ToolResult  │
│ (sync from) │                    │ (execution)  │
└─────────────┘                    └──────────────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │ ToolMetrics  │
                                   │ (learning)   │
                                   └──────────────┘
```

### Key Entities

**Tool** (existing, catalog):
```
id: str              # "source:slug" format
name: str
source: str
source_url: str
tool_type: ToolType  # MCP_SERVER | SKILL
description: str
install_hint: str
tags: list[str]
last_seen: datetime
```

**ToolConfig** (new, registry):
```
id: str
name: str
adapter_type: AdapterType  # http | cli | mcp_stdio
capabilities: list[str]
http_config: HTTPConfig | None
cli_config: CLIConfig | None
mcp_config: MCPConfig | None
auth: AuthConfig | None
adopted_at: datetime
adopted_from: str
version_hash: str | None
```

**HTTPConfig**:
```
base_url: str
endpoints: dict[str, str]    # action -> path
headers: dict[str, str]      # static headers
auth_header: str | None      # header name for auth
auth_env_var: str | None     # env var for auth value
```

**CLIConfig**:
```
command: str                 # base command
args_template: str | None    # template for args
output_format: str           # json | text | lines
env_vars: dict[str, str]     # env var mappings
```

**MCPConfig**:
```
command: str                 # command to spawn server
args: list[str]              # arguments
env_vars: dict[str, str]     # env var mappings
```

**AuthConfig**:
```
required: bool
env_var: str                 # e.g., "BRAVE_API_KEY"
signup_url: str | None       # where to get credentials
description: str | None      # what this auth is for
```

## APIs / Interfaces

### CLI Commands

**New `cub tools` subcommand:**
```bash
# List registered tools
cub tools list
cub tools list --capability web_search

# Describe a tool
cub tools describe brave-search

# Adopt a tool from catalog to registry
cub tools adopt mcp-official:brave-search
cub tools adopt mcp-official:brave-search --name brave-search

# Run a registered tool
cub tools run brave-search --query "python async patterns"
cub tools run brave-search --action search --params '{"q": "test"}'

# Check tool readiness
cub tools check brave-search

# View metrics
cub tools stats
cub tools stats brave-search
```

**Enhanced `cub toolsmith` (existing):**
```bash
# Existing commands remain
cub toolsmith sync
cub toolsmith search "database"
cub toolsmith stats

# Enhanced adopt (bridges to registry)
cub toolsmith adopt mcp-official:brave-search
```

### Internal Service API

```python
# Discovery (existing)
toolsmith_service.sync(source_names=["smithery"])
toolsmith_service.search("web search")

# Registry (new)
registry_service.load() -> Registry
registry_service.adopt(tool, config) -> ToolConfig
registry_service.find_by_capability("web_search") -> list[ToolConfig]

# Execution (new)
execution_service.execute("brave-search", params={"query": "test"}) -> ToolResult
execution_service.check_ready("brave-search") -> ReadinessCheck

# Metrics (new)
metrics_store.record(tool_id, result)
metrics_store.get(tool_id) -> ToolMetrics
metrics_store.get_degraded(threshold=0.7) -> list[ToolMetrics]
```

## Implementation Phases

### Phase 1: Execution Runtime Foundation
**Goal:** Replace hardcoded execution with pluggable adapters

- [ ] Define `ToolAdapter` protocol in `cub.core.tools.adapter`
- [ ] Define `ToolResult` model in `cub.core.tools.models`
- [ ] Implement `HTTPAdapter` (migrate brave-search logic)
- [ ] Implement `CLIAdapter` (subprocess wrapper)
- [ ] Add adapter registry with decorator pattern
- [ ] Create `ExecutionService` to orchestrate
- [ ] Tests for adapters (mock HTTP, subprocess)

**Deliverables:**
- `src/cub/core/tools/adapter.py` - Protocol + registry
- `src/cub/core/tools/adapters/http.py` - HTTP adapter
- `src/cub/core/tools/adapters/cli.py` - CLI adapter
- `src/cub/core/tools/models.py` - ToolResult, configs
- `src/cub/core/tools/execution.py` - ExecutionService

### Phase 2: Registry and Adoption
**Goal:** JSON-based registry as source of truth for runnable tools

- [ ] Define registry models (`ToolConfig`, `Registry`)
- [ ] Implement `RegistryStore` (JSON load/save, merge)
- [ ] Implement `RegistryService` (adopt, find, check)
- [ ] Enhance adoption workflow (toolsmith → registry)
- [ ] Add `cub tools` CLI subcommand
- [ ] Add capability-based lookup
- [ ] Tests for registry operations

**Deliverables:**
- `src/cub/core/tools/registry.py` - RegistryStore + RegistryService
- `src/cub/cli/tools.py` - New CLI subcommand
- Enhanced `cub toolsmith adopt` command

### Phase 3: Learning Loop
**Goal:** Track tool effectiveness over time

- [ ] Define `ToolMetrics` model
- [ ] Implement `MetricsStore` (record, query)
- [ ] Integrate metrics recording into ExecutionService
- [ ] Add metrics CLI commands (`cub tools stats`)
- [ ] Identify degraded tools (success_rate < threshold)
- [ ] Tests for metrics tracking

**Deliverables:**
- `src/cub/core/tools/metrics.py` - MetricsStore
- Metrics integration in ExecutionService
- `cub tools stats` command

### Phase 4: MCP Stdio Adapter (P1)
**Goal:** Execute MCP servers via stdio

- [ ] Implement `MCPStdioAdapter`
- [ ] JSON-RPC message formatting
- [ ] Process spawn/kill lifecycle
- [ ] Timeout handling
- [ ] Tests with mock MCP server

**Deliverables:**
- `src/cub/core/tools/adapters/mcp_stdio.py`

### Phase 5: Lifecycle Integration
**Goal:** Wire tools into cub's broader ecosystem

- [ ] Hook registration from tools
- [ ] Workbench tool invocation
- [ ] Freedom dial configuration
- [ ] Capability gap recognition API
- [ ] Integration tests

**Deliverables:**
- Hook integration in `cub.utils.hooks`
- Workbench integration
- Freedom dial in config

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| MCP server process leaks (zombies) | Medium | Medium | Use process groups, explicit cleanup, timeout kill |
| CLI command injection | High | Low | Strict arg validation, no shell=True, allowlist commands |
| Credentials in logs | High | Medium | Redact env vars matching secret patterns in all logging |
| Registry merge conflicts | Low | Low | Project wins on conflict, user registry is fallback |
| Adapter interface insufficient | Medium | Medium | Start minimal, extend Protocol as needed (backward compatible) |

## Dependencies

### External
- **httpx**: HTTP client for API tools (existing dependency)
- **Brave Search API**: Web search capability (existing)
- **MCP servers**: Various (filesystem, github, etc.) - user-installed

### Internal
- **cub.core.toolsmith**: Catalog and discovery (existing)
- **cub.core.config**: Configuration loading (existing)
- **cub.utils.hooks**: Hook system (future integration)

## Security Considerations

**Production mindset security:**

1. **Credential handling:**
   - Env vars only (no plaintext in config)
   - Redact secrets in logs (pattern matching)
   - Never include credentials in error messages

2. **Command execution:**
   - No `shell=True` in subprocess calls
   - Validate/sanitize all command arguments
   - Allowlist approach for CLI tools

3. **Process isolation:**
   - Subprocess timeout enforcement
   - Kill process group on timeout (not just process)
   - Capture stderr for debugging, don't expose to users by default

4. **Approval model:**
   - Explicit adoption required before execution
   - Version hash tracking for re-approval
   - Clear audit trail (adopted_at, adopted_from)

## Future Considerations

**Explicitly deferred:**

1. **Persistent MCP servers** - Start with spawn-per-call, add pooling if performance requires
2. **Tool generation** - High value but complex; sequence after execution foundation
3. **Full marketplace** - Cross-project sharing for same user only in v1
4. **Async adapters** - Sync-first, can wrap with `asyncio.to_thread()` if needed
5. **UI** - CLI-first, but design API surface with future UI in mind

**Design for extensibility:**

- Protocol-based adapters allow new adapter types without changing core
- Registry schema versioned for future evolution
- Metrics schema allows additional fields
- Capability taxonomy is free-form (can evolve)

---

**Next Step:** Run `cub itemize` to break this into executable tasks.

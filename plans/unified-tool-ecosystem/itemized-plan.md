# Itemized Plan: Unified Tool Ecosystem

> Source: [unified-tool-ecosystem.md](../../specs/researching/unified-tool-ecosystem.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-24

## Context Summary

Cub agents need external capabilities (web search, code analysis, competitive research) to operate autonomously. Currently humans manually discover, evaluate, integrate, and maintain tools. This blocks autonomous operation. The Unified Tool Ecosystem provides a coherent lifecycle: Discover → Adopt → Execute → Learn.

**Mindset:** Production | **Scale:** Product (single-user, 1000s of open source users)

---

## Epic: cub-x7f - unified-tool-ecosystem #1: Execution Runtime Foundation

Priority: 0
Labels: phase-1, complexity:high, critical-path

Replace the hardcoded brave-search execution with a pluggable adapter system. This is the foundation for all tool execution - HTTP, CLI, and future MCP adapters all build on this.

### Task: cub-x7f.1 - Define ToolAdapter Protocol and adapter registry

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, setup

**Context**: The adapter pattern enables pluggable tool execution backends. Following cub's established patterns (harness/tasks backends), we use a Protocol with decorator-based registration.

**Implementation Steps**:
1. Create `src/cub/core/tools/` package with `__init__.py`
2. Create `src/cub/core/tools/adapter.py` with:
   - `ToolAdapter` Protocol (runtime_checkable) with `adapter_type`, `execute()`, `is_available()` methods
   - Module-level registry dict `_adapters: dict[str, type[ToolAdapter]]`
   - `@register_adapter(name)` decorator
   - `get_adapter()`, `list_adapters()`, `get_all_adapters()` functions
3. Follow existing patterns from `cub.core.harness.backend` and `cub.core.toolsmith.sources.base`

**Acceptance Criteria**:
- [ ] `ToolAdapter` Protocol defined with all methods from architecture
- [ ] Registry pattern implemented with decorator registration
- [ ] `get_adapter("http")` returns registered adapter class
- [ ] Raises clear error for unregistered adapter names

**Files**: `src/cub/core/tools/__init__.py`, `src/cub/core/tools/adapter.py`

---

### Task: cub-x7f.2 - Define ToolResult and adapter config models

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, model

**Context**: Unified result structure ensures all adapters return consistent data. Config models (HTTPConfig, CLIConfig, MCPConfig, AuthConfig) define how each adapter type is configured.

**Implementation Steps**:
1. Create `src/cub/core/tools/models.py` with Pydantic v2 models:
   - `AdapterType` enum (http, cli, mcp_stdio)
   - `ToolResult` with all fields from architecture (tool_id, action, success, output, output_markdown, started_at, duration_ms, tokens_used, error, error_type, adapter_type, artifact_path)
   - `HTTPConfig` (base_url, endpoints, headers, auth_header, auth_env_var)
   - `CLIConfig` (command, args_template, output_format, env_vars)
   - `MCPConfig` (command, args, env_vars)
   - `AuthConfig` (required, env_var, signup_url, description)
2. Add field validators for datetime handling (timezone-aware, Z suffix support)
3. Use `ConfigDict(populate_by_name=True)` for all models

**Acceptance Criteria**:
- [ ] All models defined with proper Pydantic v2 syntax
- [ ] `ToolResult.model_dump(mode='json')` produces valid JSON
- [ ] Datetime fields handle timezone normalization
- [ ] Models include docstrings with field descriptions

**Files**: `src/cub/core/tools/models.py`

---

### Task: cub-x7f.3 - Implement HTTPAdapter

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, logic

**Context**: The HTTP adapter handles REST API tools like Brave Search. This migrates and generalizes the existing brave-search logic from `cub.core.toolsmith.execution`.

**Implementation Steps**:
1. Create `src/cub/core/tools/adapters/` package
2. Create `src/cub/core/tools/adapters/http.py` with `HTTPAdapter` class:
   - Register with `@register_adapter("http")`
   - `adapter_type` property returns "http"
   - `execute()` builds HTTP request from HTTPConfig, makes request via httpx, returns ToolResult
   - `is_available()` checks auth env var is set if required
3. Handle rate limits with exponential backoff (3 retries)
4. Map HTTP errors to ToolResult.error_type categories
5. Generate output_markdown summary from response

**Acceptance Criteria**:
- [ ] HTTPAdapter registered and retrievable via `get_adapter("http")`
- [ ] Execute method makes HTTP request and returns ToolResult
- [ ] Auth header populated from env var when configured
- [ ] HTTP errors mapped to structured error response (not exceptions)
- [ ] Timeout enforced via httpx timeout parameter

**Files**: `src/cub/core/tools/adapters/__init__.py`, `src/cub/core/tools/adapters/http.py`

---

### Task: cub-x7f.4 - Implement CLIAdapter

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, logic

**Context**: The CLI adapter executes tools via subprocess. This enables integration with command-line tools like `gh`, `jq`, etc.

**Implementation Steps**:
1. Create `src/cub/core/tools/adapters/cli.py` with `CLIAdapter` class:
   - Register with `@register_adapter("cli")`
   - `execute()` builds command from CLIConfig, runs subprocess with timeout
   - Capture stdout/stderr separately
   - Parse output based on `output_format` (json, text, lines)
   - Map exit codes to success/failure
2. Security: NO `shell=True`, validate/sanitize arguments
3. Use `subprocess.run()` with `timeout` parameter
4. Handle `subprocess.TimeoutExpired` gracefully

**Acceptance Criteria**:
- [ ] CLIAdapter registered and retrievable
- [ ] Subprocess executed without shell=True
- [ ] Timeout enforced, TimeoutExpired caught and converted to ToolResult
- [ ] JSON output parsed when output_format="json"
- [ ] Non-zero exit code results in success=False with stderr in error field

**Files**: `src/cub/core/tools/adapters/cli.py`

---

### Task: cub-x7f.5 - Create ExecutionService

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, logic

**Context**: ExecutionService orchestrates tool execution - selecting the right adapter, enforcing timeouts, and writing artifacts. It's the main entry point for running tools.

**Implementation Steps**:
1. Create `src/cub/core/tools/execution.py` with `ExecutionService` class:
   - Constructor takes optional adapter overrides (for testing)
   - `execute(tool_id, action, params, timeout)` method:
     - Look up tool config (placeholder for now, will integrate with registry)
     - Get appropriate adapter based on `adapter_type`
     - Call adapter.execute() with timing
     - Write artifact to `.cub/toolsmith/runs/`
     - Return ToolResult
   - `check_ready(tool_id)` checks adapter.is_available()
2. Add `ReadinessCheck` model (ready: bool, missing: list[str])
3. Use atomic write pattern for artifacts (tempfile → rename)

**Acceptance Criteria**:
- [ ] ExecutionService.execute() returns ToolResult
- [ ] Correct adapter selected based on tool config
- [ ] Artifact written to `.cub/toolsmith/runs/{timestamp}-{tool_id}.json`
- [ ] Timing recorded in ToolResult.duration_ms
- [ ] check_ready() returns clear status with missing requirements

**Files**: `src/cub/core/tools/execution.py`

---

### Task: cub-x7f.6 - Add tests for execution runtime

Priority: 1
Labels: phase-1, model:sonnet, complexity:medium, test

**Context**: Production mindset requires comprehensive tests. Test adapters with mocks, verify the execution service orchestration.

**Implementation Steps**:
1. Create `tests/test_tools_adapter.py`:
   - Test adapter registry (register, get, list)
   - Test ToolResult model validation
   - Test config models
2. Create `tests/test_tools_http.py`:
   - Mock httpx responses
   - Test success/failure paths
   - Test timeout handling
   - Test auth header injection
3. Create `tests/test_tools_cli.py`:
   - Mock subprocess
   - Test output parsing (json, text)
   - Test timeout handling
   - Test exit code mapping
4. Create `tests/test_tools_execution.py`:
   - Test ExecutionService with mock adapters
   - Test artifact writing
   - Test check_ready

**Acceptance Criteria**:
- [ ] All tests pass with `pytest tests/test_tools_*.py`
- [ ] Coverage >70% for adapter.py, models.py, http.py, cli.py, execution.py
- [ ] No network calls in tests (all mocked)
- [ ] Edge cases covered (timeouts, errors, missing auth)

**Files**: `tests/test_tools_adapter.py`, `tests/test_tools_http.py`, `tests/test_tools_cli.py`, `tests/test_tools_execution.py`

---

## Epic: cub-m3k - unified-tool-ecosystem #2: Registry and Adoption

Priority: 0
Labels: phase-2, complexity:high, critical-path

JSON-based registry as the source of truth for tools approved for execution. Bridges discovery (catalog) to execution (registry) via adoption workflow.

### Task: cub-m3k.1 - Define ToolConfig and Registry models

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, model
Blocks: cub-m3k.2

**Context**: ToolConfig represents an approved tool with all config needed to execute it. Registry holds all approved tools with version tracking.

**Implementation Steps**:
1. Add to `src/cub/core/tools/models.py`:
   - `ToolConfig` model with all fields from architecture (id, name, adapter_type, capabilities, http_config, cli_config, mcp_config, auth, adopted_at, adopted_from, version_hash)
   - `Registry` model (version: str, tools: dict[str, ToolConfig])
2. Add validators:
   - `adopted_at` timezone normalization
   - `version_hash` optional but recommended
3. Add helper methods:
   - `Registry.get(tool_id)` returns ToolConfig or None
   - `Registry.add(config)` adds/updates tool
   - `Registry.remove(tool_id)` removes tool

**Acceptance Criteria**:
- [ ] ToolConfig model validates all required fields
- [ ] Registry.tools is dict keyed by tool_id
- [ ] Model can serialize to/from JSON
- [ ] Version field defaults to "1.0.0"

**Files**: `src/cub/core/tools/models.py`

---

### Task: cub-m3k.2 - Implement RegistryStore

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, logic
Blocks: cub-m3k.3

**Context**: RegistryStore handles JSON file I/O for registry persistence. Supports user-level and project-level registries with merge logic.

**Implementation Steps**:
1. Create `src/cub/core/tools/registry.py` with `RegistryStore` class:
   - `__init__(user_path, project_path)` with defaults
   - Default paths: `~/.config/cub/tools/registry.json` (user), `.cub/tools/registry.json` (project)
   - `load_user()` returns Registry from user path
   - `load_project()` returns Registry from project path
   - `load_merged()` returns merged registry (project overrides user)
   - `save_project(registry)` writes to project path (atomic write)
2. Handle missing files gracefully (return empty registry)
3. Use atomic write pattern (tempfile → rename)
4. Create parent directories if needed

**Acceptance Criteria**:
- [ ] Load returns empty registry if file doesn't exist
- [ ] Project registry overrides user registry on merge
- [ ] Save uses atomic write pattern
- [ ] Parent directories created automatically
- [ ] JSON files are human-readable (indent=2)

**Files**: `src/cub/core/tools/registry.py`

---

### Task: cub-m3k.3 - Implement RegistryService

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, logic
Blocks: cub-m3k.4

**Context**: RegistryService provides business logic for registry operations - adoption, capability lookup, approval checking.

**Implementation Steps**:
1. Add `RegistryService` class to `src/cub/core/tools/registry.py`:
   - `__init__(store: RegistryStore)`
   - `load() -> Registry` delegates to store.load_merged()
   - `adopt(tool: Tool, config: ToolConfig) -> ToolConfig` adds to project registry
   - `find_by_capability(capability: str) -> list[ToolConfig]` searches tools
   - `is_approved(tool_id: str) -> bool` checks if tool in registry
   - `needs_reapproval(tool_id: str, current_hash: str) -> bool` compares version_hash
   - `remove(tool_id: str)` removes from project registry
2. Generate version_hash from tool metadata (name, source, description hash)

**Acceptance Criteria**:
- [ ] adopt() adds tool to project registry and saves
- [ ] find_by_capability() returns tools with matching capability
- [ ] is_approved() returns True only for registered tools
- [ ] needs_reapproval() detects hash mismatch
- [ ] All operations load fresh registry (no stale cache)

**Files**: `src/cub/core/tools/registry.py`

---

### Task: cub-m3k.4 - Integrate registry with ExecutionService

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, logic

**Context**: ExecutionService needs to look up tool config from registry before execution. This completes the adopt → execute flow.

**Implementation Steps**:
1. Update `ExecutionService.__init__` to accept `RegistryService`
2. Update `execute()` to:
   - Load tool config from registry via `registry_service.load().get(tool_id)`
   - Raise clear error if tool not in registry ("Tool not adopted. Run: cub tools adopt ...")
   - Pass config to adapter
3. Update `check_ready()` to also verify tool is in registry
4. Add `ToolNotAdoptedError` to exceptions

**Acceptance Criteria**:
- [ ] execute() raises ToolNotAdoptedError for non-adopted tools
- [ ] Error message includes adoption command hint
- [ ] Tool config loaded from merged registry
- [ ] Existing tests updated to provide registry

**Files**: `src/cub/core/tools/execution.py`, `src/cub/core/tools/exceptions.py`

---

### Task: cub-m3k.5 - Create cub tools CLI subcommand

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, api

**Context**: The `cub tools` CLI provides user-facing commands for listing, describing, adopting, running, and checking tools.

**Implementation Steps**:
1. Create `src/cub/cli/tools.py` with Typer app:
   - `list` command: show registered tools (table with id, name, adapter_type, capabilities)
   - `list --capability X` filter by capability
   - `describe <tool_id>`: show full tool config (panel with details)
   - `adopt <catalog_id>`: adopt tool from catalog to registry (interactive config)
   - `run <tool_id>`: execute tool (accept --params as JSON)
   - `check <tool_id>`: show readiness status
2. Register in `src/cub/cli/__init__.py`: `app.add_typer(tools.app, name="tools")`
3. Use Rich for formatted output (tables, panels)
4. Follow existing CLI patterns from toolsmith.py

**Acceptance Criteria**:
- [ ] `cub tools list` shows registered tools in table
- [ ] `cub tools describe brave-search` shows full config
- [ ] `cub tools run brave-search --params '{"query": "test"}'` executes tool
- [ ] Commands follow existing CLI style (Rich panels, error handling)
- [ ] Help text with examples for each command

**Files**: `src/cub/cli/tools.py`, `src/cub/cli/__init__.py`

---

### Task: cub-m3k.6 - Enhance toolsmith adopt to bridge to registry

Priority: 1
Labels: phase-2, model:sonnet, complexity:medium, logic

**Context**: The existing `cub toolsmith adopt` records adoption intent. Enhance it to also create a registry entry, completing the catalog → registry flow.

**Implementation Steps**:
1. Update `src/cub/cli/toolsmith.py` adopt command:
   - After recording adoption in AdoptionStore, also create ToolConfig
   - Prompt user for adapter_type if not inferrable from tool metadata
   - Prompt for capabilities (suggest defaults based on tags)
   - Create ToolConfig with appropriate config (HTTPConfig, CLIConfig, etc.)
   - Save to registry via RegistryService
2. Add `--adapter` and `--capabilities` options for non-interactive use
3. Show confirmation with registry entry details

**Acceptance Criteria**:
- [ ] `cub toolsmith adopt mcp-official:brave-search` creates registry entry
- [ ] User prompted for adapter_type and capabilities interactively
- [ ] `--adapter http --capabilities web_search` works non-interactively
- [ ] Tool appears in `cub tools list` after adoption

**Files**: `src/cub/cli/toolsmith.py`

---

### Task: cub-m3k.7 - Add tests for registry

Priority: 1
Labels: phase-2, model:sonnet, complexity:medium, test

**Context**: Test registry models, store operations, and service logic.

**Implementation Steps**:
1. Create `tests/test_tools_registry.py`:
   - Test ToolConfig and Registry model validation
   - Test RegistryStore load/save/merge
   - Test RegistryService adopt/find/check operations
   - Test version_hash generation and comparison
2. Use tmp_path fixture for file operations
3. Test merge logic (project overrides user)
4. Test missing file handling

**Acceptance Criteria**:
- [ ] All tests pass
- [ ] Coverage >70% for registry.py
- [ ] Merge logic tested (project wins on conflict)
- [ ] Edge cases: empty registry, missing files, invalid JSON

**Files**: `tests/test_tools_registry.py`

---

## Epic: cub-p9q - unified-tool-ecosystem #3: Learning Loop

Priority: 1
Labels: phase-3, complexity:medium

Track tool effectiveness over time. Record success/failure, timing, and error patterns to enable informed tool selection.

### Task: cub-p9q.1 - Define ToolMetrics model

Priority: 1
Labels: phase-3, model:sonnet, complexity:low, model
Blocks: cub-p9q.2

**Context**: ToolMetrics tracks execution statistics per tool - invocation count, success rate, timing, errors.

**Implementation Steps**:
1. Add to `src/cub/core/tools/models.py`:
   - `ToolMetrics` model with fields from architecture
   - Computed properties: `success_rate`, `avg_duration_ms`
   - `MetricsRegistry` model (version: str, tools: dict[str, ToolMetrics])
2. Add helper methods:
   - `ToolMetrics.record_success(duration_ms)`
   - `ToolMetrics.record_failure(error, error_type, duration_ms)`

**Acceptance Criteria**:
- [ ] ToolMetrics computes success_rate correctly
- [ ] record_success/failure update all relevant fields
- [ ] error_counts tracks error types
- [ ] Model serializes to JSON

**Files**: `src/cub/core/tools/models.py`

---

### Task: cub-p9q.2 - Implement MetricsStore

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, logic
Blocks: cub-p9q.3

**Context**: MetricsStore persists and queries tool metrics. Project-level storage in `.cub/tools/metrics.json`.

**Implementation Steps**:
1. Create `src/cub/core/tools/metrics.py` with `MetricsStore` class:
   - `__init__(path)` with default `.cub/tools/metrics.json`
   - `load() -> MetricsRegistry`
   - `save(registry)`
   - `get(tool_id) -> ToolMetrics | None`
   - `record(tool_id, result: ToolResult)` updates metrics based on result
   - `get_degraded(threshold=0.7) -> list[ToolMetrics]` finds tools below threshold
2. Use atomic write pattern
3. Handle missing file (return empty registry)

**Acceptance Criteria**:
- [ ] record() updates metrics from ToolResult
- [ ] get_degraded() returns tools with success_rate < threshold
- [ ] Metrics persisted across calls
- [ ] Atomic writes prevent corruption

**Files**: `src/cub/core/tools/metrics.py`

---

### Task: cub-p9q.3 - Integrate metrics into ExecutionService

Priority: 1
Labels: phase-3, model:sonnet, complexity:low, logic

**Context**: Every tool execution should automatically record metrics for the learning loop.

**Implementation Steps**:
1. Update `ExecutionService.__init__` to accept optional `MetricsStore`
2. Update `execute()` to call `metrics_store.record(tool_id, result)` after execution
3. Add `get_metrics(tool_id) -> ToolMetrics` method
4. Add `get_degraded_tools(threshold) -> list[ToolMetrics]` method

**Acceptance Criteria**:
- [ ] Every execute() call records metrics
- [ ] Metrics recorded for both success and failure
- [ ] get_metrics() returns current tool stats
- [ ] Works with MetricsStore=None (no recording)

**Files**: `src/cub/core/tools/execution.py`

---

### Task: cub-p9q.4 - Add cub tools stats command

Priority: 1
Labels: phase-3, model:sonnet, complexity:low, api

**Context**: CLI command to view tool effectiveness metrics.

**Implementation Steps**:
1. Add `stats` command to `src/cub/cli/tools.py`:
   - `cub tools stats` shows all tools with metrics (table)
   - `cub tools stats <tool_id>` shows detailed metrics for one tool (panel)
   - `cub tools stats --degraded` shows only tools below threshold
   - Include: invocations, success_rate, avg_duration, last_success, last_failure
2. Color-code success_rate (green >80%, yellow 50-80%, red <50%)
3. Show "no metrics yet" for tools without execution history

**Acceptance Criteria**:
- [ ] `cub tools stats` displays metrics table
- [ ] `cub tools stats brave-search` shows detailed panel
- [ ] Success rate color-coded
- [ ] --degraded flag filters appropriately

**Files**: `src/cub/cli/tools.py`

---

### Task: cub-p9q.5 - Add tests for metrics

Priority: 1
Labels: phase-3, model:sonnet, complexity:low, test

**Context**: Test metrics recording, persistence, and degradation detection.

**Implementation Steps**:
1. Add to `tests/test_tools_metrics.py`:
   - Test ToolMetrics model and computed properties
   - Test MetricsStore load/save/record
   - Test get_degraded threshold logic
   - Test integration with ExecutionService
2. Use tmp_path for file operations

**Acceptance Criteria**:
- [ ] All tests pass
- [ ] Coverage >70% for metrics.py
- [ ] Computed properties tested (success_rate, avg_duration)
- [ ] Degradation threshold tested at boundary

**Files**: `tests/test_tools_metrics.py`

---

## Epic: cub-r2v - unified-tool-ecosystem #4: MCP Stdio Adapter

Priority: 1
Labels: phase-4, complexity:high

Execute MCP servers via stdio JSON-RPC. Spawn-per-call model for simplicity.

### Task: cub-r2v.1 - Implement MCPStdioAdapter

Priority: 1
Labels: phase-4, model:opus, complexity:high, logic, risk:medium

**Context**: MCP servers communicate via JSON-RPC over stdio. This adapter spawns the server process, sends a request, reads the response, and kills the process.

**Implementation Steps**:
1. Create `src/cub/core/tools/adapters/mcp_stdio.py` with `MCPStdioAdapter` class:
   - Register with `@register_adapter("mcp_stdio")`
   - `execute()`:
     - Spawn process with `subprocess.Popen(stdin=PIPE, stdout=PIPE, stderr=PIPE)`
     - Send JSON-RPC request to stdin: `{"jsonrpc": "2.0", "method": action, "params": params, "id": 1}`
     - Read response from stdout with timeout
     - Parse JSON-RPC response
     - Kill process (use process group for clean shutdown)
     - Return ToolResult
   - `is_available()` checks command exists via `shutil.which()`
2. Handle timeout: kill process group, return error ToolResult
3. Handle JSON-RPC errors (error field in response)
4. Capture stderr for debugging (don't expose to user)

**Acceptance Criteria**:
- [ ] MCP server spawned and receives JSON-RPC request
- [ ] Response parsed and returned as ToolResult
- [ ] Process killed after response or timeout
- [ ] No zombie processes left behind
- [ ] JSON-RPC errors mapped to ToolResult.error

**Files**: `src/cub/core/tools/adapters/mcp_stdio.py`

---

### Task: cub-r2v.2 - Add JSON-RPC helpers

Priority: 1
Labels: phase-4, model:sonnet, complexity:low, logic

**Context**: JSON-RPC message formatting and parsing extracted to helpers for reuse and testing.

**Implementation Steps**:
1. Create `src/cub/core/tools/jsonrpc.py`:
   - `format_request(method, params, id=1) -> str` creates JSON-RPC request
   - `parse_response(data: str) -> JSONRPCResponse` parses response
   - `JSONRPCResponse` model with result, error, id fields
   - `JSONRPCError` model with code, message, data fields
2. Validate JSON-RPC 2.0 format
3. Handle malformed responses gracefully

**Acceptance Criteria**:
- [ ] format_request produces valid JSON-RPC 2.0
- [ ] parse_response handles success and error responses
- [ ] Malformed JSON raises clear error
- [ ] Missing required fields detected

**Files**: `src/cub/core/tools/jsonrpc.py`

---

### Task: cub-r2v.3 - Add process management utilities

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, logic

**Context**: Safe process spawning with timeout and cleanup. Use process groups to ensure all child processes are killed.

**Implementation Steps**:
1. Create `src/cub/core/tools/process.py`:
   - `spawn_process(cmd, args, env, timeout) -> ProcessHandle`
   - `ProcessHandle` class with stdin, stdout, stderr, pid
   - `ProcessHandle.write(data)` sends to stdin
   - `ProcessHandle.read(timeout) -> str` reads from stdout with timeout
   - `ProcessHandle.kill()` kills process group
   - Use `os.setpgrp()` / `os.killpg()` for process group management
2. Handle platform differences (Windows vs Unix process groups)

**Acceptance Criteria**:
- [ ] Process spawned in new process group
- [ ] read() respects timeout
- [ ] kill() terminates entire process group
- [ ] No zombie processes after kill
- [ ] Works on macOS/Linux (Windows can be deferred)

**Files**: `src/cub/core/tools/process.py`

---

### Task: cub-r2v.4 - Add tests for MCP adapter

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, test

**Context**: Test MCP adapter with mock server process. Verify JSON-RPC handling and process lifecycle.

**Implementation Steps**:
1. Create `tests/test_tools_mcp.py`:
   - Create simple mock MCP server script (Python script that reads stdin, writes stdout)
   - Test successful request/response
   - Test timeout handling
   - Test JSON-RPC error response
   - Test process cleanup (no zombies)
2. Create `tests/test_tools_jsonrpc.py`:
   - Test request formatting
   - Test response parsing
   - Test error handling
3. Use subprocess to run mock server

**Acceptance Criteria**:
- [ ] All tests pass
- [ ] Mock server exercises full JSON-RPC flow
- [ ] Timeout test verifies process killed
- [ ] No zombie processes after test suite

**Files**: `tests/test_tools_mcp.py`, `tests/test_tools_jsonrpc.py`, `tests/fixtures/mock_mcp_server.py`

---

## Epic: cub-t5w - unified-tool-ecosystem #5: Lifecycle Integration

Priority: 2
Labels: phase-5, complexity:medium

Wire tools into cub's broader ecosystem - hooks, workbench, freedom dial.

### Task: cub-t5w.1 - Add capability gap recognition API

Priority: 2
Labels: phase-5, model:sonnet, complexity:medium, logic

**Context**: Enable agents to query for tools by capability. Returns adopted tools or suggests adoption.

**Implementation Steps**:
1. Add to `src/cub/core/tools/registry.py`:
   - `find_capability(capability: str) -> CapabilityResult`
   - `CapabilityResult` model:
     - `available: list[ToolConfig]` - adopted tools with capability
     - `suggested: list[Tool]` - catalog tools that could be adopted
     - `has_tool: bool` - True if any available
2. Search both registry and catalog
3. Rank suggestions by relevance (exact match > partial match)

**Acceptance Criteria**:
- [ ] find_capability("web_search") returns adopted tools first
- [ ] If no adopted tools, suggests from catalog
- [ ] has_tool is True when adopted tool exists
- [ ] Empty result when no matches anywhere

**Files**: `src/cub/core/tools/registry.py`, `src/cub/core/tools/models.py`

---

### Task: cub-t5w.2 - Implement freedom dial configuration

Priority: 2
Labels: phase-5, model:sonnet, complexity:medium, logic

**Context**: Freedom dial controls autonomy level for tool execution. Stored in user config.

**Implementation Steps**:
1. Add `FreedomLevel` enum to models: low, medium, high
2. Add `ToolApprovals` model:
   - `level: FreedomLevel`
   - `approved_tools: dict[str, ToolApproval]`
   - `ToolApproval`: tool_id, approved_at, version_hash, level
3. Create `src/cub/core/tools/approvals.py`:
   - `ApprovalsStore` loads/saves `~/.config/cub/tool-approvals.json`
   - `check_approval(tool_id, level) -> bool`
   - `grant_approval(tool_id, level)`
   - `revoke_approval(tool_id)`
4. Update ExecutionService to check approval based on freedom level

**Acceptance Criteria**:
- [ ] Freedom level configurable per-user
- [ ] Tools can be approved at specific levels
- [ ] Execution respects freedom dial setting
- [ ] Version hash change triggers re-approval check

**Files**: `src/cub/core/tools/approvals.py`, `src/cub/core/tools/models.py`

---

### Task: cub-t5w.3 - Integrate tools with workbench

Priority: 2
Labels: phase-5, model:sonnet, complexity:medium, logic

**Context**: Workbench's run-next should use the new tool execution system instead of hardcoded brave-search.

**Implementation Steps**:
1. Update `src/cub/cli/workbench.py` (if exists on feature/toolsmith):
   - Replace direct brave-search calls with ExecutionService
   - Use find_capability("web_search") to get tool
   - Pass execution result to workbench note generation
2. If workbench doesn't exist yet, document integration point
3. Ensure ToolResult.output_markdown used for notes

**Acceptance Criteria**:
- [ ] Workbench uses ExecutionService for tool calls
- [ ] Tool selected by capability, not hardcoded
- [ ] Execution metrics recorded for workbench runs
- [ ] Graceful fallback if no web_search tool adopted

**Files**: `src/cub/cli/workbench.py`

---

### Task: cub-t5w.4 - Add cub tools configure command

Priority: 2
Labels: phase-5, model:sonnet, complexity:low, api

**Context**: CLI command to configure freedom dial and manage approvals.

**Implementation Steps**:
1. Add to `src/cub/cli/tools.py`:
   - `configure` command group
   - `cub tools configure freedom <level>` sets freedom dial
   - `cub tools configure show` shows current settings
   - `cub tools configure approve <tool_id>` grants approval
   - `cub tools configure revoke <tool_id>` revokes approval
2. Show current freedom level and approved tools

**Acceptance Criteria**:
- [ ] `cub tools configure freedom high` updates setting
- [ ] `cub tools configure show` displays current config
- [ ] Approval/revoke commands work
- [ ] Changes persisted to user config

**Files**: `src/cub/cli/tools.py`

---

### Task: cub-t5w.5 - Add integration tests

Priority: 2
Labels: phase-5, model:sonnet, complexity:medium, test, checkpoint

**Context**: End-to-end tests verifying the complete flow: discover → adopt → execute → learn.

**Implementation Steps**:
1. Create `tests/test_tools_integration.py`:
   - Test full flow with mock HTTP tool:
     1. Search catalog for tool
     2. Adopt tool to registry
     3. Execute tool
     4. Verify metrics recorded
     5. Query by capability
   - Test freedom dial enforcement
   - Test degraded tool detection after failures
2. Use fixtures for mock services
3. Use tmp_path for all file operations

**Acceptance Criteria**:
- [ ] Full discover → adopt → execute → learn flow tested
- [ ] Freedom dial blocks execution when not approved
- [ ] Metrics accumulate across executions
- [ ] Capability search returns adopted tools

**Files**: `tests/test_tools_integration.py`

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-x7f | 6 | P0 | Execution Runtime Foundation - adapter pattern, HTTP/CLI adapters |
| cub-m3k | 7 | P0 | Registry and Adoption - JSON registry, adoption workflow, CLI |
| cub-p9q | 5 | P1 | Learning Loop - metrics tracking, degradation detection |
| cub-r2v | 4 | P1 | MCP Stdio Adapter - JSON-RPC, process management |
| cub-t5w | 5 | P2 | Lifecycle Integration - freedom dial, workbench, capability API |

**Total**: 5 epics, 27 tasks

**Checkpoints**:
- After cub-x7f: Can execute tools via HTTP and CLI adapters
- After cub-m3k: Full adopt → execute flow working with CLI
- After cub-p9q: Tool effectiveness tracked and visible
- After cub-r2v: MCP servers can be executed
- After cub-t5w: Complete ecosystem integrated

**Ready to start immediately**: cub-x7f.1 (no dependencies)

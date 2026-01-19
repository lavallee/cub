---
status: researching
priority: critical
complexity: high
dependencies: []
blocks:
  - multi-model-review.md
  - tools-registry.md
  - workflow-management.md
  - toolsmith.md
created: 2026-01-19
updated: 2026-01-19
readiness:
  score: 6
  blockers:
    - Need to finalize interface design
    - Hook system needs definition
    - Provider authentication patterns unclear
  questions:
    - How to handle provider-specific features (Claude SDK hooks)?
    - Should hooks be opt-in or always available?
    - How to abstract streaming vs non-streaming?
    - What's the minimal common interface?
  decisions_needed:
    - Define core Harness interface (methods, signatures)
    - Design hook system (event types, registration, execution)
    - Choose authentication approach per provider
    - Decide on sync vs async API
  tools_needed:
    - API Design Validator (design harness interface)
    - Competitive Analysis Tool (how OpenCode, others abstract providers)
    - Design Pattern Matcher (provider abstraction patterns)
    - Trade-off Analyzer (sync vs async, minimal vs rich interface)
notes: |
  Critical missing piece for multi-LLM support.
  Claude harness uses Agent SDK with special abilities (hooks, custom tools).
  Other harnesses use appropriate SDKs or shell-out.
  Design must support both simple and advanced use cases.
---

# Harness Abstraction: Multi-Provider LLM Interface

## Overview

A unified abstraction layer for interacting with different LLM providers (Claude, OpenAI, Gemini, etc), enabling cub to support multiple models while leveraging provider-specific capabilities when available.

**Core principle:** "Reasonable support for a variety of harnesses but special abilities when running Claude Code."

**Design influenced by:** Claude Agent SDK capabilities, OpenCode's provider system

## Problem Statement

Currently, cub is tightly coupled to Claude via shell-out. To support:
- **Multi-model review** (different LLMs review same work)
- **Model flexibility** (users choose preferred LLM)
- **Cost optimization** (use cheaper models for simple tasks)
- **Provider-specific features** (Claude SDK hooks, OpenAI function calling)

We need a harness abstraction that:
1. Provides common interface across providers
2. Allows provider-specific extensions
3. Supports both SDK-based and shell-out approaches
4. Enables features like circuit-breaker via hooks

## Goals

1. **Unified interface** - Single API for cub to interact with any LLM
2. **Provider flexibility** - Easy to add new providers
3. **Special abilities** - Claude harness leverages SDK for hooks, custom tools
4. **Graceful degradation** - Features work across providers when possible, degrade gracefully when not
5. **Simple common path** - Basic use case (run a task) is simple for all providers
6. **Advanced when needed** - Circuit-breaker, guardrails can use provider-specific features

## Non-Goals (v1)

- Perfect feature parity across providers (accept that Claude will have advantages)
- Supporting every possible LLM (start with top 3-4)
- Building SDKs for providers that don't have them
- Complex dependency resolution between harnesses

---

## Architecture

### Core Abstraction

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Optional, Any
from enum import Enum

class HookEvent(Enum):
    """Events where hooks can intercede"""
    PRE_TASK = "pre_task"              # Before task starts
    POST_TASK = "post_task"            # After task completes
    PRE_TOOL_USE = "pre_tool_use"      # Before any tool execution
    POST_TOOL_USE = "post_tool_use"    # After tool execution
    ON_ERROR = "on_error"              # On task failure
    ON_ITERATION = "on_iteration"      # Each agent loop iteration
    ON_MESSAGE = "on_message"          # Each message from LLM

@dataclass
class Task:
    """A task to be executed by the harness"""
    prompt: str
    context: dict[str, Any] = None
    working_dir: str = None
    max_iterations: int = 100
    timeout_seconds: int = None
    
    # Permission model
    auto_approve_edits: bool = False
    auto_approve_bash: bool = False
    
    # Task metadata
    task_id: str = None
    epic_id: str = None

@dataclass
class ToolUse:
    """A tool invocation"""
    tool_id: str
    tool_name: str
    input_data: dict[str, Any]
    context: dict[str, Any]

@dataclass
class ToolResult:
    """Result of tool execution"""
    tool_id: str
    output: Any
    error: Optional[str] = None
    permission_decision: Optional[str] = None  # allow, deny, ask

@dataclass
class Message:
    """A message from the LLM"""
    role: str  # assistant, tool_result, etc
    content: str
    tool_uses: list[ToolUse] = None
    metadata: dict[str, Any] = None

@dataclass
class TaskResult:
    """Result of a completed task"""
    success: bool
    messages: list[Message]
    final_output: str
    error: Optional[str] = None
    metadata: dict[str, Any] = None  # stats, tokens, cost, etc
    
    # File tracking
    files_changed: list[str] = None
    files_created: list[str] = None

class Harness(ABC):
    """Abstract base class for all LLM harnesses"""
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.hooks: dict[HookEvent, list[Callable]] = {
            event: [] for event in HookEvent
        }
    
    # === Core Methods (Required) ===
    
    @abstractmethod
    async def run_task(self, task: Task) -> TaskResult:
        """Execute a task and return the result"""
        pass
    
    @abstractmethod
    async def stream_task(self, task: Task) -> AsyncIterator[Message]:
        """Execute a task and stream messages as they arrive"""
        pass
    
    @abstractmethod
    def supports_feature(self, feature: str) -> bool:
        """Check if this harness supports a given feature"""
        pass
    
    # === Hook System (Optional but recommended) ===
    
    def register_hook(self, event: HookEvent, handler: Callable):
        """Register a hook for an event"""
        self.hooks[event].append(handler)
    
    async def execute_hooks(self, event: HookEvent, **kwargs) -> dict[str, Any]:
        """Execute all hooks for an event, return aggregated results"""
        results = {}
        for hook in self.hooks[event]:
            result = await hook(**kwargs)
            if result:
                results.update(result)
        return results
    
    # === Custom Tools (Optional) ===
    
    def register_tool(self, tool_def: dict):
        """Register a custom tool (MCP-style)"""
        raise NotImplementedError("This harness doesn't support custom tools")
    
    # === Session Management (Optional) ===
    
    def create_session(self, session_id: str = None) -> str:
        """Create a new session, return session ID"""
        raise NotImplementedError("This harness doesn't support sessions")
    
    def fork_session(self, session_id: str) -> str:
        """Fork an existing session"""
        raise NotImplementedError("This harness doesn't support session forking")
```

### Feature Flags

```python
class HarnessFeature:
    """Standard feature flags"""
    HOOKS = "hooks"                      # Pre/post tool use hooks
    CUSTOM_TOOLS = "custom_tools"        # In-process custom tools (MCP)
    STREAMING = "streaming"              # Message streaming
    SESSIONS = "sessions"                # Session management
    SESSION_FORKING = "session_forking"  # Can fork sessions
    SUBAGENTS = "subagents"             # Supports spawning subagents
    COST_TRACKING = "cost_tracking"     # Tracks token costs
    FILE_TRACKING = "file_tracking"     # Tracks file changes
```

---

## Implementation: Claude Harness

Leverages Claude Agent SDK for full capabilities:

```python
from claude_agent_sdk import query, ClaudeAgentOptions, create_sdk_mcp_server
from claude_agent_sdk.hooks import HookContext

class ClaudeHarness(Harness):
    """Harness for Claude via Agent SDK"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("ANTHROPIC_API_KEY")
        self.model = config.get("model", "claude-sonnet-4")
        self.custom_tools = []
    
    def supports_feature(self, feature: str) -> bool:
        """Claude supports all features"""
        return feature in [
            HarnessFeature.HOOKS,
            HarnessFeature.CUSTOM_TOOLS,
            HarnessFeature.STREAMING,
            HarnessFeature.SESSIONS,
            HarnessFeature.SESSION_FORKING,
            HarnessFeature.SUBAGENTS,
            HarnessFeature.COST_TRACKING,
            HarnessFeature.FILE_TRACKING,
        ]
    
    async def run_task(self, task: Task) -> TaskResult:
        """Run task using Claude Agent SDK"""
        
        # Execute pre-task hooks
        pre_results = await self.execute_hooks(
            HookEvent.PRE_TASK,
            task=task
        )
        
        # Check if hooks blocked the task
        if pre_results.get("block"):
            return TaskResult(
                success=False,
                messages=[],
                final_output="",
                error=pre_results.get("reason", "Task blocked by hook")
            )
        
        # Build SDK options
        options = ClaudeAgentOptions(
            api_key=self.api_key,
            model=self.model,
            working_directory=task.working_dir,
            permissions={
                "acceptEdits": task.auto_approve_edits,
                "acceptBash": task.auto_approve_bash,
            }
        )
        
        # Register custom tools as MCP server
        if self.custom_tools:
            mcp_server = create_sdk_mcp_server(tools=self.custom_tools)
            options.mcp_servers = [mcp_server]
        
        # Setup hooks for SDK
        if self.hooks[HookEvent.PRE_TOOL_USE]:
            options.hooks = {
                "PreToolUse": self._make_pre_tool_use_hook()
            }
        
        # Run the task
        messages = []
        try:
            async for message in query(
                prompt=task.prompt,
                options=options
            ):
                messages.append(Message(
                    role=message.get("role"),
                    content=message.get("content", ""),
                    metadata=message
                ))
                
                # Execute on-message hooks
                await self.execute_hooks(
                    HookEvent.ON_MESSAGE,
                    message=message,
                    task=task
                )
        
        except Exception as e:
            # Execute error hooks
            await self.execute_hooks(
                HookEvent.ON_ERROR,
                error=e,
                task=task
            )
            
            return TaskResult(
                success=False,
                messages=messages,
                final_output="",
                error=str(e)
            )
        
        # Execute post-task hooks
        await self.execute_hooks(
            HookEvent.POST_TASK,
            task=task,
            result=messages
        )
        
        # Extract final output
        final_output = messages[-1].content if messages else ""
        
        return TaskResult(
            success=True,
            messages=messages,
            final_output=final_output,
            metadata=self._extract_metadata(messages)
        )
    
    async def stream_task(self, task: Task) -> AsyncIterator[Message]:
        """Stream task execution"""
        options = ClaudeAgentOptions(
            api_key=self.api_key,
            model=self.model,
            working_directory=task.working_dir,
        )
        
        async for message in query(prompt=task.prompt, options=options):
            yield Message(
                role=message.get("role"),
                content=message.get("content", ""),
                metadata=message
            )
    
    def _make_pre_tool_use_hook(self):
        """Create PreToolUse hook for SDK from registered hooks"""
        async def pre_tool_use_hook(input_data, tool_use_id, context):
            tool_use = ToolUse(
                tool_id=tool_use_id,
                tool_name=input_data.get("tool_name"),
                input_data=input_data.get("tool_input", {}),
                context=context
            )
            
            # Execute our hooks
            results = await self.execute_hooks(
                HookEvent.PRE_TOOL_USE,
                tool_use=tool_use
            )
            
            # Convert to SDK format
            if results.get("deny"):
                return {
                    "permissionDecision": "deny",
                    "permissionDecisionReason": results.get("reason")
                }
            
            return None  # Allow
        
        return pre_tool_use_hook
    
    def register_tool(self, tool_def: dict):
        """Register custom MCP tool"""
        self.custom_tools.append(tool_def)
    
    def _extract_metadata(self, messages: list[Message]) -> dict:
        """Extract metadata like token usage, cost"""
        # Parse from SDK messages
        return {
            "provider": "claude",
            "model": self.model,
            # TODO: Extract tokens, cost from messages
        }
```

---

## Implementation: OpenAI Harness

Uses OpenAI SDK or unofficial agent wrapper:

```python
from openai import AsyncOpenAI

class OpenAIHarness(Harness):
    """Harness for OpenAI models"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=config.get("api_key") or os.getenv("OPENAI_API_KEY")
        )
        self.model = config.get("model", "gpt-4")
    
    def supports_feature(self, feature: str) -> bool:
        """OpenAI has limited features compared to Claude SDK"""
        return feature in [
            HarnessFeature.STREAMING,
            HarnessFeature.COST_TRACKING,
        ]
    
    async def run_task(self, task: Task) -> TaskResult:
        """Run task via OpenAI API"""
        
        # Execute pre-task hooks (best effort)
        await self.execute_hooks(HookEvent.PRE_TASK, task=task)
        
        messages = []
        
        try:
            # Simple completion (no agentic loop built-in)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": task.prompt}
                ],
                stream=False
            )
            
            message = Message(
                role="assistant",
                content=response.choices[0].message.content,
                metadata={
                    "usage": response.usage,
                    "model": response.model
                }
            )
            messages.append(message)
            
        except Exception as e:
            await self.execute_hooks(HookEvent.ON_ERROR, error=e, task=task)
            return TaskResult(
                success=False,
                messages=[],
                final_output="",
                error=str(e)
            )
        
        await self.execute_hooks(HookEvent.POST_TASK, task=task, result=messages)
        
        return TaskResult(
            success=True,
            messages=messages,
            final_output=message.content,
            metadata=self._extract_metadata(response)
        )
    
    async def stream_task(self, task: Task) -> AsyncIterator[Message]:
        """Stream via OpenAI API"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": task.prompt}],
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield Message(
                    role="assistant",
                    content=chunk.choices[0].delta.content
                )
    
    def _extract_metadata(self, response) -> dict:
        return {
            "provider": "openai",
            "model": self.model,
            "tokens_used": response.usage.total_tokens if response.usage else None,
            "cost": self._calculate_cost(response.usage) if response.usage else None
        }
```

---

## Implementation: Shell-Out Harness

For providers without SDKs, or as fallback:

```python
import subprocess
import json

class ShellHarness(Harness):
    """Generic shell-out harness for any CLI"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.command = config["command"]  # e.g., ["claude", "run"]
        self.args = config.get("args", [])
    
    def supports_feature(self, feature: str) -> bool:
        """Shell-out has minimal features"""
        return feature in []  # No special features
    
    async def run_task(self, task: Task) -> TaskResult:
        """Run via subprocess"""
        
        await self.execute_hooks(HookEvent.PRE_TASK, task=task)
        
        # Build command
        cmd = [*self.command, *self.args, task.prompt]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=task.working_dir,
                capture_output=True,
                text=True,
                timeout=task.timeout_seconds
            )
            
            message = Message(
                role="assistant",
                content=result.stdout
            )
            
            await self.execute_hooks(
                HookEvent.POST_TASK,
                task=task,
                result=[message]
            )
            
            return TaskResult(
                success=result.returncode == 0,
                messages=[message],
                final_output=result.stdout,
                error=result.stderr if result.returncode != 0 else None
            )
            
        except Exception as e:
            await self.execute_hooks(HookEvent.ON_ERROR, error=e, task=task)
            return TaskResult(
                success=False,
                messages=[],
                final_output="",
                error=str(e)
            )
    
    async def stream_task(self, task: Task) -> AsyncIterator[Message]:
        """Stream not supported via shell-out"""
        result = await self.run_task(task)
        yield result.messages[0]
```

---

## Configuration

Multi-provider config inspired by OpenCode:

```yaml
# .cub/config.yaml
harnesses:
  # Default harness to use
  default: claude
  
  # Provider configurations
  claude:
    type: claude_sdk
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-sonnet-4
    features:
      hooks: true
      custom_tools: true
      sessions: true
  
  openai:
    type: openai_sdk
    api_key: ${OPENAI_API_KEY}
    model: gpt-4
  
  gemini:
    type: shell_out
    command: [gemini, chat]
    model: gemini-2.0-flash
  
  local:
    type: shell_out
    command: [ollama, run]
    model: codellama

# Agent-specific harness overrides
agents:
  architect:
    harness: claude      # Use Claude for architecture
    model: claude-sonnet-4
  
  coder:
    harness: claude      # Use Claude for coding
    model: claude-sonnet-4
  
  reviewer:
    harness: openai      # Use GPT-4 for review
    model: gpt-4
```

---

## Usage in Cub

### Simple Case (Transparent)

```python
# Cub code doesn't care which harness
harness = get_harness()  # Returns configured default
result = await harness.run_task(Task(
    prompt="Implement login feature",
    working_dir=project.path
))
```

### Advanced Case (Circuit Breaker)

```python
# Circuit breaker hook (works on Claude, degrades elsewhere)
async def check_stagnation(tool_use: ToolUse, **kwargs):
    """Block if same bash command run 3+ times"""
    if tool_use.tool_name == "bash":
        command = tool_use.input_data.get("command")
        if stagnation_detector.is_looping(command):
            return {
                "deny": True,
                "reason": "Circuit breaker: Same command repeated 3 times"
            }
    return None

# Register hook
harness = get_harness("claude")
if harness.supports_feature(HarnessFeature.HOOKS):
    harness.register_hook(HookEvent.PRE_TOOL_USE, check_stagnation)
else:
    logger.warning("Circuit breaker not supported on this harness")

# Run task (circuit breaker active if supported)
result = await harness.run_task(task)
```

### Multi-Model Review

```python
# Review with multiple models
harnesses = [
    get_harness("claude"),
    get_harness("openai"),
    get_harness("gemini")
]

reviews = []
for harness in harnesses:
    result = await harness.run_task(Task(
        prompt=f"Review this code:\n{code}",
    ))
    reviews.append({
        "provider": harness.config["type"],
        "review": result.final_output
    })

# Aggregate reviews
consensus = analyze_reviews(reviews)
```

---

## Integration with Other Specs

### Circuit Breaker

Uses `PRE_TOOL_USE` hooks when available:

```python
harness.register_hook(HookEvent.PRE_TOOL_USE, circuit_breaker_check)
```

Fallback: Parse output and abort externally (less elegant, but works)

### Guardrails

Uses `PRE_TASK` hooks to inject guardrails:

```python
async def inject_guardrails(task: Task, **kwargs):
    guardrails = load_guardrails()
    task.prompt = f"{guardrails}\n\n{task.prompt}"
    return None

harness.register_hook(HookEvent.PRE_TASK, inject_guardrails)
```

### Receipt-Based Gating

Uses `POST_TOOL_USE` hooks to require receipts:

```python
async def require_receipt(tool_use: ToolUse, **kwargs):
    if tool_use.tool_name == "bash":
        # Check for receipt in output
        # Block next tool if no receipt
        pass
```

### Tools Registry

Harnesses with `CUSTOM_TOOLS` feature can register tools:

```python
if harness.supports_feature(HarnessFeature.CUSTOM_TOOLS):
    for tool in tools_registry.get_custom_tools():
        harness.register_tool(tool)
```

Harnesses without this feature use external tools only

### Toolsmith

Harness selection can be a discovery criterion:

```python
# Toolsmith finds a tool that needs Claude SDK hooks
if tool.requires == "hooks":
    if not get_harness().supports_feature(HarnessFeature.HOOKS):
        logger.warning("Tool requires hooks, but current harness doesn't support them")
```

---

## Harness Selection Strategy

```python
class HarnessSelector:
    """Select appropriate harness based on task needs"""
    
    def select(self, task: Task, requirements: list[str] = None) -> Harness:
        """Select harness based on requirements"""
        
        # Default: Use configured default
        if not requirements:
            return get_harness()
        
        # Find harness that meets requirements
        for harness_id in config.harnesses:
            harness = get_harness(harness_id)
            if all(harness.supports_feature(req) for req in requirements):
                return harness
        
        # No harness meets all requirements
        logger.warning(
            f"No harness supports all requirements: {requirements}. "
            f"Using default with degraded functionality."
        )
        return get_harness()

# Usage
selector = HarnessSelector()

# Task needs hooks for circuit breaker
harness = selector.select(
    task=task,
    requirements=[HarnessFeature.HOOKS]
)
```

---

## Implementation Phases

### Phase 1: Core Abstraction (Weeks 1-2)
- Define `Harness` interface
- Implement `ClaudeHarness` with SDK
- Implement `ShellHarness` as fallback
- Basic feature detection

### Phase 2: Hooks & Features (Weeks 3-4)
- Hook system implementation
- Circuit breaker via hooks
- Guardrails integration
- Receipt-based gating

### Phase 3: Additional Providers (Weeks 5-6)
- `OpenAIHarness` implementation
- `GeminiHarness` (shell or SDK if available)
- Provider selection logic
- Config-based switching

### Phase 4: Advanced Features (Weeks 7-8)
- Custom tools registration
- Multi-model workflows
- Cost tracking
- Performance metrics

---

## Open Questions

1. **Async vs Sync:** Should interface be async-only, or support both?
   - **Recommendation:** Async-only (modern Python, better for streaming)

2. **Hook execution order:** What if multiple hooks for same event?
   - **Recommendation:** Execute in registration order, allow early exit

3. **Feature negotiation:** Should harness propose alternatives when feature unavailable?
   - **Example:** No hooks → suggest external monitoring
   - **Recommendation:** Log warning, degrade gracefully

4. **Unofficial SDKs:** Use community OpenAI agent wrappers or build our own?
   - **Recommendation:** Start with simple API calls, add wrapper later if needed

5. **Cost tracking:** Standardize cost calculation across providers?
   - **Recommendation:** Yes, but metadata format can vary per provider

---

## Success Metrics

```yaml
metrics:
  abstraction_quality:
    providers_supported: 4  # Claude, OpenAI, Gemini, local
    features_work_across_providers: 80%  # Most features available everywhere
    provider_specific_features_used: 100%  # Special abilities utilized
  
  developer_experience:
    lines_to_add_provider: <200  # Easy to add new providers
    config_complexity: simple  # YAML-based, clear
  
  performance:
    overhead_vs_direct_sdk: <5%  # Minimal abstraction cost
```

---

## Future Enhancements

- **Provider auto-selection** - Choose best provider per task type
- **Cost optimization** - Use cheaper models for simple tasks
- **Fallback chains** - Try primary, fall back to secondary if failed
- **A/B testing** - Run same task on multiple providers, compare
- **Provider health** - Monitor rate limits, errors, switch if degraded

---

**Related:**
- `tools-registry.md` - Custom tools via harness
- `workflow-management.md` - Workflows use harness abstraction
- `multi-model-review.md` - Multiple harnesses for review
- `circuit-breaker.md` - Uses harness hooks
- `guardrails-system.md` - Injected via harness hooks

**Status:** Researching (score 6/10)
- Interface mostly defined, needs validation
- Hook system needs refinement
- OpenAI harness needs real implementation (not just stub)

**Next Steps:**
1. Validate interface design with team
2. Implement Claude harness first (using SDK)
3. Build simple OpenAI harness
4. Test circuit breaker via hooks
5. Document provider addition process

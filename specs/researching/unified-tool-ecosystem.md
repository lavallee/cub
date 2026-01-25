---
status: researching
priority: high
complexity: high
dependencies:
  - harness-abstraction
  - hooks-system
  - layered-config
created: 2026-01-24
updated: 2026-01-24
readiness:
  score: 7
  blockers:
    - Generic execution runtime (especially MCP stdio) is critical path
  questions:
    - MCP launch strategy (stdio vs HTTP, supervision model)?
    - Exact registry file structure (discover during build)?
    - Tool generation budget/guardrails (500k token starting point)?
    - API surface design for future UI?
  decisions_needed:
    - Finalize MCP supervision approach during implementation
    - Define tool generation complexity thresholds
  tools_needed: []
consolidates:
  - specs/researching/toolsmith.md
  - specs/researching/tools-registry.md
  - specs/researching/tool-marketplace.md
  - specs/planned/tool-lifecycle-mvp.md
  - specs/researching/pm-workbench.md (tool-use aspects)
notes: |
  This spec synthesizes five overlapping specs into a single coherent vision.
  Existing implementation on feature/toolsmith provides foundation:
  - Catalog sync from Smithery, Glama, SkillsMP, ClawdHub
  - SQLite persistence, CLI (sync/search/stats)
  - Experimental HTTP execution (brave-search)
  - Workbench sessions (start/run-next)
---

# Unified Tool Ecosystem

## Overview

A coherent system for cub to discover, adopt, build, and execute tools across its entire lifecycle — from capture/triage to release. Cub can self-discover capability gaps, find or generate tools to fill them, and wire tools into hooks and workflows. Humans approve once (auth, budget), then tools run autonomously within a configurable freedom dial.

**Key insight:** Tools are infrastructure for extensibility. Users describe intent ("email me when the epic finishes"), cub figures out the toolchain (discover email tool → adopt → register as hook → run automatically).

## Goals

1. **Unified lifecycle**: Discover → Adopt → Install → Execute → Learn (one coherent flow)
2. **Self-discovery**: Cub recognizes capability gaps and unblocks itself
3. **Multi-source catalog**: External (MCP, Smithery, etc.) + cub-native + self-generated
4. **Generic execution runtime**: HTTP, CLI, MCP stdio adapters
5. **Registry as source of truth**: Capabilities, auth requirements, trust scores
6. **Permissive autonomy**: Approve once, run forever (with freedom dial)
7. **Tool generation with guardrails**: Build simple tools within token budget, escalate complexity
8. **Lifecycle-wide availability**: Tools power capture, triage, workflows, hooks, workbench
9. **Cross-project sharing**: Package what works for reuse (full marketplace deferred)

## Non-Goals (v1)

- **Multi-agent orchestration** — tools run in single-agent context (swarm is separate)
- **Complex dependency resolution** — escalate to human when complexity exceeds threshold
- **Paid tools/marketplace** — all tools free/open source for v1
- **Tool versioning/upgrades** — punt to package managers
- **Visual UI** — CLI-first, but design API with future UI in mind
- **Enterprise features** — SSO, audit logs, team permissions are later

## Architecture

### Five-Layer Model

```
┌─────────────────────────────────────────────────────────────┐
│  5. CONSUMERS (Lifecycle-wide)                              │
│     - Capture/Triage: research tools, feasibility checks    │
│     - Workflows: multi-tool orchestration                   │
│     - Hooks: dynamic tool-as-hook registration              │
│     - Workbench: PM research, next-move suggestions         │
│     - Agents: tool invocation during task execution         │
├─────────────────────────────────────────────────────────────┤
│  4. EXECUTION RUNTIME (Critical Path)                       │
│     - HTTP adapter (implemented: brave-search)              │
│     - CLI adapter (subprocess with allowlist)               │
│     - MCP stdio adapter (strategic priority)                │
│     - Clawdbot skill bridge (when hosted)                   │
├─────────────────────────────────────────────────────────────┤
│  3. REGISTRY (Source of Truth)                              │
│     - User registry: ~/.config/cub/tools/                   │
│     - Project registry: .cub/tools/                         │
│     - Capabilities (tags), auth requirements, trust scores  │
│     - What cub CAN run + how to invoke it                   │
├─────────────────────────────────────────────────────────────┤
│  2. ADOPTION (Toolsmith → Registry Pipeline)                │
│     - Propose registry entries from discovered tools        │
│     - Human handoff for auth/budget (once per tool)         │
│     - Track adoption decisions + rationale                  │
│     - Tool generation when discovery fails (with budget)    │
├─────────────────────────────────────────────────────────────┤
│  1. DISCOVERY (Toolsmith Catalog)                           │
│     - Multi-source sync (Smithery, Glama, SkillsMP, etc.)   │
│     - Source-level trust scores (Anthropic=9, random GH=4)  │
│     - Crowd signals for tiebreakers (stars, downloads)      │
│     - Capability gap recognition ("I need X to proceed")    │
└─────────────────────────────────────────────────────────────┘
```

### Tool Acquisition Hierarchy

When cub needs a capability:

1. **Discover** — find an existing tool in catalog (cheapest)
2. **Compose** — assemble from building blocks (medium cost)
3. **Generate** — build a simple tool from scratch (bounded by token budget)
4. **Escalate** — "this is too big, needs human involvement"

### Build vs Buy Decision Matrix

```
                    COMMONALITY
                 Low          High
              ┌───────────┬───────────┐
         Low  │  BUILD    │  EITHER   │
COMPLEXITY    │ (simple   │ (evaluate │
              │  unique)  │  options) │
              ├───────────┼───────────┤
         High │  ESCALATE │   BUY     │
              │ (too      │ (complex  │
              │  custom)  │  common)  │
              └───────────┴───────────┘
```

## Key Decisions

### Resolved

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Registry format | JSON | Consistency with existing config |
| Registry location | `~/.config/cub/tools/` + `.cub/tools/` | User + project level |
| Credentials | Env-only for now | Simpler, secure enough |
| Capability taxonomy | Tags (free-form) | Can evolve, low friction |
| Trust model | Source-level scores + crowd signals | Anthropic=9, random GH=4, then stars/downloads |
| Learning loop | LLM self-judges | "Did this help me get unstuck?" |
| Sharing scope | Cross-project for same user | Full marketplace deferred |
| Autonomy model | Permissive with freedom dial | Approve once, run forever |

### Open (Emerge During Build)

| Decision | Options | Notes |
|----------|---------|-------|
| MCP launch | stdio vs HTTP | Implementation will inform |
| Registry structure | Single file vs multiple | Discover as complexity grows |
| Generation budget | 500k tokens starting point | May need adjustment |
| API surface | TBD | Design for future UI |

## Autonomy Configuration

```yaml
# .cub/config.yaml or ~/.config/cub/config.yaml
autonomy:
  level: high  # low | medium | high

  # Capabilities that always require approval
  require_approval:
    - sudo
    - paid_apis
    - install_system_packages

  # Tool generation limits
  generation:
    max_tokens: 500000
    escalate_on_external_dependency: true
```

**Freedom dial semantics:**
- **low**: Approve each tool invocation
- **medium**: Approve first use per session
- **high**: Approve once, run forever (default)

## Registry Schema (v1)

```json
{
  "version": "1.0",
  "tools": {
    "brave-search": {
      "name": "Brave Search",
      "source": "smithery",
      "source_url": "https://smithery.ai/tools/brave-search",
      "trust_score": 8,
      "type": "http",
      "capabilities": ["web_search", "current_events"],
      "auth": {
        "required": true,
        "env_var": "BRAVE_API_KEY",
        "signup_url": "https://brave.com/search/api/"
      },
      "execution": {
        "adapter": "http",
        "base_url": "https://api.search.brave.com/res/v1",
        "endpoints": {
          "search": "/web/search"
        }
      },
      "adopted_at": "2026-01-24T12:00:00Z",
      "last_used": "2026-01-24T15:30:00Z",
      "success_rate": 0.95,
      "notes": "Good for current events, rate limited to 100/day on free tier"
    }
  }
}
```

## Execution Runtime

### Adapters

Each adapter implements a common interface:

```python
class ToolAdapter(Protocol):
    async def execute(
        self,
        tool_id: str,
        action: str,
        params: dict[str, Any],
        timeout: float = 30.0
    ) -> ToolResult:
        """Execute a tool action and return structured result."""
        ...

    async def is_available(self, tool_id: str) -> bool:
        """Check if tool is ready to execute."""
        ...
```

**Adapters to implement:**

1. **HTTP** (exists) — REST API calls with auth headers
2. **CLI** — subprocess execution with output capture
3. **MCP stdio** — launch server, call method, capture result
4. **Skill bridge** — delegate to Clawdbot when hosted

### Result Structure

```python
@dataclass
class ToolResult:
    success: bool
    output: Any  # Structured data
    output_markdown: str | None  # Human-readable summary
    duration_ms: int
    tokens_used: int | None  # For LLM-based tools
    error: str | None
    metadata: dict[str, Any]
```

## Learning Loop

Tools track their own effectiveness:

```json
{
  "tool_id": "brave-search",
  "invocations": 47,
  "successes": 45,
  "failures": 2,
  "avg_duration_ms": 234,
  "last_failure": {
    "timestamp": "2026-01-23T10:00:00Z",
    "error": "Rate limit exceeded",
    "context": "During competitive analysis task"
  },
  "effectiveness_notes": [
    "Good for current events",
    "Struggles with technical documentation queries"
  ]
}
```

**Learning signals:**
- Success/failure rate
- Duration trends
- LLM self-assessment: "Did this help me get unstuck?"
- User feedback (thumbs up/down on results)

## Integration Points

### Hooks System

Tools can be dynamically registered as hooks:

```yaml
# .cub/hooks/post-epic.yaml (auto-generated)
- trigger: epic_complete
  tool: email-sender
  params:
    to: "${USER_EMAIL}"
    subject: "Epic ${EPIC_ID} complete"
    body: "${EPIC_SUMMARY}"
  registered_by: toolsmith
  registered_at: 2026-01-24T12:00:00Z
```

### Workbench

Workbench uses tools for "next move" suggestions:

```yaml
# Next move that requires a tool
next_move:
  kind: research
  tool: brave-search
  query: "postgres query optimization patterns 2026"
  target_unknown_id: unk-003
  expected_output: "List of optimization techniques with tradeoffs"
```

### Workflows

Tools participate in multi-step workflows:

```yaml
# workflow: competitive-analysis.yaml
steps:
  - id: search_competitors
    tool: brave-search
    params:
      query: "${domain} competitors"
    outputs:
      competitors: "{{ tool_output.results }}"

  - id: analyze_each
    tool: web-scraper
    for_each: "{{ competitors }}"
    params:
      url: "{{ item.url }}"
```

## Implementation Sequence

### Epic 1: Execution Runtime Foundation
- Generic adapter interface
- CLI adapter (subprocess)
- MCP stdio adapter (critical path)
- Unified result structure
- Basic error handling and timeouts

### Epic 2: Registry and Adoption
- Registry schema v1
- User + project registry loading/merging
- Adoption workflow (toolsmith → registry)
- Trust scores and source configuration
- `cub tools list/describe/adopt` commands

### Epic 3: Self-Discovery and Generation
- Capability gap recognition
- Build vs buy decision logic
- Tool generation with token budget
- Escalation flow for complex needs
- Learning loop (success tracking)

### Epic 4: Lifecycle Integration
- Hook registration from tools
- Workbench tool invocation
- Workflow step execution
- Cross-project tool sharing
- Freedom dial configuration

### Epic 5: Polish and API
- API design for future UI
- Documentation and examples
- Performance optimization
- Error recovery and retry logic

## Success Criteria

Given a need (e.g., "do competitive analysis"), cub can:

1. ✅ Recognize it needs web search capability
2. ✅ Discover brave-search in catalog (or generate simple alternative)
3. ✅ Adopt it (human provides API key once)
4. ✅ Execute search and produce markdown artifact
5. ✅ Reuse the tool in later runs without re-discovery
6. ✅ Track effectiveness and surface if tool stops working
7. ✅ Wire tool into hooks/workflows as needed

## Migration Notes

This spec consolidates and supersedes:

- `specs/researching/toolsmith.md` — discovery/adoption → Layers 1-2
- `specs/researching/tools-registry.md` — registry/execution → Layers 3-4
- `specs/researching/tool-marketplace.md` — deferred, cross-project sharing only
- `specs/planned/tool-lifecycle-mvp.md` — incorporated into this spec
- `specs/researching/pm-workbench.md` — tool-use aspects → Layer 5

The existing implementation on `feature/toolsmith` becomes the foundation:
- Keep: catalog sync, SQLite store, search/stats CLI
- Extend: adoption workflow, registry export
- Build: generic execution runtime, MCP adapter
- Integrate: hooks, workbench, workflows

## Open Questions

1. **MCP launch strategy** — stdio vs HTTP? How to supervise long-running servers?
2. **Registry file structure** — single JSON vs directory of files?
3. **Tool generation guardrails** — 500k tokens as starting point, but how to estimate complexity upfront?
4. **API surface** — what does a future UI need from the tool ecosystem?

---

**Status**: researching
**Last Updated**: 2026-01-24

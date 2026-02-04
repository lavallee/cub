# Orient Report: Unified Tool Ecosystem

**Date:** 2026-01-24
**Orient Depth:** Standard
**Status:** Approved

---

## Executive Summary

Build a coherent system for Cub to discover, adopt, and execute tools across its lifecycle. The highest value comes from **skills/prompts** (tool generation) rather than external integrations. Humans approve once (auth, budget), then tools run autonomously within a configurable freedom dial.

## Problem Statement

Cub agents repeatedly need capabilities (web search, code analysis, competitive research) that don't exist natively. Currently:
1. Humans manually search for tools
2. Humans evaluate options
3. Humans integrate and configure
4. Humans maintain knowledge over time

This is slow, inconsistent, and blocks autonomous operation. When cub encounters a capability gap, it should be able to unblock itself—finding or generating the tool it needs.

## Refined Vision

A unified tool lifecycle: **Discover → Adopt → Install → Execute → Learn**

- **Catalog** syncs from external sources (Smithery, Glama, MCP registries, etc.)
- **Registry** tracks tools approved for execution (user + project level)
- **Adoption** bridges discovery to approval (human provides credentials once)
- **Execution runtime** invokes tools via adapters (HTTP, CLI, MCP, skills)
- **Learning loop** tracks effectiveness and surfaces tool degradation

**Key insight from stakeholder:** 70%+ of value expected from skills/prompts (tool generation), not external MCP integrations. This shifts priority toward self-generation capabilities.

## Requirements

### P0 - Must Have

- **Generic execution runtime** with pluggable adapters
  - HTTP adapter (exists, proven with brave-search)
  - CLI adapter (subprocess with output capture)
  - Basic error handling and timeouts
  - *Rationale: Foundation for all tool execution*

- **Registry as source of truth**
  - JSON format at `~/.config/cub/tools/` (user) and `.cub/tools/` (project)
  - Capabilities, auth requirements, execution config
  - `cub tools list/describe/adopt` commands
  - *Rationale: Clear separation between "known tools" (catalog) and "runnable tools" (registry)*

- **Adoption workflow**
  - Propose registry entries from discovered tools
  - Human handoff for auth/budget (once per tool)
  - Track adoption decisions and rationale
  - *Rationale: Security boundary—nothing executes without explicit approval*

- **Unified result structure**
  - Success/failure, output (structured + markdown), duration, tokens, errors
  - Consistent across all adapters
  - *Rationale: Predictable interface for consumers (hooks, workflows, workbench)*

### P1 - Should Have

- **MCP stdio adapter**
  - Simple spawn-per-call model (no persistent servers initially)
  - Kill after timeout
  - *Rationale: Strategic capability, but not highest value; keep simple*

- **Capability gap recognition**
  - Explicit API: `toolsmith.find_capability("web_search")`
  - Agent code requests capabilities, toolsmith proposes solutions
  - *Rationale: Enables self-discovery without implicit magic*

- **Freedom dial configuration**
  - low/medium/high autonomy levels
  - Approval state stored in `~/.config/cub/tool-approvals.json`
  - Include tool version/checksum for re-approval on material changes
  - *Rationale: Balance autonomy with safety*

- **Learning loop basics**
  - Track success/failure rate per tool
  - Track average duration, error patterns
  - LLM self-assessment: "Did this help me get unstuck?"
  - *Rationale: Enables tool selection improvement over time*

### P2 - Nice to Have

- **Tool generation with guardrails**
  - Build simple tools from prompts when discovery fails
  - 500k token budget (soft limit, escalate on exceed)
  - *Rationale: High strategic value per stakeholder, but complex; sequence after foundation*

- **Cross-project tool sharing**
  - Package working tools for reuse
  - Not a full marketplace—just same-user sharing
  - *Rationale: Capture value without marketplace complexity*

- **Skill bridge adapter**
  - Delegate to Clawdbot when running in hosted context
  - *Rationale: Future integration path*

## Constraints

| Constraint | Impact |
|------------|--------|
| Python 3.10+, existing tech stack | Use Pydantic, Typer, Rich as established |
| CLI-first | No UI in v1; design API for future UI |
| Existing foundation on feature/toolsmith | Build on catalog sync, adoption, HTTP execution |
| Credentials env-only | No secrets management beyond env vars for v1 |

## Assumptions

| Assumption | Rationale |
|------------|-----------|
| Skills/prompts deliver 70%+ of tool value | Stakeholder input; shapes priority |
| MCP stdio spawn-per-call is sufficient for v1 | Simplicity over optimization |
| Catalog (SQLite) and Registry (JSON) are separate | Discovery cache vs execution approval |
| "Approve once" needs version tracking | Prevent abuse if tools change |
| External catalog sources remain available | Can gracefully degrade with caching |

## Open Questions / Experiments

| Unknown | Experiment |
|---------|------------|
| Optimal tool generation token budget | Start at 500k, measure actual usage, adjust |
| MCP server resource consumption | Profile spawn-per-call overhead; add pooling if needed |
| Trust score calibration | Track prediction accuracy vs actual tool reliability |

## Out of Scope

- **Multi-agent orchestration** — tools run in single-agent context
- **Paid tools / full marketplace** — all tools free/open source for v1
- **Tool versioning/upgrades** — defer to package managers
- **Visual UI** — CLI-first, API designed for future UI
- **Enterprise features** — SSO, audit logs, team permissions are later
- **Complex dependency resolution** — escalate to human

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| MCP process management complexity (crashes, zombies) | Medium | Start simple: spawn-per-call, kill on timeout. Add pooling later only if needed. |
| Tool generation produces insecure code | Medium | Require human review for generated tools; sandbox execution. |
| "Approve once" enables abuse if tool changes | Medium | Track tool version/checksum; re-prompt on material changes. |
| External catalog sources become unavailable | Low | Aggressive caching; graceful degradation; multiple sources provide redundancy. |
| Scope creep into marketplace features | Medium | Explicitly defer marketplace; cross-project sharing only for same user. |

## MVP Definition

The smallest useful thing:

**Given a need (e.g., "do competitive analysis"), cub can:**
1. Recognize it needs web search capability (via explicit API call)
2. Discover brave-search in catalog
3. Adopt it (human provides API key once)
4. Execute search via HTTP adapter and produce markdown artifact
5. Reuse the tool in later runs without re-discovery
6. Track success/failure for future selection

This is achievable with:
- Registry schema v1 + loader
- HTTP adapter (exists) + CLI adapter (new)
- Adoption workflow (exists, enhance)
- Basic learning loop (success/failure tracking)

---

## Recommended Epic Sequencing

Based on stakeholder input that skills/prompts are highest value:

### Epic 1: Execution Runtime Foundation (Critical Path)
- Generic adapter interface
- CLI adapter (subprocess)
- Unified result structure
- Basic error handling and timeouts
- *Note: MCP stdio deferred to Epic 1.5 or Epic 2*

### Epic 2: Registry and Adoption
- Registry schema v1
- User + project registry loading/merging
- Enhanced adoption workflow (toolsmith → registry)
- Trust scores and source configuration
- `cub tools list/describe/adopt` commands

### Epic 3: Self-Discovery and Generation (High Strategic Value)
- Capability gap recognition API
- Build vs buy decision logic
- Tool generation with token budget
- Escalation flow for complex needs
- *This may be higher priority than originally sequenced*

### Epic 4: Lifecycle Integration
- Hook registration from tools
- Workbench tool invocation
- Workflow step execution
- Freedom dial configuration
- Learning loop (success tracking)

### Epic 1.5 (Can Parallel): MCP Stdio Adapter
- Simple spawn-per-call model
- Timeout and cleanup
- *Lower priority per stakeholder input*

---

**Next Step:** Run `cub architect` to design the technical architecture.

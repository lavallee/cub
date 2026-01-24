---
status: draft
priority: high
complexity: high
dependencies:
  - specs/researching/tools-registry.md
  - specs/researching/toolsmith.md
  - specs/researching/workflow-management.md
created: 2026-01-24
updated: 2026-01-24
readiness:
  score: 6
  blockers:
    - Decide canonical registry + adoption storage model (file locations + schema)
    - Decide security/approval policy for installation and execution
    - Decide how MCP servers are launched (stdio vs HTTP) and supervised
  questions:
    - What is the minimum generic runtime we need (MCP stdio first)?
    - How do we represent credentials safely (env only vs encrypted store)?
    - What are the “crowd signals” we trust (stars, last commit, downloads, curated lists)?
    - When do we prefer purpose-built Cub-native tools over external tools?
  decisions_needed:
    - Registry file format and location (align with existing config + .env layering)
    - Execution sandboxing defaults (on by default for third-party tools?)
    - Tool budget/rate-limit policy (global + per-tool)
notes: |
  This spec consolidates remaining scope from:
  - Toolsmith (discovery/adoption)
  - Tools Registry (canonical tool definitions)
  - Workflow Management (orchestration)
  after initial implementation work landed on feature/toolsmith.

  Goal: keep adding capabilities in a logical way without drifting into
  overlapping mini-systems.
---

# Spec: Tool Lifecycle MVP (Discover → Adopt → Install → Execute → Learn)

## Summary

Cub should be able to **find and use tools/skills** from multiple ecosystems to achieve its goals, balancing:

1) **Crowd signals** (popularity, maturity, curated registries) to reduce risk
2) **Cub-native purpose-built tools** (reusable internal modules) when external tools are missing, risky, or too costly

This spec defines the **minimum coherent end-to-end lifecycle** and the remaining scope to implement after the initial Toolsmith + Workbench experiments.

## What’s already implemented (as of 2026-01-24)

These pieces exist on `feature/toolsmith` and should be treated as “prototype MVP” components to either keep or refactor into the final architecture:

### Toolsmith (prototype)
- Tool catalog sync from multiple sources (e.g., mcp-official, smithery, glama, clawdhub)
- Local catalog storage at `.cub/toolsmith/catalog.json`
- CLI:
  - `cub toolsmith sync`
  - `cub toolsmith search` (now shows tool IDs)
  - `cub toolsmith adopt` / `cub toolsmith adopted`
  - `cub toolsmith run <tool_id>` (experimental)

### Execution (prototype)
- A thin execution adapter for **one tool**:
  - `mcp-official:brave-search` (via Brave Search HTTP API)
- Run artifacts written to `.cub/toolsmith/runs/*.json`

### Config / secrets loading
- Layered env loading:
  - OS env > project `.env/.env.local` > user `~/.config/cub/.env`

### Workbench (prototype)
- `cub workbench start` creates `specs/workbench/sessions/*.md`
- `cub workbench run-next` runs next_move queries via tool execution
- `cub workbench run-next --write-note` synthesizes run artifacts into a markdown note

## Problem: overlapping specs / missing unification

The research specs define three overlapping “centers of gravity”:
- **Toolsmith** = discovery + evaluation + adoption workflow
- **Tools Registry** = canonical tool definitions + capability-based selection
- **Workflow Management** = orchestration and multi-step execution

The experiment implemented a pragmatic slice across all three, but we need a **single coherent plan** for:
- canonical data models
- storage locations
- security policy
- runtime supervision

## Definitions

### Tool lifecycle stages

1) **Discover**: find candidate tools for a capability
2) **Evaluate**: score options using crowd + internal signals
3) **Adopt**: record “we intend to use this tool” (project/user)
4) **Install**: make tool available (package install, MCP server, skill fetch)
5) **Execute**: invoke tool with parameters, produce artifacts
6) **Learn**: record observed reliability/cost/utility and feed back into scoring

## Proposed architecture (v1)

### A) Canonical registry (what Cub *can* run)
Create a single canonical registry model (file-based first):

- User registry: `~/.config/cub/tools-registry.json` (or yaml)
- Project registry: `.cub/tools-registry.json`
- Runtime: merged in-memory view

The registry defines:
- tool id (stable)
- source type (mcp | skill | cli | http-api | internal)
- install/check
- execution transport (stdio/http)
- capabilities + categories
- required secrets (names only; values always come from env)

### B) Toolsmith becomes “discovery + recommendation”
Toolsmith should:
- sync external catalogs
- propose registry entries
- propose adoption + required env vars
- never silently installs without policy approval

### C) Execution runtime (the missing core)
We need a generic execution runtime layer with pluggable backends:

1) **HTTP API tools** (like brave-search) — simplest
2) **CLI tools** (subprocess) — common
3) **MCP stdio servers** — strategic (filesystem, github, browser automation)
4) **Clawdbot skills** — when running under Clawdbot (bridge mode)

The runtime must provide:
- timeouts
- rate limiting + backoff
- structured artifacts (json + optional markdown)
- consistent error envelopes

### D) “Crowd signals” + “Cub-native tools” decision rule
Add a decision rubric used by Toolsmith and/or workflows:

Prefer external tool when:
- mature + widely used
- integration cost low
- safety manageable (sandboxable)

Prefer Cub-native when:
- tool is core to Cub’s identity (PM shaping, spec readiness)
- external offerings are fragmented/unstable
- high recurrence and worth owning

## Remaining scope (what to build next)

### 1) Registry schema + migration
- Decide JSON vs YAML
- Implement loader/validator
- Provide `cub tools list/describe` (or `cub toolsmith export-registry`)

### 2) Generic executor + adapters
- CLI executor (safe allowlist)
- HTTP executor (already partially exists)
- MCP stdio executor (biggest lift)

### 3) Install + approval policy
- Explicit approval prompts (or “policy modes”)
- Sandbox defaults for third-party tools
- Audit log of installs/executions

### 4) Credentials + environment standards
- Document env var names per tool
- Ensure `.env.local` + user env are first-class
- Add redaction in logs/artifacts

### 5) Learning loop
- Track tool reliability (success/fail)
- Track cost/rate limits
- Feed into future selection scoring

## Deliverables

- `specs/planned/tool-lifecycle-mvp.md` (this spec)
- A concrete registry schema v1
- `cub tools` (or expand `toolsmith`) to:
  - export selected tool into registry
  - execute tool through a generic runtime
- MCP stdio runner (minimal): start server, call one method, stop server

## Success criteria

- Given a need (e.g., “do competitive analysis”), Cub can:
  - discover candidate tools
  - adopt one
  - configure required secrets via `.env.local` / user env
  - execute tool safely and produce a markdown artifact
  - reuse the tool in a later run without re-discovery

## Related

- `specs/researching/toolsmith.md`
- `specs/researching/tools-registry.md`
- `specs/researching/workflow-management.md`
- `specs/researching/pm-workbench.md`

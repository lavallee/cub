# Triage Report: Toolsmith

**Date:** 2026-01-20
**Triage Depth:** Standard
**Status:** Approved

---

## Executive Summary

Toolsmith is a meta-tool that helps Cub discover and catalog tools from curated sources (MCP registries, skill marketplaces). It creates a compounding layer of tool knowledge that persists across sessions and projects, enabling Cub to self-serve capabilities rather than requiring manual tool research.

## Problem Statement

Tool discovery and creation is a compounding investment - each tool learned or built makes future work faster. Modern LLMs are good at using tools (Claude skills, MCP servers), but there's no layer that accumulates this learning across sessions and projects. Toolsmith is that layer - a way for Cub to build institutional knowledge about what tools exist, which work well, and how to use them.

**Current state:** When Cub needs a capability, humans manually search, evaluate, integrate, and maintain tools. This doesn't scale and doesn't compound.

**Desired state:** Cub maintains a searchable catalog of available tools from trusted sources, enabling rapid capability acquisition.

## Refined Vision

Build the **supply side** of tool discovery: a searchable local catalog of tools from curated MCP registries and skill marketplaces. The demand side (integration with prep/investigate/run) comes later once the catalog proves useful.

## Requirements

### P0 - Must Have

- **Catalog sync from curated sources**: Fetch and parse tool metadata from MCP official repo, Smithery.ai, Glama.ai, Claude skills, and community skill repos
- **Local storage**: Store catalog in `.cub/toolsmith/catalog.json` for fast local search
- **Keyword search**: Search tool names and descriptions for query terms
- **Rich output**: Return tool name, source, type, description, and installation hints
- **CLI interface**: `cub toolsmith search <query>` and `cub toolsmith sync`

### P1 - Should Have

- **Live fallback**: When local search returns no results, query sources directly
- **Source abstraction**: Each source has its own parser, easy to add new sources
- **Catalog stats**: `cub toolsmith stats` shows catalog size, sources, last sync

### P2 - Nice to Have

- **Alias/tag support**: Add searchable aliases during sync for better discovery
- **Offline mode flag**: Explicitly disable live fallback when needed
- **Source filtering**: `cub toolsmith search --source smithery <query>`

## Constraints

- **Tech stack**: Python 3.10+, Typer CLI (matches existing Cub architecture)
- **Harness integration**: Tools may require harness features; catalog should note requirements
- **Auth handling**: API keys for sources or tools require human setup (no auto-provisioning)
- **No trawling**: Do not search GitHub, npm, PyPI, or other general package registries in v1

## Assumptions

- Curated sources have parseable formats (APIs, JSON, or scrapeable HTML)
- Initial catalog of ~100-500 tools provides sufficient signal
- Keyword matching on names and descriptions will surface relevant tools
- Tool installation hints from sources are generally accurate

## Open Questions / Experiments

- **Search effectiveness**: Will keyword matching find what's needed? Experiment: Track search success rate once demand side integrates
- **Source coverage**: Are curated sources sufficient? Experiment: Log "no results" queries to identify gaps
- **Catalog freshness**: How often do sources update? Experiment: Track delta between syncs

## Out of Scope

- **Evaluation and scoring**: No quality assessment, maturity checks, or comparison matrices (v2)
- **Auto-adoption**: No automatic installation or integration (v2)
- **General registries**: No GitHub, npm, PyPI, or similar broad searches (v2+)
- **Demand-side integration**: No automatic triggering from prep/investigate/run (separate workstream)
- **Tool creation**: No building tools from scratch, only discovery

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Sources change format/API | M | Abstract parser per source; isolate breakage |
| Tool descriptions don't match actual capability | M | Note source trust level; add manual curation later |
| Search terms don't match tool vocabulary | H | Add alias/tag support; learn from failed searches |
| Curated sources have insufficient coverage | H | Track "no results" rate; expand sources if needed |
| Rate limiting on live fallback | L | Implement backoff; prefer local catalog |

## MVP Definition

**Smallest useful thing:** A CLI that syncs tool metadata from 5 curated sources into a local catalog and provides keyword search with rich output.

```bash
# Sync catalog from all sources
cub toolsmith sync

# Search for tools
cub toolsmith search "browser automation"

# Output:
# Found 3 tools:
#
# playwright-mcp
#   Source: smithery.ai (MCP server)
#   Description: Browser automation via Playwright
#   Install: npx @anthropic/mcp add playwright
#
# puppeteer-skill
#   Source: claude-skills (Skill)
#   Description: Headless browser control
#   Install: claude skill add puppeteer
# ...
```

## Success Criteria

**Primary metric:** Time from "need identified" to "tool working" drops significantly once demand side integrates.

**Leading indicators for supply side:**
- Catalog contains 100+ tools from 5 sources
- Search returns relevant results for common needs (browser, database, file, API, etc.)
- Sync completes without errors from all sources

## Curated Sources (v1)

| Source | Type | URL | Notes |
|--------|------|-----|-------|
| MCP Official | MCP servers | github.com/modelcontextprotocol/servers | Canonical source |
| Smithery.ai | MCP marketplace | smithery.ai | Community MCP servers |
| Glama.ai | MCP directory | glama.ai | Curated MCP list |
| Claude Skills | Skills | Built-in + community | Claude Code skills |
| ClawdHub | Skills | Community repo | Community skill collection |

---

**Next Step:** Run `cub architect` to proceed to technical design.

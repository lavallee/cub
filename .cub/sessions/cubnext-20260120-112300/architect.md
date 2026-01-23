# Architecture Design: Toolsmith

**Date:** 2026-01-20
**Mindset:** Production
**Scale:** Product (1,000+ users)
**Status:** Approved

---

## Technical Summary

Toolsmith is a tool discovery system that maintains a searchable catalog of MCP servers and Claude skills from curated sources. It follows Cub's existing architectural patterns: a **Source protocol** for pluggable data fetchers (like `TaskBackend`), a **ToolsmithStore** for catalog persistence (like `CaptureStore`), and Pydantic v2 models for type-safe data.

The system uses a hybrid storage approach: a local JSON catalog that syncs on-demand from 5 curated sources, with optional live fallback when local search returns no results. This balances speed (local search) with freshness (live queries when needed).

The architecture prioritizes maintainability and testability appropriate for a production-quality public product, with clear separation between CLI, service, storage, and source layers.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Match existing Cub codebase |
| CLI Framework | Typer | Match existing Cub CLI patterns |
| Data Models | Pydantic v2 | Match existing Cub, strong validation |
| HTTP Client | httpx | Modern, sync/async support, good typing |
| Storage | JSON file | Simple, matches Cub patterns, human-readable |
| Search | In-memory keyword | Sufficient for 100-500 tools catalog |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Layer                                 │
│  cub toolsmith sync    cub toolsmith search    cub toolsmith stats│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ToolsmithService                             │
│  - Orchestrates sync across sources                              │
│  - Executes search against catalog                               │
│  - Handles live fallback when local search fails                 │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ ToolsmithStore  │  │  Source Layer   │  │   Search Engine │
│ (.cub/toolsmith │  │  (Protocol +    │  │   (keyword      │
│  /catalog.json) │  │   5 adapters)   │  │    matching)    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                              │
          ┌─────────┬─────────┼─────────┬─────────┐
          ▼         ▼         ▼         ▼         ▼
       ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐
       │ MCP │  │Smith│  │Glama│  │Skills│ │Clawd│
       │Offic│  │ery  │  │ .ai │  │ MP   │ │Hub  │
       └─────┘  └─────┘  └─────┘  └─────┘  └─────┘
```

## Components

### Tool Model
- **Purpose:** Represents a single discoverable tool (MCP server or skill)
- **Responsibilities:**
  - Store tool metadata (name, description, source, install hints)
  - Validate tool data
  - Serialize to/from JSON
- **Dependencies:** Pydantic
- **Interface:** Pydantic model with `model_dump()` / `model_validate()`

```python
class ToolType(str, Enum):
    MCP_SERVER = "mcp_server"
    SKILL = "skill"

class Tool(BaseModel):
    id: str                    # Unique: "{source}:{name}"
    name: str                  # Display name
    source: str                # Which source (smithery, glama, etc.)
    source_url: str            # Direct link to tool
    tool_type: ToolType        # MCP server or skill
    description: str           # What it does
    install_hint: str | None   # How to install (if known)
    tags: list[str]            # Searchable tags/categories
    last_seen: datetime        # When we last saw it in source
```

### Catalog Model
- **Purpose:** Container for all tools plus sync metadata
- **Responsibilities:**
  - Track catalog version for future migrations
  - Record sync timestamps per source
  - Hold the full tool list
- **Dependencies:** Tool model
- **Interface:** Pydantic model

```python
class Catalog(BaseModel):
    version: int = 1
    last_sync: datetime | None = None
    sources_synced: dict[str, datetime] = {}
    tools: list[Tool] = []
```

### ToolSource Protocol
- **Purpose:** Abstract interface for tool data sources
- **Responsibilities:**
  - Define contract for fetching tools
  - Define contract for live search
- **Dependencies:** Tool model
- **Interface:** Protocol class

```python
@runtime_checkable
class ToolSource(Protocol):
    @property
    def name(self) -> str:
        """Unique source identifier (e.g., 'smithery', 'glama')"""
        ...

    def fetch_tools(self) -> list[Tool]:
        """Fetch all tools from this source for catalog sync"""
        ...

    def search_live(self, query: str) -> list[Tool]:
        """Search source directly (for live fallback)"""
        ...
```

### Source Implementations
- **Purpose:** Concrete adapters for each curated source
- **Responsibilities:**
  - Parse source-specific formats (HTML, JSON, API)
  - Transform to Tool model
  - Handle source-specific quirks
- **Dependencies:** httpx, Tool model
- **Interface:** Implements ToolSource protocol

| Source | File | Notes |
|--------|------|-------|
| MCP Official | `mcp_official.py` | Parse GitHub repo README/servers.json |
| Smithery.ai | `smithery.py` | Scrape/API from smithery.ai |
| Glama.ai | `glama.py` | Scrape/API from glama.ai |
| SkillsMP | `skillsmp.py` | Scrape/API from skillsmp.com |
| ClawdHub | `clawdhub.py` | Parse GitHub repo |

### ToolsmithStore
- **Purpose:** Persistence layer for the tool catalog
- **Responsibilities:**
  - Load catalog from `.cub/toolsmith/catalog.json`
  - Save catalog to disk
  - Provide local search interface
- **Dependencies:** Catalog model, pathlib
- **Interface:** Class with load/save/search methods

```python
class ToolsmithStore:
    def __init__(self, toolsmith_dir: Path): ...

    def load_catalog(self) -> Catalog: ...
    def save_catalog(self, catalog: Catalog) -> None: ...
    def search(self, query: str) -> list[Tool]: ...

    @classmethod
    def default(cls) -> "ToolsmithStore":
        """Returns store at .cub/toolsmith/"""
```

### ToolsmithService
- **Purpose:** Business logic orchestration
- **Responsibilities:**
  - Coordinate sync across multiple sources
  - Merge new tools into catalog (update existing, add new)
  - Execute search with optional live fallback
  - Provide catalog statistics
- **Dependencies:** ToolsmithStore, ToolSource implementations
- **Interface:** Service class

```python
class ToolsmithService:
    def __init__(self, store: ToolsmithStore, sources: list[ToolSource]): ...

    def sync(self, source_names: list[str] | None = None) -> SyncResult: ...
    def search(self, query: str, live_fallback: bool = True) -> list[Tool]: ...
    def stats(self) -> CatalogStats: ...
```

### CLI Commands
- **Purpose:** User-facing interface
- **Responsibilities:**
  - Parse CLI arguments
  - Invoke service methods
  - Format output with Rich
- **Dependencies:** Typer, Rich, ToolsmithService
- **Interface:** Typer app with subcommands

```python
app = typer.Typer(name="toolsmith", help="Discover and catalog tools")

@app.command()
def sync(
    source: Annotated[str | None, typer.Option()] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Sync tool catalog from sources."""

@app.command()
def search(
    query: Annotated[str, typer.Argument()],
    live: Annotated[bool, typer.Option("--live")] = False,
    source: Annotated[str | None, typer.Option("--source")] = None,
) -> None:
    """Search for tools matching query."""

@app.command()
def stats() -> None:
    """Show catalog statistics."""
```

## Data Model

### Tool
```
id: str                 - Unique identifier "{source}:{slug}"
name: str               - Human-readable display name
source: str             - Source identifier (smithery, glama, etc.)
source_url: str         - URL to tool page/repo
tool_type: ToolType     - Enum: mcp_server | skill
description: str        - What the tool does
install_hint: str|None  - Installation command if known
tags: list[str]         - Categories/keywords for search
last_seen: datetime     - When tool was last seen in source
```

### Catalog
```
version: int            - Schema version for migrations
last_sync: datetime     - When any sync last ran
sources_synced: dict    - Map of source -> last sync time
tools: list[Tool]       - All tools in catalog
```

### Relationships
- Catalog contains many Tools (1:N)
- Each Tool belongs to exactly one Source
- Tools are identified by composite key `{source}:{name}`

## APIs / Interfaces

### CLI Interface
- **Type:** Command-line (Typer)
- **Purpose:** User interaction
- **Key Commands:**
  - `cub toolsmith sync [--source NAME]` - Sync catalog from sources
  - `cub toolsmith search QUERY [--live] [--source NAME]` - Search for tools
  - `cub toolsmith stats` - Show catalog statistics

### ToolSource Protocol
- **Type:** Internal Python protocol
- **Purpose:** Pluggable source adapters
- **Key Methods:**
  - `name: str` - Source identifier
  - `fetch_tools() -> list[Tool]` - Get all tools
  - `search_live(query) -> list[Tool]` - Live search

### ToolsmithService
- **Type:** Internal Python API
- **Purpose:** Business logic
- **Key Methods:**
  - `sync(source_names) -> SyncResult` - Sync sources to catalog
  - `search(query, live_fallback) -> list[Tool]` - Search catalog
  - `stats() -> CatalogStats` - Get statistics

## Implementation Phases

### Phase 1: Foundation
**Goal:** Core data structures and storage

- Define Tool and Catalog Pydantic models
- Implement ToolsmithStore (load/save JSON)
- Basic keyword search function
- CLI skeleton with `sync`, `search`, `stats` commands (stubs)
- Unit tests for models and store

### Phase 2: Sources
**Goal:** Fetch tools from all 5 curated sources

- Define ToolSource protocol
- Implement source registry (like task backend registry)
- Implement each source adapter (one at a time):
  1. MCP Official (GitHub) - likely simplest
  2. Smithery.ai
  3. Glama.ai
  4. SkillsMP
  5. ClawdHub
- Tests with response fixtures for each source

### Phase 3: Service Layer
**Goal:** Orchestration and search logic

- Implement ToolsmithService
- Sync logic: fetch from sources, merge into catalog, handle updates
- Search logic: local search, live fallback when no results
- Wire CLI commands to service
- Integration tests

### Phase 4: Polish
**Goal:** Production readiness

- Rich CLI output formatting (tables, colors)
- Error handling (network failures, parse errors)
- Retry logic with backoff for HTTP requests
- Logging for debugging
- Documentation
- Test coverage to 80%+ for core modules

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Source HTML/API format changes | M | H | Abstract per-source parser; isolate breakage; test with fixtures |
| Rate limiting on HTTP requests | L | M | Add delays between requests; prefer local catalog; implement backoff |
| Source has no search API | M | M | Fetch full catalog during sync, search locally |
| Tool IDs collide across sources | L | L | Namespace IDs as `{source}:{slug}` |
| Source unavailable during sync | M | M | Continue with other sources; report partial sync |
| Catalog file corruption | L | L | Validate on load; keep backup before write |

## Dependencies

### External
- **httpx**: HTTP client for fetching from sources
- **MCP Official GitHub**: github.com/modelcontextprotocol/servers
- **Smithery.ai**: smithery.ai (MCP marketplace)
- **Glama.ai**: glama.ai (MCP directory)
- **SkillsMP**: skillsmp.com (Claude skills marketplace)
- **ClawdHub**: GitHub community repo for skills

### Internal
- **cub.cli**: Register `toolsmith` subcommand
- **Rich**: Output formatting (already a cub dependency)
- **Pydantic v2**: Models (already a cub dependency)

## Security Considerations

- **No secrets in catalog**: Tool entries store only public metadata, never API keys
- **Validate URLs**: Don't blindly follow redirects; validate source domains
- **Sanitize search input**: Prevent injection (future-proofing for any DB/API)
- **Safe file operations**: Atomic writes, validate JSON before loading
- **Unauthenticated only**: v1 uses only public endpoints, no stored credentials

## Future Considerations

These are explicitly deferred but should inform the design:

- **Semantic search**: Add embeddings for better query matching (would add to Tool model)
- **Tool evaluation/scoring**: Quality metrics per tool (would add to Tool model)
- **Auto-adoption workflow**: Install tools automatically (new service methods)
- **Demand-side integration**: Trigger searches from prep/investigate/run (service hooks)
- **Tool version tracking**: Track tool versions over time (would add to Tool model)
- **Additional sources**: npm, PyPI, GitHub search (new source adapters)
- **Caching layer**: Cache HTTP responses for faster repeated syncs

---

**Next Step:** Run `cub plan` to generate implementation tasks.

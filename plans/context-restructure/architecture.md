# Architecture Design: Context Restructure

**Date:** 2026-01-28
**Mindset:** Production
**Scale:** Team (cub users across projects)
**Status:** Draft

---

## Technical Summary

This architecture restructures cub's context delivery into a layered system
where each layer has a single owner and clear purpose. The foundation is a
non-destructive demarcated section in CLAUDE.md/AGENTS.md that references
auto-generated files in `.cub/`. The `cub map` command uses tree-sitter (via
`grep-ast`) and PageRank (via `networkx`) to produce a token-budgeted project
map. A shipped constitution provides operating principles. The run loop gains
epic context enrichment and retry injection from the ledger.

The architecture introduces one new module (`cub.core.map`), extends two
existing commands (`init`, `update`), adds one new command (`map`), modifies
the instruction generator and run loop, and eliminates four templates. The
dependency footprint grows by three packages (`grep-ast`, `networkx`,
`tree-sitter-language-pack`) plus their transitive dependencies.

All changes preserve backward compatibility: existing CLAUDE.md/AGENTS.md
content is never destroyed, the ledger schema is unchanged, and the config
system gains new optional fields with sensible defaults.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| AST Parsing | `grep-ast` (wraps tree-sitter) | MIT licensed, by Aider's author. Provides tag extraction (definitions + references) with language-aware queries for 30+ languages. Handles tree-sitter complexity. |
| Language Grammars | `tree-sitter-language-pack` | Pre-built wheels for 100+ languages. Single install, no per-language detection needed. |
| Graph Ranking | `networkx` | Industry-standard graph library. PageRank implementation is mature and well-tested. |
| Token Estimation | `tiktoken` or sampling | For budget enforcement. Can use tiktoken (OpenAI's tokenizer) or simple word-count heuristic for model-agnostic estimation. |
| Config | Pydantic v2 (existing) | New `MapConfig` model integrates with existing config system. |
| CLI | Typer (existing) | New `map` command follows established patterns. |
| Caching | `diskcache` | SQLite-backed persistent cache for parsed ASTs. Avoids re-parsing unchanged files. |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ CLI Layer                                                       │
├─────────────────────────────────────────────────────────────────┤
│ cub init ──→ instructions.py ──→ demarcated CLAUDE.md/AGENTS.md │
│              constitution.py ──→ .cub/constitution.md            │
│              map (auto) ──────→ .cub/map.md                     │
│                                                                 │
│ cub map ───→ map.generator ──→ .cub/map.md                     │
│              ├── map.structure (directory tree, config parsing)  │
│              ├── map.code_intel (grep-ast + networkx PageRank)  │
│              └── map.renderer (token-budgeted markdown output)  │
│                                                                 │
│ cub update → instructions.py ──→ refresh managed sections       │
│              map (auto) ──────→ refresh .cub/map.md             │
│                                                                 │
│ cub run ───→ run.py                                             │
│              ├── system_prompt ← .cub/runloop.md                │
│              └── task_prompt ← generate_task_prompt()            │
│                  ├── task details                                │
│                  ├── epic_context() ← task backend               │
│                  └── retry_context() ← ledger reader             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Context Stack (what an agent sees)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ INTERACTIVE SESSION          │  CUB RUN SESSION                 │
│                              │                                  │
│ CLAUDE.md (auto-read)        │  CLAUDE.md (auto-read)           │
│ ├── user content             │  ├── user content                │
│ └── managed section          │  └── managed section             │
│     ├── @.cub/map.md         │      ├── @.cub/map.md            │
│     ├── @.cub/constitution   │      ├── @.cub/constitution      │
│     └── cub workflow cmds    │      └── cub workflow cmds       │
│                              │                                  │
│                              │  + system prompt (.cub/runloop)  │
│                              │    └── ralph-loop behavior       │
│                              │                                  │
│                              │  + task prompt (stdin)           │
│                              │    ├── task details              │
│                              │    ├── epic context              │
│                              │    ├── sibling awareness         │
│                              │    └── retry context (if retry)  │
│                              │                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Managed Section Engine (`cub.core.instructions`)

**Purpose:** Insert, find, replace, and version-manage cub's demarcated region
within CLAUDE.md and AGENTS.md files.

**Responsibilities:**
- Generate managed section content (condensed cub workflow + references)
- Find existing markers in a file (`<!-- BEGIN CUB MANAGED SECTION vN -->`)
- Replace content between markers, preserving everything outside
- Handle edge cases: missing file, no markers (first init), partial markers
  (warn + recover), version mismatch (warn + replace)
- Generate Claude-specific additions for CLAUDE.md

**Interface:**
```python
# Refactored public API
def generate_managed_section(
    project_dir: Path,
    config: CubConfig,
    harness: str = "generic",  # "generic" for AGENTS.md, "claude" for CLAUDE.md
) -> str:
    """Generate the content that goes between markers."""

def upsert_managed_section(
    file_path: Path,
    section_content: str,
    version: int = 1,
) -> UpsertResult:
    """Insert or replace managed section in a file.

    Returns UpsertResult with status (created/updated/unchanged)
    and any warnings (e.g., manual edits detected inside markers).
    """

def detect_managed_section(file_path: Path) -> SectionInfo | None:
    """Find existing managed section markers and return metadata.

    Returns version, start line, end line, or None if no markers found.
    """

# Data models
class UpsertResult(BaseModel):
    status: Literal["created", "updated", "unchanged"]
    file_path: Path
    version: int
    warnings: list[str]

class SectionInfo(BaseModel):
    version: int
    start_line: int
    end_line: int
    content_hash: str  # For detecting manual edits
```

**Dependencies:** None beyond stdlib + pydantic.

### 2. Map Generator (`cub.core.map`)

**Purpose:** Generate a token-budgeted project map combining structural
analysis with tree-sitter code intelligence.

**Submodules:**

#### 2a. Structure Analyzer (`cub.core.map.structure`)

**Responsibilities:**
- Generate directory tree (depth-limited, respects .gitignore via pathspec)
- Detect tech stack from config files (pyproject.toml, package.json, etc.)
- Extract build/test/lint commands from config
- Identify key files (README, entry points, test directories)
- Detect module boundaries (top-level packages)

**Interface:**
```python
class ProjectStructure(BaseModel):
    """Structural analysis of a project."""
    root: Path
    tree: DirectoryTree
    tech_stack: TechStack
    build_commands: list[BuildCommand]
    key_files: list[KeyFile]
    modules: list[ModuleInfo]

def analyze_structure(
    project_dir: Path,
    max_depth: int = 4,
) -> ProjectStructure:
    """Analyze project structure without code parsing."""
```

**Config file parsers** (one per ecosystem):
- `pyproject.toml` → Python (extract scripts, dependencies, tool configs)
- `package.json` → Node/JS/TS (extract scripts, main, dependencies)
- `Cargo.toml` → Rust (extract bin targets, workspace)
- `go.mod` → Go (extract module path)
- `Makefile` → Generic (extract target names)
- `Dockerfile` → Container (detect base image, entrypoint)

#### 2b. Code Intelligence (`cub.core.map.code_intel`)

**Responsibilities:**
- Parse source files using `grep-ast` (wraps tree-sitter)
- Extract definition tags (functions, classes, methods) and reference tags
  (imports, calls)
- Build cross-file reference graph (files as nodes, references as edges)
- Apply PageRank to rank symbols by structural importance
- Cache parsed results via `diskcache` to avoid re-parsing unchanged files

**Interface:**
```python
class SymbolTag(BaseModel):
    """A tagged symbol from code parsing."""
    name: str
    kind: Literal["def", "ref"]
    file: Path
    line: int
    signature: str | None  # Function/class signature if definition

class RankedSymbol(BaseModel):
    """A symbol with its PageRank score."""
    tag: SymbolTag
    rank: float
    file: Path

def extract_tags(
    project_dir: Path,
    files: list[Path],
) -> list[SymbolTag]:
    """Extract definition and reference tags from source files."""

def rank_symbols(
    tags: list[SymbolTag],
    token_budget: int = 1500,
) -> list[RankedSymbol]:
    """Rank symbols by structural importance and budget to token limit."""
```

**Dependencies:** `grep-ast`, `networkx`, `tree-sitter-language-pack`,
`diskcache`

#### 2c. Map Renderer (`cub.core.map.renderer`)

**Responsibilities:**
- Combine structural analysis + ranked symbols into markdown
- Enforce token budget (structural layer first, code intelligence fills
  remainder)
- Format for readability: sections for tree, tech stack, key symbols

**Interface:**
```python
def render_map(
    structure: ProjectStructure,
    ranked_symbols: list[RankedSymbol],
    token_budget: int = 1500,
    include_ledger_stats: bool = True,
    ledger_reader: LedgerReader | None = None,
) -> str:
    """Render the project map as markdown within token budget."""
```

**Output format:**
```markdown
# Project Map

## Tech Stack
- Python 3.10+ (pyproject.toml)
- Framework: Typer CLI + Pydantic v2
- Tests: pytest
- Linting: ruff, mypy

## Build Commands
- Install: `uv sync`
- Test: `pytest tests/ -v`
- Typecheck: `mypy src/cub`
- Lint: `ruff check src/ tests/`

## Structure
src/cub/
  cli/          # CLI commands (Typer)
  core/         # Core logic
    config/     # Configuration system
    harness/    # AI harness backends
    tasks/      # Task management backends
    map/        # Project map generation
    ledger/     # Task completion tracking
  utils/        # Utilities
tests/          # pytest test suite

## Key Symbols (ranked by structural importance)
- `CubConfig` (core/config/models.py:45) - Central configuration model
- `TaskBackend` (core/tasks/backend.py:12) - Task management protocol
- `HarnessBackend` (core/harness/backend.py:20) - AI harness protocol
- `generate_task_prompt` (cli/run.py:533) - Task prompt composition
- `LedgerReader` (core/ledger/reader.py:15) - Ledger query interface
...

## Project Health (from ledger)
- 47 tasks completed, 12 open
- Average 1.3 attempts per task
- Most active modules: cli/run.py, core/harness/
```

### 3. Constitution Manager (`cub.core.constitution`)

**Purpose:** Manage the operating principles file.

**Responsibilities:**
- Copy default constitution to `.cub/constitution.md` on init
- Never overwrite on update (user may have customized)
- Provide API for reading constitution content

**Interface:**
```python
def ensure_constitution(
    project_dir: Path,
    force: bool = False,
) -> Path:
    """Ensure constitution exists. Returns path.
    Creates from default template if missing. Never overwrites unless force=True.
    """

def read_constitution(project_dir: Path) -> str | None:
    """Read constitution content, or None if not present."""
```

**Dependencies:** None beyond stdlib. Reads `templates/constitution.md` as
the default.

### 4. Runloop Prompt (`templates/runloop.md`)

**Purpose:** Pure ralph-loop autonomous behavior prompt.

**Content (entire file, ~40 lines):**
- Work on one task at a time
- Understand → search → implement → validate → complete cycle
- Run feedback loops before closing
- Signal `<stuck>` when blocked
- Signal `<promise>COMPLETE</promise>` when all tasks done
- Escape hatch semantics

**Not in this file:**
- Project context references (now in CLAUDE.md managed section)
- Generic coding advice (now in constitution)
- Progress.txt references (eliminated)

**Used by:** `generate_system_prompt()` in `run.py`. The lookup order changes
from `PROMPT.md` → `templates/PROMPT.md` → fallback to:
`.cub/runloop.md` → `templates/runloop.md` → fallback.

### 5. Task Prompt Enrichment (`cub.cli.run`)

**Purpose:** Add epic context and retry awareness to task prompts.

**New functions in run.py:**

```python
def generate_epic_context(
    task: Task,
    task_backend: TaskBackend,
) -> str | None:
    """Generate epic context section for a task prompt.

    Returns None if task has no parent epic.
    Includes: epic description, completed siblings, remaining siblings.
    """

def generate_retry_context(
    task: Task,
    ledger_reader: LedgerReader,
    log_tail_lines: int = 50,
) -> str | None:
    """Generate previous-attempt context for a retry.

    Returns None if no previous failed attempts.
    Includes: error_category, error_summary, tail of harness log.
    """
```

**Integration point:** After `generate_task_prompt()` returns, append epic
context and retry context if available.

### 6. CLI Commands

#### `cub map` (`cub.cli.map`)

```python
def map_command(
    project_dir: str = typer.Argument(".", help="Project directory"),
    tokens: int = typer.Option(1500, "--tokens", "-t", help="Token budget"),
    output: str = typer.Option(None, "--output", "-o", help="Output path (default: .cub/map.md)"),
    no_code_intel: bool = typer.Option(False, "--no-code-intel", help="Skip tree-sitter analysis"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Generate project map with code intelligence."""
```

#### `cub update` (extend `cub.cli.update`)

Add to existing update command:
- Refresh managed sections in CLAUDE.md and AGENTS.md
- Regenerate `.cub/map.md`
- Check constitution exists (don't overwrite)
- Ensure `.cub/runloop.md` is current

#### `cub init` (extend `cub.cli.init_cmd`)

Change init behavior:
- Use `upsert_managed_section()` instead of writing entire files
- Generate `.cub/map.md` via map generator
- Copy constitution if missing
- Copy runloop if missing

## Data Model

### MapConfig (new, in `cub.core.config.models`)

```python
class MapConfig(BaseModel):
    """Codebase map generation configuration."""
    token_budget: int = Field(default=1500, ge=100, le=10000)
    max_depth: int = Field(default=4, ge=1, le=10)
    include_code_intel: bool = Field(default=True)
    include_ledger_stats: bool = Field(default=True)
    exclude_patterns: list[str] = Field(default_factory=lambda: [
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    ])
```

### Managed Section Markers

```
<!-- BEGIN CUB MANAGED SECTION v{version} -->
<!-- sha256:{content_hash} -->
<!-- Do not edit this section. Run `cub update` to refresh. -->
<!-- To customize cub behavior, add your overrides OUTSIDE this section. -->

{content}

<!-- END CUB MANAGED SECTION -->
```

The `sha256` hash of the content enables detecting manual edits inside the
managed region. If the hash doesn't match on update, warn the user.

### No new ledger models

The retry context reads existing `Attempt` fields (`error_category`,
`error_summary`) and existing harness log files
(`.cub/ledger/by-task/{id}/attempts/{n}-harness.log`). No schema changes.

## Implementation Phases

### Phase 1: Foundation

**Goal:** Non-destructive managed sections + runloop + constitution.

1. Implement `UpsertResult`, `SectionInfo` models in `instructions.py`
2. Implement `detect_managed_section()` and `upsert_managed_section()`
3. Refactor `generate_agents_md()` and `generate_claude_md()` to produce
   managed section content only (not full-file content)
4. Create `templates/runloop.md` from stripped-down PROMPT.md
5. Implement constitution manager (`ensure_constitution`, `read_constitution`)
6. Update `cub init` to use upsert + constitution + runloop
7. Extend `cub update` to refresh managed sections
8. Tests for all demarcation edge cases

### Phase 2: Project Map

**Goal:** `cub map` command with structural analysis + code intelligence.

1. Implement `cub.core.map.structure` (directory tree, config parsing, tech
   stack detection)
2. Implement `cub.core.map.code_intel` (grep-ast tag extraction, networkx
   PageRank, diskcache caching)
3. Implement `cub.core.map.renderer` (token-budgeted markdown output)
4. Implement `cub map` CLI command
5. Wire map generation into `cub init` and `cub update`
6. Add `MapConfig` to config system
7. Add dependencies to pyproject.toml
8. Tests for map generation across project types

### Phase 3: Task Prompt Enrichment

**Goal:** Epic context + retry awareness in task prompts.

1. Implement `generate_epic_context()` in run.py
2. Implement `generate_retry_context()` in run.py (reads ledger + log tail)
3. Integrate both into the task prompt generation pipeline
4. Update `generate_system_prompt()` to read from `.cub/runloop.md`
5. Tests for enriched prompts

### Phase 4: Cleanup and Documentation

**Goal:** Remove deprecated files, document the context composition.

1. Remove progress.txt references from all templates and code
2. Remove `templates/guardrails.md`
3. Remove `templates/fix_plan.md`
4. Remove `templates/AGENT.md` (replaced by map)
5. Delete stale progress.txt / progress.md from cub repo
6. Update CLAUDE.md in cub repo to use demarcated format
7. Add context composition documentation to CLAUDE.md
8. Update all affected tests

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `grep-ast` or `tree-sitter-language-pack` have breaking updates | M | L | Pin versions in pyproject.toml; test in CI |
| Token budget produces poor results at extremes (tiny/huge projects) | M | M | Configurable budget; structural layer always present as fallback |
| PageRank ranking misidentifies important symbols | L | M | Structural layer (tree, commands) provides baseline value even if ranking is off |
| `diskcache` SQLite conflicts with concurrent `cub map` runs | L | L | Use separate cache DB per project; handle lock errors gracefully |
| Managed section markers in CLAUDE.md confuse users | L | M | Clear comments; `cub update` warns if manual edits detected |
| `tree-sitter-language-pack` wheel unavailable on some platforms | M | L | Graceful fallback to structural-only map; `--no-code-intel` flag |
| Large monorepos produce maps that exceed budget | M | M | Hard cap at `token_budget`; binary search for optimal file count (Aider's approach) |

## Dependencies

### New External

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| `grep-ast` | >=0.9.0 | MIT | Tree-sitter tag extraction (defs + refs) |
| `networkx` | >=3.2.0 | BSD-3 | PageRank graph ranking |
| `tree-sitter-language-pack` | >=0.13.0 | MIT | Pre-built grammars for 100+ languages |
| `diskcache` | >=5.6.0 | Apache-2.0 | Persistent cache for parsed ASTs |
| `pathspec` | >=0.12.0 | MPL-2.0 | .gitignore pattern matching |

### Existing Internal

- `cub.core.config` — config loading; extended with `MapConfig`
- `cub.core.instructions` — instruction generation; refactored for demarcation
- `cub.core.tasks.backend` — task listing; used for epic context
- `cub.core.ledger.reader` — ledger queries; used for retry context
- `cub.cli.run` — run loop; modified for enriched prompts
- `cub.cli.init_cmd` — init command; modified for upsert behavior
- `cub.cli.update` — update command; extended for managed sections

## Security Considerations

- **No secrets in map.md**: The map generator must never include file contents,
  environment variables, or config values. Only structural information
  (paths, signatures, tech stack).
- **Cache isolation**: `diskcache` stores parsed ASTs in `.cub/cache/`. This
  directory should be in `.gitignore` (no code content in git).
- **Constitution is not a security boundary**: It guides product thinking, not
  access control. Don't rely on it for security constraints.

## Future Considerations

- **Repomix integration**: Alternative extraction backend for projects where
  tree-sitter parsing is insufficient
- **Dynamic token budgeting**: Size the map based on harness context window
- **LLM-assisted descriptions**: Post-process map with LLM for richer module
  descriptions
- **`copilot-instructions.md` generation**: Same managed section at
  `.github/copilot-instructions.md`
- **Map diff**: Show what changed since last map generation (useful for `cub
  update` output)
- **SYSTEM-PLAN.md consolidation**: The existing `PlanContext.read_system_plan()`
  reads `.cub/SYSTEM-PLAN.md`. This should be unified with constitution.md.

---

**Next Step:** Run `cub itemize` to generate implementation tasks.

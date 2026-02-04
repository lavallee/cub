# Architecture Design: Knowledge Retention System

**Date:** 2026-01-22
**Mindset:** Production
**Scale:** Team (10-100 users)
**Status:** Approved

---

## Technical Summary

The Knowledge Retention System adds a three-layer memory architecture to cub: enhanced run artifacts with token/cost persistence, a completed work ledger with LLM-extracted insights, and generated codebase context files.

The system follows cub's established patterns: Pydantic v2 models for data, Typer commands for CLI, file-based storage with markdown + JSONL, and integration through the existing harness interface for LLM operations. Tree-sitter provides AST parsing for codebase mapping.

All components are designed for team-scale usage (10-100 developers sharing repos) with production-quality code: comprehensive test coverage, strict typing, proper error handling, and clear separation of concerns.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Language** | Python 3.10+ | Match existing codebase patterns and tooling |
| **Data Models** | Pydantic v2 | Existing pattern; strict validation with `BaseModel` |
| **CLI Framework** | Typer + Rich | Existing pattern; consistent UX with `cub status`, `cub run` |
| **Storage** | File-based (MD + JSONL) | Per Letta research: 74% on LoCoMo; simple > complex |
| **Frontmatter** | python-frontmatter | Already in deps; proven pattern from captures/ |
| **LLM Integration** | Existing harness | Reuse HarnessBackend for drift detection and extraction |
| **Git Integration** | GitPython | Already in deps; commit info, hooks |
| **AST Parsing** | tree-sitter | Industry standard (Aider, GitHub); accurate structure |

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                 cub run                                       │
│                         (harness execution loop)                              │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐        ┌───────────────┐        ┌───────────────┐
│  TaskResult   │        │  TokenUsage   │        │ HarnessResult │
│ files_changed │        │ input_tokens  │        │    output     │
│ files_created │        │ output_tokens │        │   duration    │
│   messages    │        │   cost_usd    │        │  exit_code    │
└───────┬───────┘        └───────┬───────┘        └───────┬───────┘
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Run Artifacts (Enhanced)                               │
│  .cub/runs/{session}/                                                        │
│  ├── run.json          # now includes budget: {tokens, cost, tasks}          │
│  ├── status.json       # existing real-time status                           │
│  └── tasks/{id}/                                                              │
│      ├── task.json     # now includes usage: TokenUsage                      │
│      ├── harness.log   # NEW: raw harness stdout/stderr                      │
│      └── prompt.md     # NEW: rendered system + task prompt                  │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  │ on bd close / task completion
                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            Ledger Service                                     │
│  src/cub/core/ledger/                                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ models.py                                                               │  │
│  │ ├── LedgerEntry      # Core entry with all fields                      │  │
│  │ ├── LedgerIndex      # JSONL row for fast queries                      │  │
│  │ ├── EpicSummary      # Aggregated epic view                            │  │
│  │ └── DriftReport      # Spec vs ledger comparison                       │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ writer.py                                                               │  │
│  │ ├── create_entry()   # Generate entry from task close                  │  │
│  │ ├── update_entry()   # Add commits, update status                      │  │
│  │ ├── finalize_epic()  # Generate epic summary                           │  │
│  │ └── extract_insights()  # LLM call for approach/decisions              │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ reader.py                                                               │  │
│  │ ├── get_entry()      # Load single entry                               │  │
│  │ ├── list_entries()   # Query with filters                              │  │
│  │ ├── search()         # Full-text search                                │  │
│  │ └── stats()          # Aggregate statistics                            │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ drift.py                                                                │  │
│  │ ├── compare_spec_to_ledger()  # Core drift detection                   │  │
│  │ ├── parse_spec_requirements() # Extract checkable items                │  │
│  │ └── generate_drift_report()   # Format results                         │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Ledger Storage                                      │
│  .cub/ledger/                                                                │
│  ├── index.jsonl           # One line per task: fast queries                 │
│  │   {"id":"cub-abc","title":"...","cost_usd":0.30,"completed":"2026-01-22"}│
│  ├── by-task/                                                                │
│  │   └── {task-id}.md      # Full markdown entry with frontmatter           │
│  └── by-epic/                                                                │
│      └── {epic-id}.md      # Aggregated summary                             │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                         Context Generator                                     │
│  src/cub/core/context/                                                       │
│  ├── generator.py       # Orchestrates context file generation              │
│  ├── llms_txt.py        # llms.txt generation from CLAUDE.md + activity     │
│  └── codebase_map.py    # tree-sitter based structure mapping               │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Context Files                                         │
│  {project}/                                                                  │
│  ├── llms.txt              # LLM-friendly overview (generated)              │
│  └── .cub/codebase-map.md  # Structure + entry points (generated)           │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                           Git Hooks                                           │
│  .git/hooks/                                                                 │
│  └── post-commit           # Installed by cub init                          │
│      ├── Extract Task-Id from commit message                                 │
│      ├── Create/update ledger stub if task found                            │
│      └── Log orphan commit if no task found                                  │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                            CLI Layer                                          │
│  src/cub/cli/ledger.py                                                       │
│  ├── cub ledger show <id>      # Display entry                              │
│  ├── cub ledger stats          # Cost/time aggregates                       │
│  ├── cub ledger search <q>     # Full-text search                           │
│  ├── cub ledger drift <spec>   # Compare spec to ledger                     │
│  └── cub ledger index          # Rebuild index                              │
│                                                                              │
│  src/cub/cli/context.py                                                      │
│  ├── cub context generate      # Generate llms.txt + codebase-map           │
│  └── cub context show          # Display generated context                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Enhanced Run Artifacts

**Purpose:** Persist token/cost data that's currently in-memory only during runs.

**Responsibilities:**
- Save `TokenUsage` to `task.json` after each harness invocation
- Aggregate totals in `run.json` at run completion
- Capture raw harness output to `harness.log`
- Save rendered prompts to `prompt.md`

**Dependencies:** Existing `HarnessResult`, `TaskResult`, `TokenUsage` models

**Interface:** Extensions to existing `StatusWriter` and run loop in `cli/run.py`

**Location:** Modifications to `src/cub/core/status/writer.py` and `src/cub/cli/run.py`

---

### 2. Ledger Service

**Purpose:** Core business logic for completed work ledger operations.

**Responsibilities:**
- Create ledger entries from task completion data
- Extract insights (approach, decisions, lessons) via harness LLM calls
- Maintain JSONL index for fast queries
- Generate epic summaries from constituent tasks
- Perform drift detection against specs

**Dependencies:**
- `HarnessBackend` for LLM extraction and drift detection
- `TaskBackend` for task metadata
- `frontmatter` for markdown parsing
- `GitPython` for commit information

**Interface:**
```python
class LedgerService:
    def create_entry(self, task: Task, result: TaskResult, run_dir: Path) -> LedgerEntry
    def get_entry(self, task_id: str) -> LedgerEntry | None
    def list_entries(self, since: date | None, epic_id: str | None) -> list[LedgerEntry]
    def search(self, query: str) -> list[LedgerEntry]
    def stats(self, since: date | None) -> LedgerStats
    def drift_check(self, spec_path: Path) -> DriftReport
    def finalize_epic(self, epic_id: str) -> EpicSummary
```

**Location:** `src/cub/core/ledger/`

---

### 3. Context Generator

**Purpose:** Generate orientation documents for fast agent context recovery.

**Responsibilities:**
- Generate `llms.txt` from CLAUDE.md template + recent activity
- Generate `.cub/codebase-map.md` using tree-sitter AST parsing
- Identify entry points, key patterns, and structure
- Refresh on demand or after run completion

**Dependencies:**
- `tree-sitter` + language grammars for AST parsing
- Existing `CLAUDE.md` as template
- Recent ledger entries for activity

**Interface:**
```python
class ContextGenerator:
    def generate_llms_txt(self) -> Path
    def generate_codebase_map(self) -> Path
    def regenerate_all(self) -> tuple[Path, Path]
```

**Location:** `src/cub/core/context/`

---

### 4. Git Hook Installer

**Purpose:** Capture commits to ledger even when users bypass `cub run`.

**Responsibilities:**
- Install post-commit hook on `cub init`
- Extract Task-Id from commit messages
- Create/update ledger stubs for linked commits
- Log orphan commits (no Task-Id) for visibility

**Dependencies:**
- `GitPython` for hook installation
- Ledger writer for entry updates

**Interface:**
```python
def install_hooks(project_dir: Path, force: bool = False) -> None
def uninstall_hooks(project_dir: Path) -> None
```

**Location:** `src/cub/core/hooks/installer.py`

---

### 5. Ledger CLI

**Purpose:** User interface for querying and managing the ledger.

**Responsibilities:**
- Display individual entries with rich formatting
- Show aggregate statistics (cost by time period, by epic)
- Search entries by text query
- Run drift detection against specs
- Rebuild index if corrupted

**Dependencies:**
- `LedgerService` for all operations
- `Rich` for terminal output
- `Typer` for CLI framework

**Interface:**
```
cub ledger show <task-id>              # Display entry
cub ledger show <task-id> --json       # JSON output
cub ledger stats                       # All-time stats
cub ledger stats --since 2026-01-01    # Date-filtered stats
cub ledger stats --epic <id>           # Epic-specific stats
cub ledger search "authentication"     # Full-text search
cub ledger drift specs/auth.md         # Drift check
cub ledger index --rebuild             # Rebuild index
```

**Location:** `src/cub/cli/ledger.py`

## Data Model

### LedgerEntry

```python
class LedgerEntry(BaseModel):
    """A completed work record for a single task."""

    # Identity
    id: str                              # Task ID (e.g., "cub-abc")
    title: str                           # Task title
    epic_id: str | None                  # Parent epic if applicable

    # Timing
    started_at: datetime                 # When work began
    completed_at: datetime               # When task closed
    duration_seconds: int                # Total execution time

    # Cost
    tokens: TokenUsage                   # Detailed token breakdown
    iterations: int                      # Number of harness invocations

    # Files
    files_changed: list[str]             # Modified files
    files_created: list[str]             # New files
    commits: list[CommitRef]             # Associated commits

    # Intent & Outcome (structured)
    original_description: str            # From task/beads
    acceptance_criteria: list[str]       # From task
    spec_path: str | None                # Link to spec if exists

    # Insights (LLM-extracted)
    approach_taken: str                  # Summary of how it was done
    key_decisions: list[str]             # Important choices made
    lessons_learned: list[str]           # What was learned

    # Metadata
    run_session: str                     # Run session ID
    harness: str                         # Which harness was used
    model: str | None                    # Model used (sonnet, opus, etc.)

    # Status
    verification: VerificationStatus     # Tests pass, manual check, etc.
```

### LedgerIndex (JSONL row)

```python
class LedgerIndex(BaseModel):
    """Compact index entry for fast queries."""

    id: str
    title: str
    epic_id: str | None
    completed_at: date
    cost_usd: float
    tokens_total: int
    files_count: int
    commits_count: int
    spec_path: str | None
```

### CommitRef

```python
class CommitRef(BaseModel):
    """Reference to a git commit."""

    hash: str                            # Short hash (7 chars)
    message: str                         # First line of commit message
    timestamp: datetime
    files: list[str]
```

### DriftReport

```python
class DriftReport(BaseModel):
    """Result of comparing a spec to ledger entries."""

    spec_path: Path
    generated_at: datetime

    # Categorized requirements
    implemented_as_specified: list[RequirementMatch]
    diverged_documented: list[RequirementDivergence]  # Has explanation
    diverged_undocumented: list[RequirementDivergence]  # No explanation
    not_implemented: list[str]
    out_of_scope: list[str]

    # Summary
    total_requirements: int
    match_percentage: float
    action_items: list[str]
```

### Relationships

```
Task (beads) ──────────────────┬─────────────────────► LedgerEntry
  │                            │                         │
  │ parent                     │ creates                 │ references
  ▼                            │                         ▼
Epic ◄─────────────────────────┴────────── aggregates ── EpicSummary
  │                                                      │
  │ spec_path                                            │ compares
  ▼                                                      ▼
Spec (markdown) ◄────────────────────────────────────── DriftReport
```

## APIs / Interfaces

### Internal Python API

```python
# Ledger Operations
from cub.core.ledger import LedgerService

service = LedgerService(project_dir=Path("."))
entry = service.create_entry(task, result, run_dir)
entry = service.get_entry("cub-abc")
entries = service.list_entries(since=date(2026, 1, 1))
stats = service.stats(epic_id="nxa6f")
report = service.drift_check(Path("specs/auth.md"))

# Context Generation
from cub.core.context import ContextGenerator

gen = ContextGenerator(project_dir=Path("."))
gen.generate_llms_txt()
gen.generate_codebase_map()
```

### CLI Interface

```bash
# Ledger Commands
cub ledger show cub-abc                    # Rich formatted display
cub ledger show cub-abc --json             # JSON for scripting
cub ledger stats                           # Aggregate stats
cub ledger stats --since 2026-01-01        # Date filter
cub ledger stats --epic nxa6f              # Epic filter
cub ledger stats --json                    # JSON output
cub ledger search "authentication"         # Full-text search
cub ledger drift specs/auth.md             # Drift detection
cub ledger index --rebuild                 # Rebuild JSONL index

# Context Commands
cub context generate                       # Generate all context files
cub context generate --llms-txt            # Only llms.txt
cub context generate --codebase-map        # Only codebase map
cub context show                           # Display generated context
```

### JSON Output Format

```json
// cub ledger show cub-abc --json
{
  "id": "cub-abc",
  "title": "Implement user authentication",
  "completed_at": "2026-01-22T14:30:00Z",
  "duration_seconds": 2700,
  "tokens": {
    "input_tokens": 45000,
    "output_tokens": 12000,
    "cost_usd": 0.30
  },
  "files_changed": ["src/auth/middleware.ts"],
  "approach_taken": "Used JWT with refresh tokens...",
  "key_decisions": ["Chose 24h expiry over 1h"],
  "lessons_learned": ["bcrypt.compare is async"]
}

// cub ledger stats --json
{
  "total_entries": 156,
  "total_cost_usd": 47.32,
  "total_tokens": 15000000,
  "by_epic": {
    "nxa6f": {"entries": 12, "cost_usd": 3.50}
  },
  "by_month": {
    "2026-01": {"entries": 45, "cost_usd": 12.30}
  }
}
```

## Implementation Phases

### Phase 1: Token Persistence
**Goal:** Persist token/cost data that currently exists only in-memory

**Tasks:**
- Extend `task.json` schema in `core/status/models.py` to include `usage: TokenUsage`
- Extend `run.json` schema to include `budget: BudgetStatus` totals
- Modify `cli/run.py` to write `harness.log` (raw output capture)
- Modify `cli/run.py` to write `prompt.md` (rendered prompts)
- Update `StatusWriter` to persist token data on each task completion
- Update `cub status` to display cost breakdown from persisted data

**Deliverables:**
- Token data persisted in `.cub/runs/` artifacts
- `cub status` shows accurate cost even after run completes
- Audit trail for prompt debugging

---

### Phase 2: Ledger Core
**Goal:** Create the completed work ledger with entries and queries

**Tasks:**
- Create `src/cub/core/ledger/` package structure
- Define Pydantic models: `LedgerEntry`, `LedgerIndex`, `EpicSummary`
- Implement `LedgerWriter` for creating/updating entries
- Implement JSONL index maintenance
- Implement LLM extraction for approach/decisions/lessons via harness
- Implement `LedgerReader` for queries and search
- Create `src/cub/cli/ledger.py` with show/stats/search commands
- Wire into run loop: create entry on task close (after `bd close`)
- Add `--json` flag support for all commands

**Deliverables:**
- `.cub/ledger/` directory structure populated on task completion
- `cub ledger show/stats/search` commands working
- LLM-extracted insights in entries

---

### Phase 3: Context & Drift
**Goal:** Add context generation and drift detection

**Tasks:**
- Add `tree-sitter` dependency with Python grammar
- Implement `CodebaseMapper` using tree-sitter for structure extraction
- Implement `LlmsTxtGenerator` for llms.txt from CLAUDE.md + activity
- Create `src/cub/core/context/` package
- Implement drift detection: `compare_spec_to_ledger()` via harness
- Define `DriftReport` model and CLI output formatting
- Create `src/cub/cli/context.py` with generate/show commands
- Add `cub ledger drift <spec>` command
- Implement git post-commit hook installer
- Wire context regeneration to end of `cub run`

**Deliverables:**
- `llms.txt` and `.cub/codebase-map.md` generated on demand
- `cub ledger drift` working with meaningful reports
- Git hooks installed on `cub init`

---

### Phase 4: Epic Summaries & Polish
**Goal:** Add aggregation and production polish

**Tasks:**
- Implement `finalize_epic()` for epic summary generation
- Generate `.cub/ledger/by-epic/{id}.md` when epic completes
- Add `cub ledger epic <id>` command
- Add date-based index sharding if needed (likely not for team scale)
- Comprehensive test coverage (target 60%+)
- Documentation in CLAUDE.md
- Performance optimization if needed

**Deliverables:**
- Epic summaries with cost/time aggregation
- Production-ready code with tests
- Documentation complete

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LLM extraction quality varies | Medium | Medium | Tune prompts; allow manual override; make fields optional |
| Drift detection false positives | High | Medium | Position as advisory; require human review; tune prompts |
| Tree-sitter grammar installation | Low | Medium | Bundle common grammars; graceful fallback to file tree |
| JSONL index grows large | Medium | Low | Date-based sharding; for team scale unlikely to matter |
| Git hooks conflict with CI | Low | Low | No-op on error; check for cub init; disable flag |
| Harness rate limits during extraction | Medium | Low | Use fast model (Haiku); batch if needed; cache results |

## Dependencies

### External (New)

| Dependency | Version | Purpose |
|------------|---------|---------|
| tree-sitter | ^0.21.0 | AST parsing for codebase map |
| tree-sitter-python | ^0.21.0 | Python grammar |
| tree-sitter-javascript | ^0.21.0 | JS/TS grammar |

### Internal (Existing)

| Dependency | Purpose |
|------------|---------|
| `HarnessBackend` | LLM calls for extraction and drift |
| `TaskBackend` | Task metadata for entries |
| `TokenUsage` | Cost tracking (already exists) |
| `frontmatter` | Markdown with metadata |
| `GitPython` | Commit info, hook installation |
| `Rich` | CLI output formatting |

## Security Considerations

**For Production/Team scale:**

- **No secrets in ledger entries** - Filter out env vars, API keys from extracted content
- **Harness output sanitization** - Apply existing guardrail patterns to harness.log
- **Hook safety** - Hooks fail silently (no-op on error), don't block commits
- **File permissions** - Ledger files follow project permissions; no special handling needed
- **Cost data privacy** - Cost/token data is sensitive; consider gitignore for teams that don't want to share

## Future Considerations

**Explicitly deferred:**

- **Cross-project knowledge base** - Aggregate learnings across repos
- **External observability export** - OpenTelemetry GenAI format for Langfuse/Grafana
- **Real-time dashboards** - Web UI for ledger visualization
- **Automatic spec updates** - Update specs from drift reports
- **Guardrail auto-generation** - Promote repeated lessons to guardrails
- **Constitutional principles** - High-confidence rules from ledger patterns

**Keep in mind for future:**

- Index format should be extensible (JSONL makes this easy)
- Ledger entry format should version (add `version` field to frontmatter)
- Tree-sitter grammars can be extended for more languages
- Harness abstraction allows swapping LLM providers easily

---

**Next Step:** Run `cub plan itemize` to generate implementation tasks.

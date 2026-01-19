# Language Migration Strategy

**Source:** Original analysis of cub codebase
**Dependencies:** None (can be done incrementally)
**Complexity:** High (phased approach recommended)

## Overview

Cub is currently ~9,400 lines of Bash across 21 library files. While well-engineered, Bash imposes performance and maintainability limits that will constrain future features.

This spec outlines a migration strategy to Python and/or Go for performance-critical components while preserving Bash's strengths for extensibility.

## Current State Analysis

### Codebase by Size

| File | Lines | Category | Migration Priority |
|------|-------|----------|-------------------|
| cmd_run.sh | 1,200 | Core loop | Medium |
| harness.sh | 1,161 | AI backends | High |
| tasks.sh | 937 | Task management | Critical |
| git.sh | 912 | Git operations | High |
| artifacts.sh | 842 | File I/O | Medium |
| budget.sh | 673 | Token tracking | Low |
| logger.sh | 461 | Logging | Low |
| cmd_doctor.sh | 443 | Diagnostics | Low |
| beads.sh | 376 | Beads wrapper | Critical (with tasks) |
| Others | ~2,400 | Various | Keep as Bash |

### Performance Bottlenecks

| Operation | Current Approach | Problem | Frequency |
|-----------|------------------|---------|-----------|
| JSON parsing | jq subprocess per field | ~10-100 jq calls/iteration | Every task |
| Git status | Multiple git calls | 5-10 git calls/iteration | Every task |
| Config access | File-based cache + jq | Disk I/O + subprocess | Throughout |
| Stream parsing | Line-by-line bash read | Unbuffered, slow | Harness output |
| Dependency resolution | jq queries in loops | O(n²) with subprocesses | Task selection |

### Why Migrate?

**Performance:**
- jq subprocess: ~10-50ms per invocation
- 100 jq calls = 1-5 seconds overhead per iteration
- Git subprocess: ~20-100ms per call
- File I/O for state: unnecessary latency

**Maintainability:**
- No type safety
- Error handling is verbose
- Complex string parsing
- Difficult to test in isolation

**New Features:**
- Parallel task execution needs proper concurrency
- Sandbox provider abstraction needs clean interfaces
- Verification protocol needs structured data
- Dashboard needs real-time state access

---

## Language Comparison

### Python

**Pros:**
- Rapid development
- Excellent JSON/YAML libraries
- Rich ecosystem (GitPython, click, rich)
- Easy to read and maintain
- Good for prototyping
- Can call existing bash scripts

**Cons:**
- Slower than Go for CPU-bound work
- GIL limits true parallelism
- Startup time (~50-100ms)
- Dependency management (venv, pip)
- Distribution complexity

**Best for:**
- Complex data transformation
- AI/ML adjacent features
- Rapid iteration
- Teams familiar with Python

### Go

**Pros:**
- Fast execution (compiled)
- Single binary distribution
- Excellent concurrency (goroutines)
- Strong typing
- Fast startup (~5ms)
- go-git library is mature
- Cross-compilation easy

**Cons:**
- More verbose than Python
- Slower development iteration
- Error handling verbosity
- Less flexible for scripting

**Best for:**
- Performance-critical paths
- CLI tools (single binary)
- Concurrent operations
- Long-running processes

### Recommendation: Hybrid Approach

```
┌─────────────────────────────────────────────────────────────┐
│                        CUB ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────┤
│  BASH (keep)           │  GO (core)           │  PYTHON     │
│  ─────────────         │  ────────            │  (optional) │
│  • CLI entry point     │  • Task engine       │  • Pipeline │
│  • Hook execution      │  • Harness layer     │    stages   │
│  • Installation        │  • Config system     │  • AI-heavy │
│  • Simple utilities    │  • Git operations    │    features │
│                        │  • Artifact mgmt     │  • Plugins  │
│                        │  • State management  │             │
└─────────────────────────────────────────────────────────────┘
```

**Rationale:**
- **Go for core**: Performance-critical, runs frequently, benefits from single binary
- **Bash for glue**: Hook system extensibility, installation, CLI dispatch
- **Python for AI features**: Vision-to-Tasks pipeline, AI-assisted review (optional)

---

## Migration Phases

### Phase 1: Core Data Layer (Go)

**Target:** Task management + Configuration
**Files:** tasks.sh, beads.sh, config.sh
**Current:** ~1,500 lines Bash
**Estimated:** ~400 lines Go

**Why first:**
- Highest jq usage (biggest perf win)
- Clean interface boundary
- No UI/harness dependencies
- Easy to test in isolation

**Interface:**
```go
// cub-core (Go binary)

// Task operations
cub-core tasks list [--status open] [--label X]
cub-core tasks get <id>
cub-core tasks ready [--epic X] [--label X]
cub-core tasks update <id> --status X
cub-core tasks deps <id>

// Config operations
cub-core config get <key>
cub-core config set <key> <value>
cub-core config dump

// Output: JSON to stdout
```

**Bash integration:**
```bash
# Before (slow)
task_json=$(jq ".tasks[] | select(.id == \"$id\")" prd.json)
task_title=$(echo "$task_json" | jq -r '.title')

# After (fast)
task_json=$(cub-core tasks get "$id")
task_title=$(echo "$task_json" | jq -r '.title')  # Single jq call
# Or even better:
task_title=$(cub-core tasks get "$id" --field title)
```

**Performance gain:** 10-50x for task operations

---

### Phase 2: Harness Layer (Go)

**Target:** AI backend abstraction
**Files:** harness.sh
**Current:** ~1,161 lines Bash
**Estimated:** ~350 lines Go

**Why second:**
- Stream parsing is slow in Bash
- Token counting needs precision
- Multiple backends benefit from interfaces
- Enables parallel harness calls (future)

**Interface:**
```go
// cub-harness (Go binary)

// Invoke harness
cub-harness invoke --harness claude --prompt-file /tmp/prompt.md [--stream]
cub-harness invoke --harness codex --prompt "..." --model gpt-4

// Output: JSON with result + token usage
{
  "output": "...",
  "tokens": {"input": 1234, "output": 567},
  "model": "claude-sonnet-4",
  "duration_ms": 4500
}
```

**Streaming:**
```go
// Stream mode outputs JSONL
{"type": "content", "text": "..."}
{"type": "content", "text": "..."}
{"type": "done", "tokens": {...}}
```

**Performance gain:** 2-5x for stream parsing, better token accuracy

---

### Phase 3: Git Operations (Go)

**Target:** Git workflow
**Files:** git.sh
**Current:** ~912 lines Bash
**Estimated:** ~300 lines Go

**Why third:**
- go-git library is excellent
- Batch operations possible
- Reduces subprocess overhead
- Enables richer git analysis

**Interface:**
```go
// cub-git (Go binary)

cub-git status              // Combined status in one call
cub-git commit --message "..." --paths file1,file2
cub-git branch --create "cub/session/..."
cub-git diff [--cached] [--name-only]
```

**Performance gain:** 3-5x fewer subprocess calls

---

### Phase 4: Artifact Management (Go)

**Target:** File I/O and state
**Files:** artifacts.sh, state.sh, session.sh
**Current:** ~1,200 lines Bash
**Estimated:** ~250 lines Go

**Why fourth:**
- Batch file operations
- Structured templates
- State can be in-memory
- Enables artifact caching

---

### Phase 5: Core Loop (Go or keep Bash)

**Target:** Main orchestration
**Files:** cmd_run.sh
**Current:** ~1,200 lines Bash
**Decision:** Evaluate after phases 1-4

**Options:**
1. **Keep as Bash** - Orchestrates Go binaries, keeps flexibility
2. **Rewrite in Go** - Full performance, but less hackable
3. **Hybrid** - Go daemon with Bash control scripts

---

## Alternative: Single Go Binary

Instead of multiple binaries, could build single `cub` binary in Go:

```
cub (Go binary)
├── cub run [options]
├── cub tasks [subcommand]
├── cub config [subcommand]
├── cub git [subcommand]
├── cub harness [subcommand]
└── cub hooks [run bash hooks]
```

**Pros:**
- Single distribution
- Shared memory/state
- Faster inter-component calls
- Consistent error handling

**Cons:**
- Bigger rewrite
- Lose Bash flexibility
- Hook system needs care
- Longer before any benefits

**Recommendation:** Start with separate binaries, unify later if beneficial.

---

## Python for Pipeline Features

The Vision-to-Tasks Pipeline (triage, architect, plan, bootstrap) is a good candidate for Python:

**Why Python for pipeline:**
- Heavy AI interaction (prompt engineering)
- Complex document parsing
- Template generation
- Less performance-critical (runs once per project)
- Easier to iterate on prompts/flows

**Interface:**
```bash
# Python handles pipeline stages
cub-pipeline triage VISION.md --output .cub/sessions/xxx/triage.md
cub-pipeline architect --session xxx
cub-pipeline plan --session xxx --granularity micro
cub-pipeline bootstrap --session xxx
```

**Or as library:**
```python
# cub_pipeline/triage.py
from cub_pipeline import Triage, Architect, Planner, Bootstrap

triage = Triage(input_file="VISION.md")
result = triage.run(depth="standard")
result.save(".cub/sessions/xxx/triage.md")
```

---

## Distribution Strategy

### Current (Bash)
```bash
curl -fsSL .../install.sh | bash
# Copies scripts to ~/.local/bin/
```

### With Go Binaries
```bash
# Option 1: Download prebuilt
curl -fsSL .../install.sh | bash
# Downloads platform-specific binaries

# Option 2: Homebrew
brew install cub

# Option 3: Go install
go install github.com/lavallee/cub@latest
```

### With Python Components
```bash
# Option 1: Bundled (pyinstaller)
# Single binary includes Python runtime

# Option 2: pip install
pip install cub-pipeline

# Option 3: pipx (isolated)
pipx install cub-pipeline
```

---

## Migration Path

### Incremental Approach (Recommended)

```
Month 1-2: Phase 1 (Task + Config in Go)
├── Build cub-core binary
├── Update tasks.sh to call cub-core
├── Maintain backward compatibility
└── Measure performance improvement

Month 2-3: Phase 2 (Harness in Go)
├── Build cub-harness binary
├── Update harness.sh to call cub-harness
├── Test all 4 backends
└── Verify token counting accuracy

Month 3-4: Phase 3-4 (Git + Artifacts in Go)
├── Build cub-git binary
├── Build cub-artifacts binary
├── Update respective .sh files
└── Full integration testing

Month 4+: Evaluate
├── Measure total performance gain
├── Decide on core loop migration
├── Consider single binary unification
└── Python pipeline if needed
```

### Parallel Development

Can develop Go components in parallel with Bash improvements:
- Go team works on cub-core
- Bash maintenance continues
- Integration happens when Go ready
- No big-bang cutover

---

## File Structure (Post-Migration)

```
cub/
├── cmd/                    # Go binaries
│   ├── cub-core/          # Task + config
│   ├── cub-harness/       # AI backends
│   ├── cub-git/           # Git operations
│   └── cub-artifacts/     # File management
├── pkg/                    # Go libraries
│   ├── tasks/
│   ├── config/
│   ├── harness/
│   └── git/
├── lib/                    # Bash libraries (reduced)
│   ├── hooks.sh           # Keep - extensibility
│   ├── cmd_run.sh         # Keep or migrate
│   └── ...
├── python/                 # Python components (optional)
│   └── cub_pipeline/
│       ├── triage.py
│       ├── architect.py
│       ├── planner.py
│       └── bootstrap.py
├── bin/
│   └── cub                # Entry point (Bash or Go)
└── tests/
    ├── bats/              # Bash tests (keep)
    └── go/                # Go tests
```

---

## Metrics to Track

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| Task list time | ~500ms | <50ms | `time cub-core tasks list` |
| Config access | ~50ms | <5ms | `time cub-core config get X` |
| Git status | ~200ms | <50ms | `time cub-git status` |
| Stream parse | ~100ms/line | <10ms/line | Benchmark harness output |
| Startup time | ~100ms | <20ms | `time cub --version` |
| Memory (idle) | ~50MB | <20MB | Process monitoring |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking changes | Maintain Bash fallback during transition |
| Distribution complexity | Use goreleaser for multi-platform builds |
| Test coverage gaps | Port BATS tests to Go test framework |
| Hook compatibility | Keep hook execution in Bash |
| User disruption | Semantic versioning, clear upgrade path |

---

## Acceptance Criteria

### Phase 1 Complete
- [ ] cub-core binary handles all task operations
- [ ] tasks.sh calls cub-core instead of jq
- [ ] 10x performance improvement on task list
- [ ] All existing tests pass
- [ ] Works on Linux and macOS

### Full Migration Complete
- [ ] All Go binaries functional
- [ ] Bash reduced to ~3,000 lines (hooks, CLI, utils)
- [ ] Performance targets met
- [ ] Single-command installation works
- [ ] Documentation updated

---

## Summary

| Component | Language | Reason |
|-----------|----------|--------|
| Task management | **Go** | Performance-critical, heavy JSON |
| Harness layer | **Go** | Stream parsing, concurrency |
| Config system | **Go** | Frequent access, caching |
| Git operations | **Go** | go-git library, batching |
| Artifacts | **Go** | File I/O, templates |
| Core loop | **Bash or Go** | TBD after phases 1-4 |
| Hooks | **Bash** | Extensibility, simplicity |
| CLI dispatch | **Bash** | Flexibility |
| Pipeline stages | **Python** | AI-heavy, iteration speed |
| Verification | **Python** | Plugin ecosystem |

**Expected outcome:** 40-50% code reduction, 10-100x performance improvement on hot paths, better maintainability, enables advanced features (parallelism, dashboard, sandbox).

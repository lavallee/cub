---
status: researching
priority: high
complexity: medium
dependencies: []
blocks: []
created: 2026-01-20
updated: 2026-01-20
readiness:
  score: 7
  blockers:
    - Decide on retention policy (how long to keep runs)
    - Clarify streaming token tracking approach
  questions:
    - Should we persist full message history or just summaries?
    - What's the right balance between detail and disk usage?
    - Should run artifacts be gitignored or committed?
    - How to handle multi-harness runs (SDK + streaming fallback)?
  decisions_needed:
    - Define artifact retention policy (7 days? 30 days? manual cleanup?)
    - Choose between full message logs vs summary-only
    - Decide on JSONL vs JSON for task execution records
  tools_needed: []
notes: |
  The bash version had comprehensive run tracking via lib/artifacts.sh.
  Python migration only implemented status.json (StatusWriter).
  This spec aims to restore full tracking with improvements.

  Historical tracking was in .cub/runs/{session}/tasks/{task-id}/ with:
  - harness_output.log, changes.patch, summary.md, commands.jsonl

  Current Python tracking writes only .cub/runs/{run_id}/status.json
---

# Run Tracking System

## Overview

A comprehensive system for tracking task execution, capturing harness output, token usage, costs, and file changes during `cub run` sessions. This restores and improves upon the tracking that existed in the bash version but was lost during the Python migration.

**Problem:** When debugging failed tasks or reviewing AI output, there's no persistent record of what happened. Token costs are tracked in aggregate but not per-task. Harness output is displayed but not saved.

**Solution:** Extend the existing `.cub/runs/` infrastructure to capture detailed execution records at both run and task levels.

## Goals

1. **Audit trail** - Full record of what each task attempted and produced
2. **Token accountability** - Per-task token usage and cost tracking
3. **Debugging support** - Harness output preserved for post-mortem analysis
4. **Progress visibility** - Real-time status (already exists via StatusWriter)
5. **Minimal overhead** - Don't slow down execution with heavy I/O

## Non-Goals

- Real-time streaming to external systems (use existing JSONL logger for that)
- Building a full observability platform
- Historical analytics across many runs (future enhancement)
- Compression or archival of old runs (manual for now)

---

## Current State Analysis

### What Exists (Python)

**StatusWriter** (`src/cub/core/status/writer.py`):
- Writes `.cub/runs/{run_id}/status.json`
- Atomic writes via temp file + rename
- Contains: run phase, iteration count, budget status, task stats, event log

**Status Models** (`src/cub/core/status/models.py`):
- `RunStatus`: Top-level with budget, events, current task
- `BudgetStatus`: tokens_used, tokens_limit, cost_usd, tasks_completed
- `EventLog`: timestamped events with severity

**Harness Models** (`src/cub/core/harness/models.py`):
- `TokenUsage`: input/output/cache tokens, cost_usd
- `HarnessResult`: output, usage, duration, exit_code, error
- `TaskResult`: extends HarnessResult with messages, files_changed

**Run Loop** (`src/cub/cli/run.py`):
- Captures `HarnessResult` with full token usage
- Updates aggregate budget in status.json
- Logs events to `status.events`
- **Does NOT persist**: harness output, per-task records, message history

### What Existed (Bash)

**lib/artifacts.sh** provided:
```
.cub/runs/{session}/
├── run.json                    # Run-level metadata
├── status.json                 # Real-time status
└── tasks/
    └── {task-id}/
        ├── task.json           # Task metadata (started_at, status, iterations)
        ├── harness_output.log  # Raw AI harness output
        ├── changes.patch       # Git diff of changes
        ├── summary.md          # Human-readable task summary
        ├── plan.md             # Task plan (if captured)
        └── commands.jsonl      # Commands executed (JSONL format)
```

### Gaps

| Feature | Bash | Python | Gap |
|---------|------|--------|-----|
| Run metadata | ✅ run.json | ✅ status.json | - |
| Real-time status | ✅ | ✅ StatusWriter | - |
| Per-task directory | ✅ | ❌ | Need task artifacts |
| Harness output | ✅ harness_output.log | ❌ | **Critical gap** |
| Token per task | ❌ | ❌ (aggregate only) | Enhancement |
| File changes | ✅ changes.patch | ❌ | Nice to have |
| Task execution record | ✅ task.json | ❌ | **Critical gap** |
| Summary generation | ✅ summary.md | ❌ | Nice to have |
| JSONL logger integration | ✅ | ❌ (exists but not wired) | Easy fix |
| Message history | ❌ | ❌ (captured, not saved) | Enhancement |

---

## Proposed Design

### Directory Structure

```
.cub/runs/
└── {run_id}/
    ├── run.json                    # Run-level metadata (enhanced)
    ├── status.json                 # Real-time status (existing)
    └── tasks/
        └── {task_id}/
            ├── execution.json      # Task execution record
            ├── output.log          # Raw harness output (text)
            ├── messages.jsonl      # Message history (optional)
            └── changes.patch       # Git diff (optional)
```

### Data Models

#### RunMetadata (run.json)

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class RunMetadata(BaseModel):
    """Persisted run-level metadata"""
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str  # "running", "completed", "failed", "stopped"

    # Configuration snapshot
    harness: str
    model: Optional[str] = None
    max_iterations: int
    budget_tokens: Optional[int] = None
    budget_cost: Optional[float] = None

    # Aggregate results
    tasks_attempted: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0

    # Total usage
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0

    # Environment
    working_directory: str
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
```

#### TaskExecution (execution.json)

```python
class TaskExecution(BaseModel):
    """Per-task execution record"""
    task_id: str
    run_id: str

    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Status
    status: str  # "running", "completed", "failed", "skipped"
    exit_code: Optional[int] = None
    error: Optional[str] = None

    # Token usage (per-task breakdown)
    tokens: Optional[TokenUsage] = None

    # What changed
    files_changed: list[str] = []
    files_created: list[str] = []

    # Iteration tracking
    iterations: int = 0

    # References
    output_file: Optional[str] = None  # Relative path to output.log
    messages_file: Optional[str] = None  # Relative path to messages.jsonl
    changes_file: Optional[str] = None  # Relative path to changes.patch
```

### Writer Interface

```python
class RunArtifacts:
    """Manages run artifacts directory"""

    def __init__(self, run_id: str, base_dir: Path = None):
        self.run_id = run_id
        self.base_dir = base_dir or Path(".cub/runs")
        self.run_dir = self.base_dir / run_id

    def initialize(self, metadata: RunMetadata) -> None:
        """Create run directory and write initial metadata"""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(self.run_dir / "run.json", metadata)

    def start_task(self, task_id: str) -> TaskArtifacts:
        """Create task artifacts subdirectory"""
        task_dir = self.run_dir / "tasks" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return TaskArtifacts(task_dir, task_id, self.run_id)

    def finalize(self, metadata: RunMetadata) -> None:
        """Write final run metadata"""
        self._write_json(self.run_dir / "run.json", metadata)


class TaskArtifacts:
    """Manages per-task artifacts"""

    def __init__(self, task_dir: Path, task_id: str, run_id: str):
        self.task_dir = task_dir
        self.task_id = task_id
        self.run_id = run_id
        self._output_handle: Optional[TextIO] = None

    def start(self, execution: TaskExecution) -> None:
        """Initialize task execution record"""
        self._write_json(self.task_dir / "execution.json", execution)
        self._output_handle = open(self.task_dir / "output.log", "w")

    def append_output(self, text: str) -> None:
        """Append to harness output log (streaming-friendly)"""
        if self._output_handle:
            self._output_handle.write(text)
            self._output_handle.flush()

    def write_messages(self, messages: list[dict]) -> None:
        """Write message history as JSONL"""
        with open(self.task_dir / "messages.jsonl", "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

    def write_changes(self, patch: str) -> None:
        """Write git diff of changes"""
        (self.task_dir / "changes.patch").write_text(patch)

    def finalize(self, execution: TaskExecution) -> None:
        """Write final task execution record"""
        if self._output_handle:
            self._output_handle.close()
            self._output_handle = None
            execution.output_file = "output.log"

        if (self.task_dir / "messages.jsonl").exists():
            execution.messages_file = "messages.jsonl"

        if (self.task_dir / "changes.patch").exists():
            execution.changes_file = "changes.patch"

        self._write_json(self.task_dir / "execution.json", execution)
```

---

## Integration Points

### In run.py

```python
# At run start
artifacts = RunArtifacts(run_id)
artifacts.initialize(RunMetadata(
    run_id=run_id,
    started_at=datetime.now(),
    harness=harness_name,
    model=model,
    max_iterations=config.max_iterations,
    ...
))

# At task start
task_artifacts = artifacts.start_task(task.id)
task_execution = TaskExecution(
    task_id=task.id,
    run_id=run_id,
    started_at=datetime.now(),
    status="running"
)
task_artifacts.start(task_execution)

# During task execution (streaming output)
task_artifacts.append_output(output_chunk)

# At task completion
task_execution.status = "completed" if result.success else "failed"
task_execution.completed_at = datetime.now()
task_execution.duration_seconds = result.duration_seconds
task_execution.tokens = result.usage
task_execution.exit_code = result.exit_code
task_execution.error = result.error
task_execution.files_changed = result.files_changed or []

# Write message history if available
if hasattr(result, 'messages') and result.messages:
    task_artifacts.write_messages([m.model_dump() for m in result.messages])

# Capture git diff
patch = subprocess.run(
    ["git", "diff", "HEAD~1"],
    capture_output=True, text=True
).stdout
if patch.strip():
    task_artifacts.write_changes(patch)

task_artifacts.finalize(task_execution)

# At run end
run_metadata.completed_at = datetime.now()
run_metadata.status = "completed"
run_metadata.total_tokens = status.budget.tokens_used
run_metadata.total_cost_usd = status.budget.cost_usd
artifacts.finalize(run_metadata)
```

### Wire CubLogger (Quick Win)

In `src/cub/cli/run.py`, wire the existing JSONL logger:

```python
from cub.utils.logging import CubLogger, EventType

# At run start
logger = CubLogger(project_id, run_id)
logger.write(EventType.LOOP_START, {
    "harness": harness_name,
    "max_iterations": config.max_iterations
})

# At task start
logger.task_start(task.id, task.title)

# At task end
logger.task_end(task.id, success=result.success, tokens=result.usage.total_tokens)

# On budget warning
logger.budget_warning(tokens_used, tokens_limit)

# At run end
logger.write(EventType.LOOP_END, {
    "tasks_completed": tasks_completed,
    "total_tokens": total_tokens
})
```

---

## Streaming Token Tracking

Currently, streaming mode uses empty `TokenUsage()` with comment "Usage tracking TBD for streaming".

**Options:**

1. **Count from SDK events** - If the streaming API emits usage events, capture them
2. **Estimate from output length** - Rough estimate based on character count (inaccurate)
3. **Post-hoc API call** - Query usage after streaming completes (if API supports)
4. **Accept gap** - Document that streaming doesn't track tokens

**Recommendation:** Option 1 if SDK supports it, otherwise Option 4 with clear documentation.

---

## Retention Policy

Runs accumulate over time. Options:

1. **Manual cleanup** - User runs `cub runs cleanup` or deletes manually
2. **Time-based** - Delete runs older than N days automatically
3. **Count-based** - Keep last N runs, delete older
4. **Size-based** - Delete when .cub/runs exceeds N MB

**Recommendation:** Start with Option 1 (manual), add `cub runs cleanup --older-than 30d` command.

---

## CLI Commands

### Viewing Runs

```bash
# List recent runs
cub runs list
cub runs list --limit 10

# Show run details
cub runs show {run_id}
cub runs show --latest

# Show task execution details
cub runs task {run_id} {task_id}

# View harness output
cub runs output {run_id} {task_id}
cub runs output --latest --task {task_id}

# View message history
cub runs messages {run_id} {task_id}
```

### Cleanup

```bash
# Delete old runs
cub runs cleanup --older-than 30d
cub runs cleanup --keep 10  # Keep last 10

# Delete specific run
cub runs delete {run_id}
```

---

## Implementation Plan

### Phase 1: Core Tracking (MVP)
- [ ] Create `RunArtifacts` and `TaskArtifacts` classes
- [ ] Add `RunMetadata` and `TaskExecution` models
- [ ] Integrate into run.py at task start/end
- [ ] Capture harness output to output.log
- [ ] Write per-task execution.json

### Phase 2: Enhanced Data
- [ ] Wire CubLogger JSONL logging
- [ ] Capture message history for SDK harness
- [ ] Capture git diff for completed tasks
- [ ] Add file change tracking

### Phase 3: CLI & Cleanup
- [ ] Add `cub runs list` command
- [ ] Add `cub runs show` command
- [ ] Add `cub runs output` command
- [ ] Add `cub runs cleanup` command

### Phase 4: Polish
- [ ] Address streaming token tracking
- [ ] Add retention policy configuration
- [ ] Documentation

---

## Open Questions

1. **Message history size** - Full conversation can be large. Store all or summarize?
   - **Lean:** Store all for SDK (it's structured), skip for shell-out (just text)

2. **Git diff scope** - Diff since task start vs diff of final commit?
   - **Lean:** Diff of staged/unstaged changes at task completion

3. **gitignore** - Should .cub/runs/ be gitignored?
   - **Lean:** Yes, runs are local artifacts, not shared

4. **Multi-iteration tasks** - How to track iterations within a task?
   - **Lean:** Single execution.json with iteration count, append to output.log

---

## Success Criteria

- [ ] Every task execution has a persistent record in .cub/runs/
- [ ] Harness output can be reviewed after the run completes
- [ ] Per-task token usage is tracked (not just aggregate)
- [ ] `cub runs show` displays useful debugging info
- [ ] No measurable performance impact on task execution

---

## Related Specs

- `harness-abstraction.md` - Harness interface provides HarnessResult with usage
- `live-dashboard.md` - Dashboard reads from status.json (unchanged)

## References

- Bash implementation: `lib/artifacts.sh` (git history)
- Python status: `src/cub/core/status/writer.py`
- Harness models: `src/cub/core/harness/models.py`
- Run loop: `src/cub/cli/run.py` (lines 829-1111)

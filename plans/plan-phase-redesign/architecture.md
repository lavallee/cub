# Architecture: Plan Phase Redesign

> Source: [specs/researching/plan-phase-redesign.md](../../specs/researching/plan-phase-redesign.md)
> Orient: [orientation.md](./orientation.md)
> Generated: 2026-01-20

## Technical Summary

Rewrite the `cub prep` pipeline in Python, replacing 1,700+ lines of bash with a modular, testable implementation using the Claude Agent SDK for interview orchestration. The architecture follows existing cub patterns: Typer CLI, Pydantic models, Rich terminal UI, and the `TaskBackend` Protocol for task system abstraction.

## Mindset & Scale

| Dimension | Choice | Rationale |
|-----------|--------|-----------|
| Mindset | MVP | Internal tooling; clean modules, good tests, not enterprise-grade |
| Scale | Personal → Team | Single developer or small team; no high-scale concerns |

## Technology Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| CLI Framework | Typer | Existing pattern; subcommands for `cub plan orient/architect/itemize` |
| Data Models | Pydantic v2 | `Plan`, `PlanStage`, `PlanStatus` models |
| Terminal UI | Rich | Progress bars, streaming output, confirmation prompts |
| Interview Engine | Claude Agent SDK | Direct use for MVP; flag for future harness abstraction |
| Task Backend | `TaskBackend` Protocol | Add `import_tasks()` method; works with Beads + JSON |
| Tests | pytest + pytest-mock | Match existing test infrastructure |
| Type Checking | mypy strict | Required for all new code |

**New dependencies**: None. Existing stack covers all needs.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLI Layer                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ cub plan    │  │ cub plan    │  │ cub plan    │  │ cub stage   │   │
│  │ orient      │  │ architect   │  │ itemize     │  │             │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
└─────────┼────────────────┼────────────────┼────────────────┼───────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                             Core Layer                                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        plan/pipeline.py                           │  │
│  │         Orchestrates SDK-based interview flow                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │
│  │ plan/orient.py │  │plan/architect.py│ │ plan/itemize.py│           │
│  │                │  │                │  │                │           │
│  │ - Build prompt │  │ - Build prompt │  │ - Build prompt │           │
│  │ - Gather ctx   │  │ - Gather ctx   │  │ - Generate IDs │           │
│  │ - Parse output │  │ - Parse output │  │ - Parse output │           │
│  └────────────────┘  └────────────────┘  └────────────────┘           │
│                                                                         │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │
│  │ plan/parser.py │  │ stage/stager.py│  │specs/workflow.py│          │
│  │                │  │                │  │                │           │
│  │ Parse itemized │  │ Plan → Tasks   │  │ Find/move specs│           │
│  │ plan.md → Task │  │ via TaskBackend│  │ between stages │           │
│  └────────────────┘  └────────────────┘  └────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
          │                                        │
          ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          External Systems                                │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │
│  │ Claude SDK     │  │ TaskBackend    │  │ Git            │           │
│  │                │  │                │  │                │           │
│  │ Interview      │  │ - Beads (bd)   │  │ - git mv specs │           │
│  │ orchestration  │  │ - JSON         │  │ - git add/rm   │           │
│  └────────────────┘  └────────────────┘  └────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Module Structure

```
src/cub/
├── cli/
│   ├── plan.py                 # Typer app: cub plan [orient|architect|itemize]
│   ├── stage.py                # Typer command: cub stage
│   └── plans.py                # Typer command: cub plans (stub for future)
│
├── core/
│   ├── plan/
│   │   ├── __init__.py
│   │   ├── models.py           # Plan, PlanStage, PlanStatus, OrientResult, etc.
│   │   ├── pipeline.py         # SDK orchestration: run_plan_pipeline()
│   │   ├── orient.py           # Orient stage: build_orient_prompt(), run_orient()
│   │   ├── architect.py        # Architect stage: build_architect_prompt(), run_architect()
│   │   ├── itemize.py          # Itemize stage: build_itemize_prompt(), run_itemize()
│   │   ├── parser.py           # parse_itemized_plan() → list[Task]
│   │   ├── context.py          # gather_context() for self-answering
│   │   └── ids.py              # generate_epic_id(), generate_task_id()
│   │
│   ├── stage/
│   │   ├── __init__.py
│   │   └── stager.py           # run_stage(): parse plan → TaskBackend.import_tasks()
│   │
│   ├── specs/
│   │   ├── __init__.py
│   │   └── workflow.py         # SpecWorkflow: find_spec(), move_spec()
│   │
│   └── tasks/
│       ├── backend.py          # Add import_tasks() to TaskBackend Protocol
│       ├── beads.py            # Implement import_tasks() via bd import
│       └── json.py             # Implement import_tasks() via bulk append
```

## Data Models

```python
# plan/models.py

from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path

class PlanStage(str, Enum):
    ORIENT = "orient"
    ARCHITECT = "architect"
    ITEMIZE = "itemize"

class StageStatus(str, Enum):
    PENDING = None
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"

class PlanStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    STAGED = "staged"

class Plan(BaseModel):
    slug: str
    created: datetime
    updated: datetime
    status: PlanStatus
    spec_file: str  # filename only, search specs/ to find
    stages: dict[PlanStage, StageStatus | None]
    project: str

    @classmethod
    def load(cls, plan_dir: Path) -> "Plan":
        """Load from plan.json."""
        ...

    def save(self, plan_dir: Path) -> None:
        """Save to plan.json."""
        ...

class SpecStage(str, Enum):
    RESEARCHING = "researching"
    PLANNED = "planned"
    STAGED = "staged"
    IMPLEMENTING = "implementing"
    RELEASED = "released"
```

## Key Interfaces

### TaskBackend.import_tasks()

```python
# Addition to TaskBackend Protocol

def import_tasks(self, tasks: list[Task]) -> list[Task]:
    """
    Bulk import tasks.

    Args:
        tasks: List of Task objects to create (with pre-generated IDs)

    Returns:
        List of created tasks (IDs preserved)
    """
    ...
```

**BeadsBackend implementation:**
```python
def import_tasks(self, tasks: list[Task]) -> list[Task]:
    # Write to temp JSONL
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for task in tasks:
            f.write(json.dumps(task.to_beads_dict()) + '\n')
        temp_path = f.name

    try:
        # Import via bd
        self._run_bd(["import", temp_path])
        return tasks
    finally:
        os.unlink(temp_path)
```

**JsonBackend implementation:**
```python
def import_tasks(self, tasks: list[Task]) -> list[Task]:
    data = self._load_prd()
    for task in tasks:
        data["tasks"].append(self._task_to_dict(task))
    self._save_prd(data)
    return tasks
```

### SpecWorkflow

```python
# specs/workflow.py

class SpecWorkflow:
    STAGES = ["researching", "planned", "staged", "implementing", "released"]

    def __init__(self, project_dir: Path):
        self.specs_dir = project_dir / "specs"

    def find_spec(self, filename: str) -> tuple[Path, SpecStage] | None:
        """Search all stage directories for spec file."""
        for stage in self.STAGES:
            path = self.specs_dir / stage / filename
            if path.exists():
                return path, SpecStage(stage)
        return None

    def move_spec(self, filename: str, to_stage: SpecStage) -> Path:
        """Move spec to new stage directory via git mv."""
        result = self.find_spec(filename)
        if result is None:
            raise SpecNotFoundError(filename)

        current_path, current_stage = result
        if current_stage == to_stage:
            return current_path  # Already there

        target = self.specs_dir / to_stage.value / filename
        target.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "mv", str(current_path), str(target)], check=True)
        return target
```

### Pipeline Orchestration

```python
# plan/pipeline.py

async def run_plan_pipeline(
    input_path: Path,
    slug: str | None = None,
    resume_from: PlanStage | None = None,
) -> Plan:
    """Run full planning pipeline with SDK-based interviews."""

    # Determine slug
    if slug is None:
        slug = input_path.stem  # e.g., "user-auth" from "user-auth.md"

    # Handle collision
    plan_dir = resolve_plan_dir(slug)  # Adds _alt_[a-z] if needed

    # Create or load plan
    plan = Plan.create_or_load(plan_dir, spec_file=input_path.name)

    # Determine starting stage
    start_stage = resume_from or plan.next_incomplete_stage()

    # Run stages
    if start_stage <= PlanStage.ORIENT:
        await run_orient(plan, plan_dir)
        plan.stages[PlanStage.ORIENT] = StageStatus.COMPLETE
        plan.save(plan_dir)

    if start_stage <= PlanStage.ARCHITECT:
        await run_architect(plan, plan_dir)
        plan.stages[PlanStage.ARCHITECT] = StageStatus.COMPLETE
        plan.save(plan_dir)

    if start_stage <= PlanStage.ITEMIZE:
        await run_itemize(plan, plan_dir)
        plan.stages[PlanStage.ITEMIZE] = StageStatus.COMPLETE
        plan.status = PlanStatus.COMPLETE
        plan.save(plan_dir)

    # Move spec: researching → planned
    spec_workflow = SpecWorkflow(Path.cwd())
    spec_workflow.move_spec(plan.spec_file, SpecStage.PLANNED)

    return plan
```

## ID Generation

```python
# plan/ids.py

import secrets
import string

def generate_epic_id(project: str, existing_ids: set[str] | None = None) -> str:
    """
    Generate beads-compatible epic ID with random suffix.

    Format: {project}-{random 3 chars}
    Example: cub-k7m
    """
    chars = string.ascii_lowercase + string.digits
    max_attempts = 100

    for _ in range(max_attempts):
        suffix = ''.join(secrets.choice(chars) for _ in range(3))
        epic_id = f"{project}-{suffix}"

        if existing_ids is None or epic_id not in existing_ids:
            return epic_id

    raise RuntimeError("Failed to generate unique epic ID after 100 attempts")

def generate_task_id(epic_id: str, task_num: int) -> str:
    """Generate task ID as epic.number."""
    return f"{epic_id}.{task_num}"

def generate_subtask_id(task_id: str, subtask_num: int) -> str:
    """Generate subtask ID as task.number."""
    return f"{task_id}.{subtask_num}"
```

## Self-Answering Context Gathering

```python
# plan/context.py

async def gather_context(
    spec_path: Path,
    plan_dir: Path | None = None,
) -> PlanningContext:
    """
    Gather context for self-answering interviews.

    Searches for answers in:
    - The spec being planned
    - CLAUDE.md (project patterns)
    - Existing specs (for patterns)
    - Existing plans (for patterns)
    - .cub/SYSTEM-PLAN.md (if exists)
    """
    context = PlanningContext()

    # Read the spec
    context.spec_content = spec_path.read_text()

    # Read CLAUDE.md
    claude_md = Path.cwd() / "CLAUDE.md"
    if claude_md.exists():
        context.claude_md = claude_md.read_text()

    # Read SYSTEM-PLAN.md if exists
    system_plan = Path.cwd() / ".cub" / "SYSTEM-PLAN.md"
    if system_plan.exists():
        context.system_plan = system_plan.read_text()

    # Scan existing plans for patterns
    plans_dir = Path.cwd() / "plans"
    if plans_dir.exists():
        context.existing_plans = list(plans_dir.glob("*/orientation.md"))[:5]

    return context
```

## Implementation Phases

### Phase 1: Foundation
1. Add `TaskBackend.import_tasks()` to Protocol
2. Implement in BeadsBackend (via `bd import`)
3. Implement in JsonBackend (bulk append)
4. Create `SpecWorkflow` class
5. Create plan data models

### Phase 2: Plan Command
1. Create `cli/plan.py` with Typer app
2. Implement orient stage (prompt + SDK + output)
3. Implement architect stage
4. Implement itemize stage
5. Wire up pipeline orchestration

### Phase 3: Stage Command
1. Create `cli/stage.py`
2. Implement `plan/parser.py` (parse itemized-plan.md)
3. Implement `stage/stager.py` (tasks → backend)
4. Wire spec lifecycle transitions

### Phase 4: Polish
1. Deprecation warnings on old commands
2. Documentation updates
3. Test coverage
4. Error handling and edge cases

## Technical Risks

| Risk | Mitigation |
|------|------------|
| SDK doesn't support graceful interrupts | Design checkpoint system; save partial progress to plan.json |
| Markdown parsing edge cases | Use structured format in itemized-plan.md; comprehensive parser tests |
| Beads import edge cases | Leverage existing `bd import` behavior; test with real data |
| Git operations in non-git dirs | Check for git repo; graceful fallback or error |

## Testing Strategy

- **Unit tests**: Models, ID generation, markdown parsing, spec workflow
- **Integration tests**: Full pipeline with mock SDK responses
- **Backend tests**: `import_tasks()` for both Beads and JSON
- **CLI tests**: Typer command invocation with fixtures

---

**Status**: Ready for Itemize phase

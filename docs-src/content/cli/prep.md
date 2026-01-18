---
title: cub prep
description: Run the vision-to-tasks prep pipeline to transform ideas into executable tasks.
---

# cub prep

Run the vision-to-tasks prep pipeline. Transforms a vision document into structured, agent-executable tasks through an interactive four-stage process.

---

## Synopsis

```bash
cub prep [OPTIONS] [VISION_FILE]
```

---

## Description

The `prep` command runs a four-stage pipeline to convert high-level ideas into executable tasks:

1. **Triage** - Interactive requirements refinement
2. **Architect** - Technical design and approach
3. **Plan** - Task decomposition into agent-sized chunks
4. **Bootstrap** - Initialize task backend with generated plan

Each invocation launches an interactive Claude session for the next incomplete stage. After exiting Claude, prep shows progress and the next step.

---

## Options

| Option | Description |
|--------|-------------|
| `--session ID` | Resume a specific session |
| `--continue` | Resume the most recent session |
| `--non-interactive` | Run stages using `claude -p` (best-effort, no interaction) |
| `--vision PATH` | Vision/input markdown file (required for non-interactive triage) |
| `-h`, `--help` | Show help message |

---

## Pipeline Stages

### Stage 1: Triage

Requirements refinement through interactive questioning.

```bash
cub triage [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--session ID` | Resume an existing session |
| `--non-interactive` | Run without interactive Claude session |
| `--vision PATH` | Vision file (required for non-interactive) |

**Output:** `.cub/sessions/{session-id}/triage.md`

The triage document includes:

- Executive summary
- Goals and non-goals
- Requirements (prioritized P0-P3)
- Constraints and risks
- Open questions

---

### Stage 2: Architect

Technical design based on triage output.

```bash
cub architect [OPTIONS] [SESSION_ID]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--session ID` | Specify session ID |
| `--non-interactive` | Run without interactive Claude session |

**Output:** `.cub/sessions/{session-id}/architect.md`

The architecture document includes:

- Technical summary
- System architecture
- Component design
- Data and state management
- Interfaces and APIs
- Testing strategy

---

### Stage 3: Plan

Task decomposition into agent-executable chunks.

```bash
cub plan [OPTIONS] [SESSION_ID]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--session ID` | Specify session ID |
| `--non-interactive` | Run without interactive Claude session |

**Output:**

- `.cub/sessions/{session-id}/plan.jsonl` - Beads-compatible tasks
- `.cub/sessions/{session-id}/plan.md` - Human-readable plan

---

### Stage 4: Bootstrap

Initialize task backend with generated plan.

```bash
cub bootstrap [OPTIONS] [SESSION_ID]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--prefix PREFIX` | Beads prefix for issue IDs |
| `--skip-prompt` | Don't generate PROMPT.md and AGENT.md |
| `--dry-run` | Preview actions without executing |

**Actions:**

1. Run pre-flight checks (git, tools)
2. Initialize beads (if needed)
3. Import plan.jsonl
4. Wire up task dependencies
5. Generate PROMPT.md and AGENT.md
6. Create git commit

---

## Session Management

### List Sessions

```bash
cub sessions                    # List all sessions
cub sessions list               # Same as above
```

### Show Session Details

```bash
cub sessions show               # Show most recent
cub sessions show myproj-...    # Show specific session
```

### Delete Session

```bash
cub sessions delete myproj-...
```

---

## Examples

### Run Full Pipeline

```bash
# Start new session, runs triage first
cub prep

# After triage completes, run again for architect
cub prep

# Continue through plan and bootstrap
cub prep
cub prep
```

### Resume Specific Session

```bash
# Resume by session ID
cub prep --session myproj-20260117-143022

# Continue most recent session
cub prep --continue
```

### Non-Interactive Mode

```bash
# Run all stages non-interactively from vision doc
cub prep --non-interactive --vision VISION.md
```

### Run Individual Stages

```bash
# Run just triage
cub triage

# Run just architect (uses most recent session)
cub architect

# Run just plan
cub plan

# Run just bootstrap
cub bootstrap
```

---

## Session Directory Structure

Sessions are stored in `.cub/sessions/{session-id}/`:

```
.cub/sessions/myproj-20260117-143022/
├── session.json     # Session metadata
├── triage.md        # Refined requirements
├── architect.md     # Technical design
├── plan.jsonl       # Beads-compatible tasks
└── plan.md          # Human-readable plan
```

### Session Metadata

The `session.json` file tracks:

```json
{
  "id": "myproj-20260117-143022",
  "epic_id": "abc12",
  "created": "2026-01-17T14:30:22Z",
  "status": "created",
  "stages": {
    "triage": "complete",
    "architect": "complete",
    "plan": "complete",
    "bootstrap": null
  }
}
```

---

## Vision Document

Prep looks for a vision document in this order:

1. Explicit path provided via `--vision`
2. `VISION.md` in project root
3. `docs/PRD.md`
4. `README.md` (fallback)

Create a `VISION.md` with your feature description:

```markdown
# My Feature

## Problem
Users cannot currently...

## Solution
We will add...

## Success Criteria
- Users can...
- System handles...
```

---

## Requirements

- **Claude Code** must be installed for interactive stages
- **Beads CLI** (`bd`) required for bootstrap stage
- **jq** required for JSON processing

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Stage completed successfully |
| `1` | Error occurred |
| `2` | Stage needs human input before continuing |

---

## Related Commands

- [`cub run`](run.md) - Execute tasks after prep
- [`cub status`](status.md) - View task progress
- [`cub sessions`](#session-management) - Manage prep sessions

---

## See Also

- [Prep Pipeline Guide](../guide/prep-pipeline/index.md) - Detailed pipeline documentation
- [Triage Stage](../guide/prep-pipeline/triage.md) - Requirements refinement
- [Architect Stage](../guide/prep-pipeline/architect.md) - Technical design
- [Plan Stage](../guide/prep-pipeline/plan.md) - Task decomposition
- [Bootstrap Stage](../guide/prep-pipeline/bootstrap.md) - Initialization

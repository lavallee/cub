---
title: Glossary
description: Definitions of key terms and concepts used throughout Cub documentation.
---

# Glossary

Definitions of key terms and concepts used throughout Cub. Terms are organized alphabetically for quick reference.

---

## B

**Backend**
:   The storage system used to persist and query tasks. Cub ships with two backends: JSONL (default, file-based) and Beads (advanced, via the external `bd` CLI). The active backend is configured in `.cub/config.json` under `backend.mode`. See [Task Management](guide/tasks/index.md) for details.

**Beads**
:   An external CLI tool (`bd`) that provides advanced task management with built-in support for dependencies, labels, epics, and priority. Used as an alternative task backend when richer task operations are needed. See [Beads Backend](guide/tasks/beads.md).

**Budget**
:   Cost or token limits that cap spending during a `cub run` session. Set via `--budget` (in USD) or `--budget-tokens` (raw token count) on the command line, or configured in `.cub/config.json`. Budgets prevent runaway spending when running autonomous loops. See [Budget & Guardrails](guide/budget/index.md).

## C

**Capture**
:   A raw idea, note, or observation recorded for later processing. Captures are lightweight and unstructured, intended to be triaged into specs or tasks later. Managed with `cub capture` (create) and `cub captures` (list/review). See [Captures](guide/advanced/captures.md).

**Checkpoint**
:   A review or approval gate that blocks downstream tasks until a human approves it. Created as a task with type `gate`. When running `cub run`, tasks that depend on an unapproved checkpoint are skipped automatically. Managed with `cub checkpoints`. See [Git Integration](guide/git/index.md).

**Circuit Breaker**
:   A stagnation detection mechanism in the run loop. When the loop detects that no meaningful progress has been made after repeated iterations (e.g., the same task keeps failing), the circuit breaker trips and halts execution to prevent infinite loops.

**Context Composition**
:   The system that assembles the prompt sent to an AI harness from multiple layers: the runloop template (`.cub/runloop.md`), plan-specific context (`plans/<slug>/prompt-context.md`), epic context, task context, and retry context from previous attempts. Context is composed at runtime rather than through file mutation. See [Core Concepts](getting-started/concepts.md).

## E

**Epic**
:   A group of related tasks that form a larger unit of work. Tasks belong to an epic via the `parent` field in the task record, and epic IDs are embedded in the hierarchical task ID format (`{project}-{epic}-{task}`). Epics enable grouped progress tracking, branch bindings, and pull request management. See [Git Integration](guide/git/index.md).

## F

**Forensics**
:   Session event logs stored as JSONL files in `.cub/ledger/forensics/`. Each file records timestamped events from a single session, including file writes, task claims, git commits, and session start/end markers. Forensics data is used by `cub reconcile` to reconstruct ledger entries after direct harness sessions.

## G

**Guardrail**
:   A safety mechanism that prevents issues during autonomous execution. Guardrails include iteration limits, budget caps, clean-state requirements before task execution, secret redaction in prompts, and the circuit breaker. Configured in `.cub/config.json` under `state`, `loop`, and `budget` sections. See [Budget & Guardrails](guide/budget/index.md).

## H

**Harness**
:   An abstraction layer over AI coding CLIs that normalizes how Cub invokes different tools. Supported harnesses: Claude Code (`claude`), OpenAI Codex (`codex`), Google Gemini (`gemini`), and OpenCode (`opencode`). Each harness implements a common interface for prompt delivery, execution, and output capture. See [AI Harnesses](guide/harnesses/index.md).

**Hook**
:   A script or command that runs automatically at specific lifecycle points during a session. Used in the symbiotic workflow to track work done in direct harness sessions. Supported hook events include `SessionStart`, `PostToolUse`, `Stop`, and `PreCompact`. Hooks are configured in `.claude/settings.json` and installed by `cub init`. See [Hooks System](guide/hooks/index.md).

## I

**Itemize**
:   The third and final phase of the planning pipeline. Itemize takes an architectural design and breaks it into individual, agent-sized tasks with clear acceptance criteria and dependency relationships. Run with `cub plan itemize`. See [Plan Pipeline](guide/plan-pipeline/itemize.md).

## J

**JSONL**
:   JSON Lines format, where each line of a file is a self-contained JSON object. Used by the default task backend (`.cub/tasks.jsonl`), the ledger index (`.cub/ledger/index.jsonl`), and forensics logs. JSONL is append-friendly and easy to process with standard tools. See [JSON Backend](guide/tasks/json.md).

## L

**Ledger**
:   An append-only record of all completed work, stored in `.cub/ledger/`. Entries are organized by task (`by-task/`), epic (`by-epic/`), and run (`by-run/`), with a combined index in `index.jsonl`. The ledger captures what was done, when, by whom, and at what cost. Queryable with `cub ledger show`, `cub ledger stats`, and `cub ledger search`.

## O

**Orient**
:   The first phase of the planning pipeline. Orient researches and understands the problem space before any design work begins, producing an orientation document that captures requirements, constraints, and context. Run with `cub plan orient`. See [Plan Pipeline](guide/plan-pipeline/orient.md).

## P

**Plan**
:   A structured decomposition of work created through the three-phase planning pipeline: orient, architect, and itemize. Plans are stored in the `plans/` directory and contain orientation research, architectural decisions, itemized tasks, and runtime context for prompt injection. See [Plan Pipeline](guide/plan-pipeline/index.md).

**Punchlist**
:   A file listing discovered issues, remaining work items, or polish tasks identified during development. Processed by `cub punchlist` into structured epics with individual tasks, bridging informal notes into the formal task system.

## R

**Reconcile**
:   The process of converting session forensics into formal ledger entries after the fact. Useful when work is done in direct harness sessions (outside `cub run`) and needs to be recorded in the ledger. Run with `cub reconcile <session-id>` for a single session or `cub reconcile --all` for batch processing.

**Runloop**
:   The core autonomous execution cycle that drives `cub run`. The loop repeats: find a ready task, generate a prompt, invoke the AI harness, verify completion, record results in the ledger, then move to the next task. The runloop template (`.cub/runloop.md`) defines the system-level instructions sent to the harness. See [The Run Loop](guide/run-loop/index.md).

## S

**Session**
:   A single execution period, either a `cub run` invocation or a direct interactive harness session (e.g., opening Claude Code manually). Each session is assigned a unique ID and can be associated with one or more tasks. Session data flows into forensics logs and ledger entries.

**Stage**
:   The process of importing tasks from a completed plan into the active task backend. Running `cub stage` reads the itemized plan, creates tasks in the backend, and generates a `prompt-context.md` file for runtime context injection. See [Plan Pipeline](guide/plan-pipeline/stage.md).

**Symbiotic Workflow**
:   The system that enables fluid movement between CLI-driven autonomous sessions (`cub run`) and interactive direct harness sessions. Hooks implicitly track file writes, task claims, and git commits during direct sessions, achieving near-parity with `cub run` for work visibility and ledger recording. See [Hooks System](guide/hooks/index.md).

## T

**Task**
:   The fundamental unit of work in Cub. Each task has a hierarchical ID in the format `{project}-{epic}-{task}`, lifecycle states (`open`, `in_progress`, `closed`), a priority level (P0 through P4), and optional acceptance criteria. Tasks are selected, executed, and completed by the runloop. See [Task Management](guide/tasks/index.md).

**Task ID**
:   A hierarchical identifier that encodes project, epic, and task information. For example, `cub-048a-5.4` refers to project `cub`, epic `048a-5`, task `4`. This structure enables organized queries by project, epic, or individual task.

## W

**Worktree**
:   A git worktree used for isolated, parallel task execution. When running `cub run --worktree`, Cub creates a separate working directory linked to the same repository, allowing multiple tasks to execute simultaneously without interfering with each other. Managed with `cub worktree`. See [Worktrees](guide/git/worktrees.md).

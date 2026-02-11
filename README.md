# Cub

> ⚠️ **Alpha** — Breaking changes possible. See [ALPHA-NOTES.md](docs/ALPHA-NOTES.md) for known limitations.

**Work ahead of your AI coding agents, then let them run.**

Cub wraps AI coding CLIs (Claude Code, Codex, Gemini, OpenCode) to provide a reliable autonomous loop. You break work into structured tasks, Cub picks the next ready task, generates a prompt, invokes the right AI harness, verifies the result, records what happened, and moves on.

If you're juggling multiple agent sessions, manually routing work to different models, or finding that hands-off agents tend to run amok — Cub helps you invest time *before* execution so you can be more hands-off *during* execution.

### Before and After

**Without Cub:** You open Claude Code, paste a vague prompt, watch it for 20 minutes, realize it went off track, manually fix things, try again, lose track of what was done, repeat.

**With Cub:** You spend 10 minutes planning — `cub plan run` breaks your idea into 6 agent-sized tasks with acceptance criteria. You run `cub run`, walk away, come back to 6 commits, a structured ledger of what happened, and tests passing. If task 3 failed, Cub retried it with failure context and moved on.

## Prerequisites

- **Python 3.10+** (required)
- **At least one AI coding CLI:**
  - [Claude Code](https://github.com/anthropics/claude-code) (default, recommended)
  - [OpenAI Codex CLI](https://github.com/openai/codex)
  - [Google Gemini CLI](https://github.com/google-gemini-cli)
  - [OpenCode CLI](https://github.com/opencode)

## Installation

```bash
curl -LsSf https://install.cub.tools | bash
```

Restart your shell, then run:

```bash
cub init --global
```

Already installed? Run `pipx upgrade cub` or re-run the installer.

<details>
<summary>Alternative install methods</summary>

**Using pipx manually:**
```bash
pipx install git+https://github.com/lavallee/cub.git
cub init --global
```

**Using uv:**
```bash
uv tool install git+https://github.com/lavallee/cub.git
cub init --global
```

**From source (for development):**
```bash
git clone https://github.com/lavallee/cub ~/tools/cub
cd ~/tools/cub
uv sync
export PATH="$HOME/tools/cub/.venv/bin:$PATH"
cub init --global
```
</details>

## Quick Start

Try it in 5 minutes.

### New Project

```bash
# Create a project with git and cub initialized
cub new my-project
cd my-project

# Create a task
cub task create "Add a hello world HTTP server" --type feature --priority 0

# Run one iteration
cub run --once
```

### Existing Project

```bash
cd my-project
cub init

# Create a task
cub task create "Refactor auth module to use JWT" --type task --priority 0

# Run one iteration
cub run --once
```

### What Happens

Cub finds the ready task, generates a prompt with your project context and task details, invokes Claude Code (or your configured harness), waits for completion, records the result in the ledger, and commits the work. You'll see output like:

```
[cub] Session: porcupine-20260211-143022
[cub] Task: my-project-a1b → "Add a hello world HTTP server"
[cub] Harness: claude (sonnet)
[cub] ... (agent working) ...
[cub] Task completed (exit 0, 45s, 12k tokens)
[cub] Committed: abc123f "task(my-project-a1b): Add a hello world HTTP server"
```

### Continuous Loop

Once you're comfortable with single iterations, let it run:

```bash
cub run                     # Run until all tasks complete or budget exhausted
cub run --epic my-feature   # Target a specific epic
cub run --stream            # Watch agent activity in real-time
cub run --budget 10         # Set a $10 USD budget limit
```

## Key Features

### Multi-Harness Support

Cub abstracts across AI coding CLIs. Use the right tool without vendor lock-in:

```bash
cub run --harness claude    # Claude Code (default)
cub run --harness codex     # OpenAI Codex CLI
cub run --harness gemini    # Google Gemini CLI
cub run --harness opencode  # OpenCode CLI
```

Per-task model selection routes simple work to fast models and complex work to capable ones:

```bash
cub task create "Rename variable" --labels "model:haiku"
cub task create "Redesign auth system" --labels "model:opus"
```

### Planning Pipeline

Go from a rough idea to structured, agent-ready tasks:

```bash
cub plan run                # Full pipeline: orient → architect → itemize
cub plan orient             # Research the problem space
cub plan architect          # Design the solution
cub plan itemize            # Break into agent-sized tasks with acceptance criteria
cub stage                   # Import planned tasks into the task backend
```

### Budget Controls and Guardrails

Hard limits that actually stop execution:

- **Token budgets** — per-task and per-session limits
- **Iteration limits** — max retries per task, max iterations per run
- **Circuit breaker** — stops the loop if the harness hangs (configurable timeout)
- **Clean state enforcement** — verifies git state before and after tasks

### Symbiotic Workflow

When you work directly in Claude Code (not through `cub run`), hooks automatically track what you do — file writes, task claims, git commits — and create ledger entries. No work goes unrecorded.

```bash
cub init                    # Installs hooks into .claude/settings.json
cub task claim my-task-id   # Claim a task in a direct session
# ... work normally ...
cub task close my-task-id -r "Implemented feature"
```

See the [Symbiotic Workflow guide](https://docs.cub.tools/docs/) for details.

### Ledger: Work Tracking and Learning

Every task execution is recorded in a structured ledger with duration, tokens, cost, git SHAs, and outcomes:

```bash
cub ledger show             # View completed work
cub ledger stats            # Show statistics
cub retro epic-id           # Generate retrospective report
cub learn extract           # Extract patterns from completed work
cub verify                  # Check data integrity
```

## How It Works

```
┌───────────────────────────────────────────────┐
│                  cub run                      │
│                                               │
│  Tasks ────> Find Ready Task (by priority,    │
│              dependencies, filters)           │
│                     │                         │
│                     v                         │
│              Generate Prompt                  │
│              (runloop + plan + task context)   │
│                     │                         │
│                     v                         │
│              Invoke AI Harness                │
│              (claude / codex / gemini / ...)   │
│                     │                         │
│                     v                         │
│              Verify & Record                  │
│              (exit code, git commit, ledger)   │
│                     │                         │
│                /         \                    │
│               v           v                   │
│           More tasks    All done              │
│           (loop back)   (exit)                │
└───────────────────────────────────────────────┘
```

**Task selection:** Find open tasks where all dependencies are closed, sort by priority (P0 first), pick the first one. Filters by epic, label, or specific task ID narrow the selection.

**Prompt generation:** Composed from multiple layers — core runloop instructions, plan context (if tasks came from `cub plan`), epic context, task details with acceptance criteria, and retry context if this is a subsequent attempt.

**Verification:** The harness exit code determines success. On failure, configurable modes control behavior: `stop`, `move-on`, `retry` (with failure context), or `triage`.

**Recording:** Each completion writes a ledger entry with timestamps, duration, token usage, git SHA, and outcome. The ledger enables retrospectives, pattern extraction, and learning.

## Common Commands

### Task Management

```bash
cub task create "Title" --type feature --priority 0
cub task list               # List all tasks
cub task ready              # Show ready (unblocked) tasks
cub task show <id>          # View task details
cub task close <id> -r "reason"
```

### Run Loop

```bash
cub run                     # Run until complete
cub run --once              # Single iteration
cub run --epic <id>         # Target specific epic
cub run --task <id>         # Run specific task
cub run --harness codex     # Use specific harness
cub run --model haiku       # Use specific model
cub run --budget 10         # USD budget limit
cub run --stream            # Watch in real-time
cub run --monitor           # Live dashboard in tmux
cub run --parallel 4        # Parallel task execution
```

### Planning

```bash
cub plan run                # Full pipeline
cub plan orient             # Research phase
cub plan architect          # Design phase
cub plan itemize            # Task breakdown phase
cub stage                   # Import tasks from plan
```

### Status and Monitoring

```bash
cub status                  # Project progress overview
cub suggest                 # Smart suggestions for next actions
cub monitor                 # Live execution dashboard
cub dashboard               # Kanban board visualization
cub doctor                  # Diagnose configuration issues
```

### Session and Ledger

```bash
cub session log             # Log work in a direct session
cub session done            # Mark session complete
cub ledger show             # View completed work
cub ledger stats            # Statistics
cub verify                  # Check data integrity
cub learn extract           # Extract patterns from work history
```

For the full command reference: `cub --help` or `cub <command> --help`.

Running `cub` without a subcommand defaults to `cub run`.

## Documentation

Full documentation is available at **[docs.cub.tools](https://docs.cub.tools/docs/)**.

| Topic | Link |
|-------|------|
| Getting Started | [docs.cub.tools/docs/getting-started](https://docs.cub.tools/docs/) |
| Planning Guide | [docs.cub.tools/docs/planning](https://docs.cub.tools/docs/) |
| CLI Reference | [docs.cub.tools/docs/cli](https://docs.cub.tools/docs/) |
| Harness Configuration | [docs.cub.tools/docs/harnesses](https://docs.cub.tools/docs/) |
| Hooks & Symbiotic Workflow | [docs.cub.tools/docs/hooks](https://docs.cub.tools/docs/) |
| Budget & Guardrails | [docs.cub.tools/docs/budget](https://docs.cub.tools/docs/) |
| Dashboard | [docs.cub.tools/docs/dashboard](https://docs.cub.tools/docs/) |
| Git Workflow | [docs.cub.tools/docs/git](https://docs.cub.tools/docs/) |
| Toolsmith | [docs.cub.tools/docs/toolsmith](https://docs.cub.tools/docs/) |
| Troubleshooting | [docs.cub.tools/docs/troubleshooting](https://docs.cub.tools/docs/) |

---

## Configuration Reference

### Config Precedence

1. **CLI flags** (highest)
2. **Environment variables**
3. **Project config** (`.cub/config.json`)
4. **Global config** (`~/.config/cub/config.json`)
5. **Hardcoded defaults** (lowest)

### Key Settings

`.cub/config.json`:

```json
{
  "harness": "claude",
  "budget": {
    "max_tokens_per_task": 500000,
    "max_total_cost": null
  },
  "state": {
    "require_clean": true,
    "run_tests": true
  },
  "loop": {
    "max_iterations": 100,
    "on_task_failure": "stop"
  },
  "hooks": {
    "enabled": true,
    "fail_fast": false
  },
  "circuit_breaker": {
    "enabled": true,
    "timeout_minutes": 30
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HARNESS` | `auto` | AI harness: `auto`, `claude`, `codex`, `gemini`, `opencode` |
| `CUB_MODEL` | | Override model for harness |
| `CUB_BUDGET` | | Override token budget |
| `CUB_MAX_ITERATIONS` | `100` | Max loop iterations |
| `CUB_EPIC` | | Filter to tasks in this epic |
| `CUB_LABEL` | | Filter to tasks with this label |
| `CUB_BACKEND` | `auto` | Task backend: `auto`, `jsonl`, `beads`, `json` |
| `CUB_DEBUG` | `false` | Enable debug mode |
| `CUB_STREAM` | `false` | Enable streaming output |
| `CLAUDE_FLAGS` | | Extra flags for Claude Code |
| `CODEX_FLAGS` | | Extra flags for Codex CLI |
| `GEMINI_FLAGS` | | Extra flags for Gemini CLI |
| `OPENCODE_FLAGS` | | Extra flags for OpenCode CLI |

For the full configuration reference, see [docs/CONFIG.md](docs/CONFIG.md).

## Project Structure

After `cub init`, your project will have:

```
my-project/
├── .cub/                   # Cub runtime data
│   ├── config.json         # Project configuration
│   ├── agent.md            # Agent instructions (symlinked as CLAUDE.md)
│   ├── runloop.md          # System prompt for autonomous sessions
│   ├── map.md              # Project structure map
│   ├── tasks.jsonl         # Task backend (JSONL)
│   ├── hooks/              # Hook scripts
│   ├── scripts/hooks/      # Shell fast-path hooks
│   └── ledger/             # Task completion records
│       ├── index.jsonl     # Index of all entries
│       ├── by-task/        # Entries grouped by task ID
│       ├── by-epic/        # Entries grouped by epic ID
│       ├── by-run/         # Entries grouped by run/session ID
│       └── forensics/      # Session event logs (JSONL per session)
├── specs/                  # Detailed specifications
├── plans/                  # Planning artifacts
└── CLAUDE.md               # Symlink to .cub/agent.md
```

**Key files:**

| File | Purpose |
|------|---------|
| `.cub/config.json` | All project-specific settings |
| `.cub/agent.md` | Build instructions, architecture notes, gotchas for AI agents |
| `.cub/runloop.md` | Core loop instructions for autonomous sessions |
| `.cub/tasks.jsonl` | Task definitions (JSONL backend) |
| `.cub/ledger/` | Structured records of all completed work |
| `CLAUDE.md` | Symlink so Claude Code reads project instructions |

## Source Code Reference

For contributors and agents exploring the codebase:

| Module | Purpose |
|--------|---------|
| `src/cub/cli/` | Typer CLI subcommands (run, status, init, task, plan, etc.) |
| `src/cub/core/services/` | Service layer orchestrators (RunService, LaunchService, LedgerService, StatusService, SuggestionService) |
| `src/cub/core/run/` | Run loop domain logic (prompt builder, budget tracking, state machine) |
| `src/cub/core/launch/` | Harness detection and environment setup |
| `src/cub/core/suggestions/` | Recommendation engine for next actions |
| `src/cub/core/config/` | Configuration loading with layered precedence |
| `src/cub/core/tasks/` | Task backend abstraction (JSONL, beads, JSON) |
| `src/cub/core/harness/` | AI harness backends (Claude, Codex, Gemini, OpenCode) |
| `src/cub/core/ledger/` | Task completion ledger (models, reader, writer, extractor) |
| `src/cub/core/tools/` | Tool execution runtime with pluggable adapters |
| `src/cub/core/circuit_breaker.py` | Stagnation detection for the run loop |
| `src/cub/core/instructions.py` | Instruction file generation |

## License

MIT

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

**Upgrading from v0.20 (Bash)?** See [UPGRADING.md](UPGRADING.md) for the migration guide.

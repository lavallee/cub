# Cub command map: commands/subcommands + implementation + LLM involvement

Captured: 2026-01-26

This is a practical inventory of **Cub CLI commands** (from `cub --help`) plus notable subcommands, annotated with:

- **Impl**: `python` (Typer CLI) vs `bash` script
- **LLM**: whether the command **invokes an LLM** in any way
  - `yes` = always uses an LLM/harness
  - `optional` = only with certain flags/options or depending on configuration
  - `no` = should not call an LLM (purely local/infra), though it may call other system tools

> Notes:
> - The `cub` executable itself is implemented in **Python**; many commands shell out to tools like `git`, `gh`, `docker`, etc.
> - “LLM involvement” here means **any call to a model provider / harness** (Claude/Codex/Gemini/OpenCode), not just “chatty” UX.

## 1) Top-level `cub` CLI commands

| Command | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub init` | python | no | Project/global initialization. |
| `cub run` | python | yes | Autonomous execution loop; uses selected harness (`--harness`, `--model`). |
| `cub artifacts` | python | no | Lists artifacts produced by runs/tasks. |
| `cub status` | python | no | Status reporting (`--json`, `--verbose`). |
| `cub monitor` | python | no | Live dashboard/monitoring for a run session. |
| `cub sandbox ...` | python | no | Docker sandbox lifecycle (see subcommands below). |
| `cub ledger ...` | python | no | Ledger queries + exports (see subcommands below). |
| `cub review ...` | python | optional | `--deep` uses LLM-based analysis. Otherwise local analysis. |
| `cub dashboard ...` | python | no | Web dashboard server + sync/export utilities. |
| `cub interview` | python | optional* | Likely LLM-assisted “deep dive on task specs” (help text doesn’t say; confirm in code). |
| `cub explain-task` | python | no | Task introspection (should be local). |
| `cub close-task` | python | no | Agent-use command to close tasks (local backend operation). |
| `cub verify-task` | python | no | Agent-use command to verify task closure (local checks). |
| `cub task ...` | python | no | Backend-agnostic task CRUD/queries (see subcommands below). |
| `cub punchlist` | python | no | Converts punchlist markdown into epics/tasks (appears deterministic). |
| `cub workflow ...` | python | no | Post-completion workflow stage mgmt (see subcommands below). |
| `cub branch` | python | no | Branch creation/binding (git operations). |
| `cub branches` | python | no | Branch↔epic bindings management. |
| `cub checkpoints` | python | no | Review/approval gates (local). |
| `cub worktree ...` | python | no | Git worktree management (see subcommands below). |
| `cub pr ...` | python | no | PR create/status; shells out to VCS tooling (no LLM implied). |
| `cub merge ...` | python | no | PR merge/wait; CI integration (no LLM implied). |
| `cub guardrails` | python | no | Institutional memory management (local files). |
| `cub audit ...` | python | no | Code health audits (local tooling). |
| `cub capture` | python | optional | `--interactive` explicitly uses Claude; auto-tags/slug may use an LLM unless disabled (`--no-auto-tags`, `--no-slug`). |
| `cub spec` | python | yes | “AI-guided interview” to generate a spec. |
| `cub triage` | python | optional* | Stage 1 of prep pipeline; likely LLM-based, but help text is minimal. |
| `cub organize-captures` | python | no | Normalizes/renames capture files; deterministic. |
| `cub import` | python | no | Imports tasks from external sources (non-LLM). |
| `cub captures ...` | python | no | List/show/edit/import/archive captures. |
| `cub tools ...` | python | no | Tool runtime mgmt/execution (see subcommands below). Execution can indirectly support LLM workflows but is not “LLM” by default. |
| `cub toolsmith ...` | python | no | Tool catalog discovery/sync/adopt (no LLM implied; does web/API). |
| `cub workbench ...` | python | no | PM workbench orchestration; `run-next` executes the configured tool (not necessarily LLM). |
| `cub version` | python | no | Prints version. |
| `cub update` | python | no | Update templates/skills (project maintenance). |
| `cub system-upgrade` | python | no | Upgrades cub installation. |
| `cub uninstall` | python | no | Uninstall cub. |
| `cub doctor` | python | no | Diagnostics; can auto-fix. |
| `cub plan ...` | python | yes | Planning pipeline: orient/architect/itemize are LLM-style phases. |
| `cub stage` | python | no | Stages/imports tasks from completed plan into task backend. |

\* *Marked “optional*” where help output doesn’t explicitly mention LLM usage; confirm by inspecting command implementation.*

## 2) Notable subcommands

### `cub sandbox`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub sandbox logs` | python | no | Container logs. |
| `cub sandbox status` | python | no | Resource usage/status. |
| `cub sandbox diff` | python | no | Show filesystem changes. |
| `cub sandbox export` | python | no | Export files to local. |
| `cub sandbox apply` | python | no | Apply sandbox changes to project. |
| `cub sandbox clean` | python | no | Cleanup. |

### `cub ledger`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub ledger show` | python | no | Show entry. |
| `cub ledger update` | python | no | Update workflow stage. |
| `cub ledger stats` | python | no | Aggregate stats. |
| `cub ledger search` | python | no | Search ledger. |
| `cub ledger export` | python | no | Export ledger data. |
| `cub ledger gc` | python | no | Garbage collect old attempt files. |

### `cub review`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub review task` | python | optional | `--deep` triggers LLM-based analysis.
| `cub review epic` | python | optional | `--deep` triggers LLM-based analysis.
| `cub review plan` | python | optional | `--deep` triggers LLM-based analysis.

### `cub dashboard`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub dashboard sync` | python | no | Builds dashboard DB. |
| `cub dashboard export` | python | no | Exports board JSON. |
| `cub dashboard views` | python | no | Lists configured views. |
| `cub dashboard init` | python | no | Initializes example views. |

### `cub task`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub task create` | python | no | Creates a task in backend. |
| `cub task show` | python | no | Shows task detail. |
| `cub task list` | python | no | Lists tasks with filters. |
| `cub task update` | python | no | Updates task fields. |
| `cub task close` | python | no | Closes a task. |
| `cub task ready` | python | no | Lists ready tasks. |
| `cub task counts` | python | no | Task stats. |
| `cub task dep` | python | no | Dependency mgmt. |

### `cub workflow`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub workflow set` | python | no | Set stage. |
| `cub workflow show` | python | no | Show stage/status. |
| `cub workflow list` | python | no | List by stage. |

### `cub worktree`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub worktree list` | python | no | Lists worktrees. |
| `cub worktree create` | python | no | Creates worktree. |
| `cub worktree remove` | python | no | Removes worktree. |
| `cub worktree clean` | python | no | Cleans merged worktrees. |

### `cub pr`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub pr status` | python | no | PR status. |

### `cub merge`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub merge wait` | python | no | Wait for CI checks. |

### `cub plan`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub plan orient` | python | yes | Produces `orientation.md` in plan dir. |
| `cub plan architect` | python | yes | Produces architecture output for plan. |
| `cub plan itemize` | python | yes | Produces tasks breakdown for plan. |
| `cub plan run` | python | yes | Runs orient→architect→itemize. |
| `cub plan list` | python | no | Lists plans. |

### `cub tools`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub tools list` | python | no | Lists tool adapters. |
| `cub tools check` | python | no | Checks readiness. |
| `cub tools run` | python | no | Executes a tool via adapter. |
| `cub tools artifacts` | python | no | Lists artifacts. |
| `cub tools stats` | python | no | Effectiveness metrics. |
| `cub tools configure` | python | no | Approvals/freedom dial config. |

### `cub toolsmith`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub toolsmith sync` | python | no | Syncs from sources (smithery/glama/etc). |
| `cub toolsmith search` | python | no | Local or live search. |
| `cub toolsmith adopt` | python | no | Writes adoption/registry entries. |
| `cub toolsmith run` | python | no | Runs adopted tool (experimental). |
| `cub toolsmith adopted` | python | no | Lists adopted tools. |
| `cub toolsmith stats` | python | no | Catalog stats. |

### `cub workbench`
| Subcommand | Impl | LLM | Notes |
|---|---:|---:|---|
| `cub workbench start` | python | no | Creates/starts a session from a spec. |
| `cub workbench run-next` | python | no | Executes Next Move tool + appends artifacts to session file. |

## 3) Repo `scripts/` (bash) — not part of `cub` CLI

These are **maintenance/release helper scripts** (bash) shipped in the repo:

| Script | Impl | LLM | Notes |
|---|---:|---:|---|
| `scripts/build-plan.sh` | bash | unknown | Build helper for plans (needs review). |
| `scripts/spec-interview.sh` | bash | likely | Suggests spec interview flow; likely calls Claude CLI/SDK via wrappers. |
| `scripts/new-branch.sh` | bash | no | Branch utility. |
| `scripts/land-branch.sh` | bash | no | Branch landing utility. |
| `scripts/cut-release.sh` | bash | no | Release automation. |
| `scripts/release-pipeline.sh` | bash | no | Release pipeline automation. |
| `scripts/spec-to-issues.sh` | bash | no | Likely creates issues from specs (could call gh). |
| `scripts/test_install_from_source.sh` | bash | no | Installer testing. |

(There are also python helper scripts in `scripts/` like `generate_changelog.py`, `move_specs_released.py`, etc.)

## 4) Follow-ups / gaps to tighten

- Confirm whether `cub interview` and `cub triage` always/ever invoke an LLM (help text doesn’t say).
- For `cub capture`, confirm whether auto-tags and slug generation are LLM-backed or heuristic.
- Confirm whether any “no” commands ever call LLM indirectly (e.g., `tools run` might execute an adopted tool that itself calls an LLM).

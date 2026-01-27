# Cub CLI: `cub` (no subcommand) as graceful bootstrap / triage

## Goal
Make running `cub` with **no arguments** feel like:
- `git` (helpful defaults)
- `gh` / `vercel` / `flyctl` (detect state → suggest next action)
- `npm create` / `cargo new` (smooth project bootstrap)

…while staying predictable, scriptable, and non-annoying.

**Design principle:** *default path should either “resume work” or present a single, tight choice set.* Avoid wizard fatigue.

---

## What others do (patterns worth copying)

### 1) “Ambient detection → suggest next command” (GitHub CLI, Vercel, Fly)
Common behaviors:
- Detect auth/session state; if missing, prompt to login.
- Detect project context; if missing, prompt to link/create.
- If already linked, default to the most common action (“deploy”, “status”, “open”).

**Cub translation:** detect “Cub project? git repo? harness installed? active task?” and default to “resume” or “start”.

### 2) “Scaffold when context is empty” (npm create, cargo new, rails new)
Common behaviors:
- If no project exists, guide creation quickly with sensible defaults.
- Put config in a predictable place.
- Leave you in a runnable state.

**Cub translation:** `cub` in a non-project dir offers “create here” or “create new directory”; then creates minimal `.cub/` state and optionally git init.

### 3) “Doctor + diagnostics as first-class” (brew doctor, flutter doctor)
Common behaviors:
- One command gives actionable fixes.

**Cub translation:** `cub doctor` exists; `cub` may suggest it if triage finds issues (missing harness, missing git, incompatible env).

### 4) “Composable status surfaces” (tmux, starship, Claude Code statusline)
Common behaviors:
- Tools expose a *cheap* `--short` status output for prompts/bars.
- They store state on disk so other tools can read it.

**Cub translation:** maintain `.cub/status.json` (small, stable) + `cub status --short` (fast).

---

## The `cub` (no args) decision tree

### Inputs / signals

**Filesystem & project signals**
- `cubRoot`: nearest ancestor containing `.cub/` (or configured marker)
- `isGitRepo`: `git rev-parse --is-inside-work-tree` success
- `repoRoot`: `git rev-parse --show-toplevel`
- `dirty`: `git status --porcelain` non-empty

**Cub signals**
- `.cub/config.json` present?
- `.cub/state.json` includes `activeTaskId`?
- `openTaskCount` / `blockedCount` / `inProgressCount`

**Harness signals**
- `claudeCodeInstalled`: can exec `claude` (or whatever binary)
- `codexInstalled`: can exec `codex` (or equivalent)
- `tmux`: `$TMUX` set

**User preference signals**
- default harness (from config)
- preference for “auto-launch vs print command”

### States

#### State A: Already in a Cub project (`cubRoot` found)
Default behavior: **resume**.

- If `activeTaskId` exists → open harness with “resume task” context.
- Else if `openTaskCount > 0` → offer “Pick task” vs “Start new task” (default start new).
- Else → “Start new task” (default).

#### State B: In a git repo but not Cub-initialized
Default behavior: **adopt repo**.

Offer:
1) “Adopt this repo for Cub” (creates `.cub/` + seeds config)
2) “Create new Cub project directory…”
3) “Quit”

If adopted: go to State A.

#### State C: Not a git repo, not a Cub project
Default behavior: **create project**.

Offer:
1) “Create Cub project here”
2) “Create new directory…” (default)
3) “Quit”

During creation: optionally offer `git init`.

---

## UX contract: fast path + safe path

### Fast path (no questions)
Only do a no-prompt action if **all** are true:
- You found a Cub project (`cubRoot`).
- A default harness is configured *and* installed.
- You have an `activeTaskId` or exactly one obvious next action.

Otherwise show a picker.

### Safe path (always offer “just show me commands”)
Every interactive screen should include a non-launch option:
- “Print launch command instead”
- “Run without harness (CLI mode)”

For public alpha, I’d default to **printing commands** unless the user has opted in.

---

## Proposed interactive screen designs (examples)

### Example 1: In initialized Cub project, active task exists
```
$ cub
Cub: project ✓  git ✓  harness: Claude Code ✓
Active: #24 "Fix capture dedupe"

→ Resuming in Claude Code…
(Use `cub status` for details)
```

### Example 2: In initialized project, no active task
```
$ cub
Cub: project ✓  git ✓
Tasks: 3 open • 1 blocked

What next?
  1) Start new task (recommended)
  2) Pick from open tasks
  3) Capture an idea
  4) Open dashboard / status
  5) Configure harness
```

### Example 3: In git repo, not initialized
```
$ cub
No Cub project found, but this looks like a git repo:
  repo: ~/src/acme-api (main)

Set up Cub here?
  1) Adopt this repo for Cub (creates .cub/) (default)
  2) Create a new Cub project directory…
  3) Cancel
```

### Example 4: Random directory (Downloads)
```
$ cub
No Cub project found.
You’re in: ~/Downloads

Create a new Cub project?
  1) Create new directory "cub-project" (default)
  2) Use current directory
  3) Cancel
```

---

## Harness: what “drop into harness” should mean

### Modes
- **launch**: actually launch the harness UI (new process)
- **print**: print the command to run
- **attach**: if already inside harness context, emit instructions + maybe open files

Config:
- `cub config set harness.mode print|launch|attach`
- default for alpha: `print`

### Minimal “handoff payload”
Regardless of harness, Cub should generate a consistent “handoff” bundle:
- Title (task name)
- Current goal
- Suggested next steps
- Useful commands (test/build)
- Context anchors (paths, key files)

Mechanically:
- write `.cub/handoff.md` (or `.cub/brief.md`) each time
- and/or copy to clipboard (optional)

Then:
- For Claude Code: open in repo root, ask to read `.cub/handoff.md` first.
- For Codex/other: same.

---

## Claude Code integration sketch (statusline + startup)

### 1) Statusline: include Cub task counts
Claude Code supports running a **statusline command/script** and feeds it JSON via stdin.

Cub provides:
- `cub integrate claude-code` → installs `~/.claude/cub_statusline.sh` and optionally updates settings.

`cub_statusline.sh` behavior:
- Read Claude JSON from stdin.
- Read `.cub/status.json` if present in `workspace.current_dir` or nearest parent.
- Print one line combining:
  - git branch/dirty (optional)
  - model + context%
  - cub open/active counts + active task name

Example output:
`main ● | Opus | ctx 12% | cub: 3 open (1 active) | #24 Fix capture dedupe`

### 2) Cub state surface
Keep a small file intended for status bars:

`.cub/status.json`
```json
{
  "activeTask": {"id": 24, "title": "Fix capture dedupe"},
  "counts": {"open": 3, "blocked": 1, "inProgress": 1},
  "updatedAt": "2026-01-27T15:00:00Z"
}
```

### 3) Startup UX
When `cub` chooses Claude Code, it should:
- ensure `.cub/handoff.md` is updated
- launch/print command like:
  - `claude .` (or equivalent)
  - and the very first instruction: “Open `.cub/handoff.md` and follow it.”

---

## `cub` command surface (proposed)

### Core
- `cub` (triage)
- `cub init` (explicit initialization)
- `cub adopt` (initialize within an existing repo)
- `cub new <dir?>` (create directory + init)
- `cub start` (start/resume harness with handoff)
- `cub status [--short|--json]`
- `cub tasks` (list)
- `cub task start <id>` / `cub task new` / `cub task done <id>`
- `cub capture` (quick intake)
- `cub doctor`
- `cub integrate <harness>` (claude-code, tmux, starship)

### UX helpers
- `cub config` (get/set)
- `cub completion` (shell completions)

---

## Public alpha defaults (recommendation)

1) `cub` defaults to **interactive triage** only when ambiguous.
2) Harness handoff defaults to **print** not auto-launch.
3) Ship creature comforts as **opt-in integrations**:
   - Claude Code statusline script
   - tmux status segment
   - shell prompt segment

---

## Open questions to lock down

1) What is Cub’s canonical “project root marker”? `.cub/` seems best.
2) Do we require git for alpha, or allow no-git projects?
3) What’s the minimum “task state” Cub needs to expose in `.cub/status.json`?
4) Should `cub` ever auto-launch a harness without opt-in?

---

## Next step (if you want)
I can turn this into:
- a concrete state machine table (inputs → state → output)
- exact CLI text + prompts
- a minimal JSON schema for `.cub/status.json` and `.cub/state.json`
- a stub `cub_statusline.sh` example

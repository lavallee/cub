# Harness usage map: where Cub uses the harness interface vs calling Claude directly

Captured: 2026-01-26

Goal: list the places Cub:
1) **uses the (Python) harness abstraction** (`cub.core.harness.*`), vs
2) **calls Claude directly** (either via `claude` CLI or direct SDK invocation without going through the harness interface), and
3) equivalent mapping for the legacy **bash harness layer**.

> Terminology
> - **Harness interface (Python):** `cub.core.harness.async_backend.AsyncHarnessBackend` + registry (`get_async_backend`, `detect_async_harness`) and legacy sync `HarnessBackend`.
> - **Direct Claude CLI:** code that runs `subprocess.run(["claude", ...])` (or bash scripts calling `claude ...`) without going through Cub’s harness backend.
> - **Direct Claude SDK:** code that uses Anthropic/Claude SDK directly without going through the harness backend (didn’t spot any obvious bypass in a quick scan; most SDK usage appears encapsulated in `claude_sdk.py`).

---

## A) Python (current Typer CLI) — harness interface usage

These places **use the harness abstraction** (good: consistent logging/capabilities/features, swappable backends):

### `cub run` (primary)
- **Uses harness interface:** YES
- **Where:** `src/cub/cli/run.py`
  - Imports `detect_async_harness`, `get_async_backend`
  - `_setup_harness(...)` selects backend
  - `_invoke_harness(...)` calls:
    - `harness_backend.stream_task(...)` when streaming
    - `harness_backend.run_task(...)` when non-streaming

### Deep review analysis (`cub review --deep`)
- **Uses harness interface:** YES
- **Where:** `src/cub/core/review/assessor.py`
  - `_run_deep_analysis(...)` uses `get_async_backend()` and `await harness.analyze(...)`
  - This is explicitly “LLM-based deep analysis” but routed through the harness so it can degrade gracefully.

### Harness backends themselves
- **Where:** `src/cub/core/harness/*`
  - `claude_sdk.py` (SDK-based backend)
  - `claude_cli.py` (shell-out backend) — still “hitting claude”, but *through the harness interface*
  - `codex.py` (codex CLI)
  - plus registries/protocols in `backend.py` / `async_backend.py`

---

## B) Python — places that call Claude **directly** (bypassing harness interface)

These are the spots that currently **invoke `claude` directly** via `subprocess.run(...)` rather than going through `cub.core.harness.*`.

### 1) Plan stages: Claude slash commands (interactive + non-interactive)
- **Direct Claude CLI:** YES
- **Where:** `src/cub/core/plan/claude.py`
- **How:** builds a slash command (e.g. `"/cub:orient ..."`) and runs:
  - `subprocess.run([claude_path, "--dangerously-skip-permissions", full_command], ...)`
- **Why it matters:** these plan flows can’t currently swap to other harnesses via `--harness`; they’re hard-bound to Claude.

### 2) Capture slug generation
- **Direct Claude CLI:** YES
- **Where:** `src/cub/core/captures/slug.py`
- **How:** `subprocess.run(["claude", "--model", "haiku", "--print", "-p", prompt], ...)`
- **Notes:** has a fallback path when Claude isn’t available.

### 3) Punchlist hydration
- **Direct Claude CLI:** YES
- **Where:** `src/cub/core/punchlist/hydrator.py`
- **How:** `subprocess.run(["claude", "--model", "haiku", "--print", "-p", prompt], ...)`
- **Notes:** falls back to a deterministic extractor on failure.

### 4) Ledger insight extraction (post-run summarization)
- **Direct Claude CLI:** YES
- **Where:** `src/cub/core/ledger/extractor.py`
- **How:** `subprocess.run(["claude", "--model", "haiku", "--print", "-p", prompt], ...)`

### 5) (Likely) other direct Claude CLI callers
A quick grep also showed `subprocess.run(["claude", ...])` in:
- `src/cub/core/punchlist/hydrator.py` (above)
- `src/cub/core/captures/slug.py` (above)
- `src/cub/core/ledger/extractor.py` (above)

If we want this to be exhaustive, we can do a full scan for `subprocess.run(["claude"` and enumerate all call sites.

---

## C) Bash layer — harness interface vs direct Claude calls

There’s also a legacy bash implementation under `src/cub/bash/`.

### Bash harness abstraction layer (interface)
- **Harness interface (bash):** YES
- **Where:** `src/cub/bash/lib/harness.sh`
- **Used by:** `src/cub/bash/cub` (sources `lib/harness.sh`)
- **What it does:** capability detection + standardized invocation for multiple harnesses (claude/opencode/codex/gemini).

### Bash scripts that call Claude directly (bypass bash harness layer)
These scripts call `claude ...` directly rather than using `harness_invoke...`:

- `src/cub/bash/lib/cmd_prep.sh`
  - Has `_claude_prompt_to_file()` that runs `claude -p ...` (with TTY workaround)
  - Invokes slash commands directly, e.g.:
    - `claude --dangerously-skip-permissions "/cub:orient ..."`
    - `claude --dangerously-skip-permissions "/cub:architect ..."`
    - `claude --dangerously-skip-permissions "/cub:itemize ..."`

- `src/cub/bash/lib/cmd_interview.sh`
  - Directly calls `claude --print --model sonnet ...` (based on grep hits)

- `src/cub/bash/lib/guardrails.sh`
  - Directly calls `claude --model haiku/sonnet --no-stream ...` for curation steps

---

## D) Suggested follow-ups (to tighten Cub’s architecture)

1) **Make “plan/spec/triage/interview” harness-agnostic (where possible)**
   - Today, those flows are tightly coupled to Claude slash commands.
   - Options:
     - Keep slash-command approach for Claude, but route invocation through a harness backend capability like `supports_feature(SLASH_COMMANDS)`.
     - Add parallel non-Claude implementations (or degrade to prompt-based mode).

2) **Move direct Claude CLI calls (slug/punchlist/ledger extraction) behind the harness**
   - These could become:
     - `harness.analyze(...)` for extraction tasks, or
     - a lightweight `harness.run_task(...)` with a dedicated system prompt.

3) **Document the intent**
   - Some “direct calls” may be intentional (fast, cheap, haiku-only, best-effort).
   - If so, explicitly mark them in code/comments: “intentionally bypasses harness for now.”

# Curb Architecture Review & Growth Strategy

## Executive Summary

Curb has matured from a simple script into a sophisticated task orchestration system. While the current Bash implementation is impressive and well-tested, the proposed roadmap (web interface, networked monitoring, dynamic resource management) exceeds the natural capabilities of a pure Bash environment.

**Recommendation:** Adopt a **hybrid architecture** immediately, migrating complex logic to **Go (Golang)** while retaining Bash for the top-level "glue" and user-facing CLI entry point during the transition. This provides the performance and type safety needed for future features without a complete rewrite-the-world stalling period.

---

## The Case for Bash (And Why It's Reaching Its Limit)

### Strengths of Current Approach
*   **"Glue" Efficiency:** Bash excels at piping output between tools (`git`, `jq`, `llm-cli`), which is 80% of what Curb does today.
*   **No Build Step:** Users can git clone and run. There's no binary to compile or cross-reference.
*   **Test Suite:** The BATS test suite is comprehensive (`tests/tasks.bats` etc.), providing a high degree of confidence that is rare in Bash projects.

### Limitations for Roadmap Features
1.  **Complex Data Structures:** Future features like "dynamic LLM resource management" require tracking state, costs, and performance history in memory. Bash has no structs or objects, forcing fragile JSON passing.
2.  **Networking & Concurrency:** `curb-hub` monitoring requires asynchronous networking. Bash's background jobs (`&`) and `curl` calls are hard to manage robustly (timeouts, retries, race conditions).
3.  **Web Interface:** A web view requires a persistent HTTP server. Bash cannot do this effectively.
4.  **Performance:** As task lists grow, `jq` operations in loops (O(n^2) for dependency resolution) will become noticeably slow.

---

## Logical Separation & Utility Extraction

To prepare for growth, we should begin extracting distinct domains into standalone utilities or libraries.

### 1. `curb-core` (The Brain)
*   **Current State:** `lib/tasks.sh` (jq logic).
*   **Future:** A compiled binary (Go) that handles state management.
*   **Responsibility:**
    *   Parsing `prd.json` / Beads tasks.
    *   Resolving dependency graphs.
    *   Selecting the next task based on priority/labels.
    *   Calculating budget and resource allocation.
*   **Why:** Strongly typed structs allow for complex dependency graph algorithms that are painful in `jq`.

### 2. `curb-hub` (The Network)
*   **Current State:** Non-existent.
*   **Future:** A centralized server or peer-to-peer agent.
*   **Responsibility:**
    *   Ingesting telemetry from active Curb runs.
    *   Providing a dashboard API for the web interface.
    *   Syncing state between agents.

### 3. `curb-driver` (The Hands)
*   **Current State:** `lib/harness.sh`.
*   **Future:** Plugin interface.
*   **Responsibility:**
    *   Standardizing the interface between Curb and LLMs (Claude, OpenAI, etc.).
    *   Handling retries, rate limits, and cost tracking.

---

## Strategic Recommendations

### Preferred Path: Migration to Go (Golang)
Go is the industry standard for CLI tools (Kubernetes, Docker, gh CLI) and fits Curb's needs perfectly.

*   **Libraries:**
    *   **CLI:** `spf13/cobra` (standard for CLIs) or `urfave/cli`.
    *   **UI:** `charmbracelet/bubbletea` for a rich, interactive TUI (Terminal User Interface) – would make `cub status` beautiful.
    *   **JSON:** Native standard library support.
    *   **Git:** `go-git` for native git operations without shelling out.

*   **SDLC Benefits:**
    *   **Testing:** Native `go test` is orders of magnitude faster than BATS.
    *   **CI/CD:** compile to a single binary for Mac/Linux/Windows. Easy to release via Homebrew/GitHub Releases.
    *   **Type Safety:** Eliminates entire classes of "empty variable" bugs common in Bash.

### Alternative Path: Python
If the team is more comfortable with Python (especially given the AI domain), it is a valid choice, though distribution is harder.

*   **Libraries:**
    *   **CLI:** `Typer` or `Click`.
    *   **TUI:** `Textual` (rich web-like TUI).
    *   **AI:** `LangChain` or `LiteLLM` for easier integration with new models.
*   **Cons:** Requires managing Python versions/virtualenvs on user machines (`pipx` helps, but adds friction).

---

## Implementation Plan

### Phase 1: The "Strangler Fig" Pattern
Don't rewrite everything at once. Replace the slow/complex parts first.

1.  **Replace `lib/tasks.sh` logic with a Go binary (`curb-engine`).**
    *   Keep the Bash CLI entry point.
    *   Bash calls `curb-engine get-next-task` instead of using complex `jq`.
    *   *Gain:* Speed and reliability in task selection.

### Phase 2: Rich TUI & Monitoring
1.  **Replace `cub status` with a Bubbletea (Go) TUI.**
    *   Provides a live, auto-updating dashboard.
2.  **Build `curb-hub` MVP.**
    *   A simple Go server that accepts JSON payloads from the `curb` CLI.

### Phase 3: Full Rewrite (Optional)
Once the core logic and UI are in Go, the remaining Bash "glue" (running git commands) can be trivially ported, resulting in a single binary executable.

## SDLC & CI Integration

*   **Testing:**
    *   **Unit:** Migrate logic tests to Go `testing` package.
    *   **Integration:** Keep BATS for end-to-end tests (treating the Go binary as a black box).
*   **Release:**
    *   Use **GoReleaser** in GitHub Actions to automatically build and attach binaries to releases.
    *   Maintain the Bash installer for backward compatibility, but have it download the binary.

## Clarification on "Curb Hub"
Building a web interface for active runs suggests a client-server model.
*   **Local:** Curb starts a local web server (`localhost:8080`) to view progress.
*   **Remote:** Curb sends events to a hosted `hub.curb.dev`.
*   **Recommendation:** Start with the local web server embedded in the Go binary. It's zero-config for users and high value.

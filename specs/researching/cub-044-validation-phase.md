---
status: researching
priority: high
complexity: medium
dependencies:
- reliability-phase
blocks: []
created: 2026-01-26
updated: 2026-01-26
readiness:
  score: 6
  blockers: []
  questions:
  - What's the full list of pytest markers to add?
  - Where should test_plan.yaml live? (tests/? .cub/?)
  - How should agent validation report results? (JSONL? GitHub issues? both?)
  decisions_needed:
  - Alpha-blocker criteria (what failures block release vs. become known issues)
  - Agent validation scope (just README? all docs? specific workflows?)
  tools_needed: []
spec_id: cub-044
---
# Validation Phase (0.30 Alpha)

## Overview

Build testing infrastructure for ongoing validation—not just one-time manual testing. This phase creates a repeatable, growable testing regime with three components: pytest markers for automated test categorization, a structured test plan for human validation workflows, and agent-driven testing for automated doc/onboarding validation.

## Goals

- **Test Categorization (E7):** Extend pytest markers to categorize tests by test plan categories (installation, task_management, run_loop, etc.) and criticality (alpha_blocker). Enable targeted test runs via `pytest -m "alpha_blocker"`.

- **Human Testing Checklist (E7):** Create structured test plan YAML that tracks both automated and manual tests. Single source of truth for what needs validation, with clear mapping to pytest tests where automated.

- **Agent-Driven Validation (E8):** Build a harness that spawns an agent to follow documentation as a "fresh eyes" user. Agent attempts workflows on greenfield projects, reports what works, what fails, and what's confusing. Automated dogfooding of the onboarding experience.

- **Repeatable Execution:** Tools for streamlined test execution that Marc can run repeatedly. Infrastructure that grows with the project.

## Non-Goals

- **100% automation:** Human judgment still needed for UX, taste, and subjective quality. The goal is to automate what can be automated, not replace human testing entirely.

- **Exhaustive edge case coverage:** Focus on happy paths and critical failure modes for alpha. Comprehensive edge case testing is post-alpha work.

- **Cross-platform matrix testing:** Pick representative targets (macOS, one Linux distro, Python 3.10+). Full matrix testing is post-alpha.

- **Backfilling existing tests:** New markers and categories apply going forward. No requirement to retrofit all 779 existing tests immediately.

## Design / Approach

### Component 1: Pytest Marker Extension

Extend the existing strict_markers configuration to support test plan categories:

```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "asyncio: mark test as an async test",
    # Criticality
    "alpha_blocker: failure blocks 0.30 release",
    "human_validation: requires human judgment, not fully automatable",
    # Test plan categories (from E7 test plan)
    "installation: Installation & Setup tests",
    "task_management: Task Management / JSON Backend tests",
    "plan_pipeline: Plan Pipeline tests",
    "run_loop: Run Loop / Core tests",
    "harness_integration: Harness Integration tests",
    "git_integration: Git Integration tests",
    "artifacts: Artifacts & Observability tests",
    "hooks: Hooks System tests",
]
```

**Usage patterns:**
- `pytest -m "alpha_blocker"` — run only release-blocking tests
- `pytest -m "installation"` — run installation category
- `pytest -m "run_loop and not human_validation"` — run automated run_loop tests
- `pytest -m "alpha_blocker and installation"` — critical installation tests

**Benefits:**
- Colocated with code (markers on test functions)
- CI/CD integration (run categories on different triggers)
- Already have `--strict-markers` so typos caught immediately
- Builds on established pytest patterns

### Component 2: Test Plan YAML

Create structured test plan that tracks both automated and manual validation:

```yaml
# tests/test_plan.yaml (or .cub/test_plan.yaml)
version: "0.30-alpha"
categories:
  - id: installation
    name: Installation & Setup
    description: Verify cub can be installed and initialized
    tests:
      - id: install-pip
        description: "pip install cub succeeds on fresh venv"
        automated: true
        pytest_marker: installation
        pytest_match: "test_installation.py::test_pip_install*"
        alpha_blocker: true

      - id: install-pipx
        description: "pipx install cub succeeds"
        automated: false
        human_steps:
          - "Run: pipx install cub"
          - "Verify: cub --version shows version"
          - "Verify: cub --help shows commands"
        alpha_blocker: true

      - id: init-project
        description: "cub init creates valid .cub.json"
        automated: true
        pytest_marker: installation
        pytest_match: "test_init.py::test_init_creates_config"
        alpha_blocker: true

  - id: run_loop
    name: Run Loop / Core
    description: Verify cub run executes reliably
    tests:
      - id: run-once-happy
        description: "cub run --once completes on simple task"
        automated: true
        pytest_marker: run_loop
        pytest_match: "test_run.py::test_run_once*"
        alpha_blocker: true

      - id: ctrl-c-clean
        description: "Ctrl+C during run exits cleanly"
        automated: false
        human_steps:
          - "Start: cub run"
          - "Press Ctrl+C during execution"
          - "Verify: Clean exit message, no traceback"
          - "Verify: No data corruption in .cub/"
        alpha_blocker: true
```

**CLI tooling:**
```bash
# Show test plan status
cub test-plan status
# Output: 53 tests total, 38 automated, 15 manual, 0 executed

# Run automated tests for a category
cub test-plan run installation
# Runs: pytest -m "installation"

# Show manual test checklist
cub test-plan checklist --category run_loop
# Output: Interactive checklist for human execution

# Mark manual test as passed/failed
cub test-plan record ctrl-c-clean --status pass --notes "Clean exit observed"
```

**Benefits:**
- Single source of truth for test coverage
- Mix of automated + manual tests in one view
- Progress tracking for human testing campaigns
- Can generate reports for release readiness

### Component 3: Agent-Driven Doc Validation

Build a test harness for E8 (External Project Validation) that uses an agent as a "fresh eyes" user:

```bash
# Validate README onboarding flow
cub validate-onboarding --readme

# Validate specific workflow
cub validate-onboarding --workflow quickstart

# Validate on external project (greenfield)
cub validate-onboarding --init-fresh --project-dir /tmp/test-project
```

**How it works:**

1. **Setup:** Create isolated environment (temp dir, fresh venv, no prior state)

2. **Agent spawn:** Launch agent (Claude Code or similar) with instructions:
   - "You are a new user trying cub for the first time"
   - "Follow the README Quick Start exactly as written"
   - "Report each step: what you tried, what happened, any confusion"

3. **Execution:** Agent attempts each step, captures:
   - Commands executed and their output
   - Success/failure status
   - Subjective notes ("instruction unclear", "unexpected behavior")

4. **Reporting:** Generate structured report:
   ```yaml
   # .cub/validation/onboarding-2026-01-26.yaml
   workflow: quickstart
   agent: claude-code
   timestamp: 2026-01-26T10:30:00Z
   environment:
     os: darwin
     python: 3.11.0
     fresh_install: true
   steps:
     - instruction: "pip install cub"
       command: "pip install cub"
       status: success
       output: "Successfully installed cub-0.30.0a1"
       notes: null

     - instruction: "Run cub init"
       command: "cub init"
       status: success
       output: "Created .cub.json"
       notes: "Instruction says 'cub init' but help shows 'cub init --help' first. Minor confusion."

     - instruction: "Create a task"
       command: "cub task create 'Fix typo in README'"
       status: failure
       output: "Error: Unknown command 'task'"
       notes: "README says 'cub task create' but command doesn't exist. Doc is out of date."
   summary:
     total_steps: 8
     passed: 6
     failed: 2
     issues:
       - "Step 5: 'cub task create' command doesn't exist"
       - "Step 7: Expected output doesn't match actual"
   ```

5. **Issue creation (optional):** Auto-file GitHub issues for failures:
   ```bash
   cub validate-onboarding --readme --create-issues
   ```

**Benefits:**
- Catches doc drift automatically
- "Fresh eyes" perspective without human time
- Repeatable—run on every release candidate
- Structured output for tracking improvements over time

## Implementation Notes

### Marker Extension

- Update `pyproject.toml` with new markers
- Add markers to existing tests incrementally (start with alpha_blocker critical path)
- Document marker usage in CONTRIBUTING.md
- Add CI job that runs `pytest -m "alpha_blocker"` on every PR

### Test Plan YAML

- Design schema for test plan format
- Build `cub test-plan` CLI command (new subcommand)
- Implement status, run, checklist, record subcommands
- Store execution history in `.cub/test-results/`

### Agent Validation

- Design prompt for "fresh user" agent behavior
- Build isolation harness (temp dir, fresh venv)
- Implement step-by-step execution with output capture
- Design report schema
- Optional: GitHub issue creation integration

## Open Questions

1. **Marker granularity:** Should every test have a category marker, or only tests explicitly in the test plan?

2. **Test plan location:** `tests/test_plan.yaml` (with code) or `.cub/test_plan.yaml` (with cub config)?

3. **Agent validation scope:** Start with just README Quick Start, or include other docs (CONTRIBUTING, UPGRADING)?

4. **Failure classification:** What's the rubric for "alpha_blocker" vs "known issue"? Need clear criteria.

5. **Agent choice:** Use cub's own harness system to spawn the validation agent, or separate tooling?

## Future Considerations

- **Visual regression testing:** Screenshots of CLI output for Rich tables/progress bars
- **Performance benchmarking:** Track test suite execution time over releases
- **Mutation testing:** Verify test quality by introducing bugs
- **Cross-platform CI:** Expand to Windows, multiple Python versions post-alpha
- **Community test contributions:** Structure for external contributors to add tests

---

**Status**: researching
**Last Updated**: 2026-01-26

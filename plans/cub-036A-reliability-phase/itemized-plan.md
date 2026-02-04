# Itemized Plan: Reliability Phase (0.30 Alpha)

> Source: [reliability-phase.md](../../specs/researching/reliability-phase.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-26

## Context Summary

Solo builders running overnight `cub run` sessions can't trust the loop—it might crash, hang for hours on a stuck task, or lose track of work they did directly in Claude Code. The reliability phase delivers three capabilities: rock-solid core loop, hang detection, and unified tracking regardless of entry point.

**Mindset:** Production | **Scale:** Personal

---

## Epic: cub-orphan-14 - reliability-phase #1: Core Loop Hardening

Priority: 0
Labels: phase-1, e4, hardening

Verify and strengthen existing exit handling in `cub run`. The foundation is solid—this is primarily testing, documentation, and edge case fixes. Goal: `cub run` exits cleanly on all paths with artifacts preserved.

### Task: cub-orphan-14.1 - Audit run.py exit paths

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, audit
Blocks: cub-orphan-14.2, cub-orphan-14.3

**Context**: Before adding tests, we need to document current behavior. This audit identifies all exit paths and their current artifact-preservation status.

**Implementation Steps**:
1. Read through `src/cub/cli/run.py` and identify all exit points (return statements, sys.exit, exceptions)
2. For each exit path, document: trigger condition, whether `write_run_artifact()` is called, whether status is persisted
3. Identify gaps where artifacts might not be created
4. Create a markdown document in `.cub/docs/` summarizing findings

**Acceptance Criteria**:
- [ ] Document lists all exit paths in run.py with line numbers
- [ ] Each path annotated with artifact preservation status
- [ ] Gaps identified and prioritized for fixing
- [ ] Document saved to `.cub/docs/run-exit-paths.md`

**Files**: src/cub/cli/run.py, .cub/docs/run-exit-paths.md

---

### Task: cub-orphan-14.2 - Integration tests for exit scenarios

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, test
Blocks: cub-orphan-14.3

**Context**: We need automated tests that verify clean exits on all paths. These tests ensure regressions are caught early.

**Implementation Steps**:
1. Add `pytest-timeout` to dev dependencies if not present
2. Create `tests/integration/test_run_exits.py`
3. Write tests for: Ctrl+C (SIGINT), SIGTERM, budget exhaustion, iteration limit reached, task failure
4. Each test should verify: clean exit (no crash), status.json updated, run artifact created
5. Use subprocess to run `cub run` and send signals

**Acceptance Criteria**:
- [ ] Test for SIGINT exits cleanly with artifacts
- [ ] Test for SIGTERM exits cleanly with artifacts
- [ ] Test for budget exhaustion stops with clear message
- [ ] Test for iteration limit stops with clear message
- [ ] Test for task failure handled per config (stop/move-on)
- [ ] All tests use pytest-timeout to prevent hangs

**Files**: tests/integration/test_run_exits.py, pyproject.toml

---

### Task: cub-orphan-14.3 - Ensure artifacts on all exits

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, fix

**Context**: Based on audit findings, fix any exit paths that don't preserve artifacts. This is the core deliverable of E4.

**Implementation Steps**:
1. Review gaps identified in cub-orphan-14.1 audit
2. Add try/finally blocks where needed to ensure `write_run_artifact()` is called
3. Ensure `StatusWriter.write()` is called before any exit
4. Handle edge cases: exceptions during artifact write, partial state
5. Run integration tests to verify fixes

**Acceptance Criteria**:
- [ ] All exit paths identified in audit now preserve artifacts
- [ ] Status.json always reflects final state on exit
- [ ] Run artifact created even on interrupt/failure
- [ ] Integration tests from cub-orphan-14.2 all pass

**Files**: src/cub/cli/run.py, src/cub/core/status/writer.py

---

### Task: cub-orphan-14.4 - Manual testing protocol for E4

Priority: 1
Labels: phase-1, model:haiku, complexity:low, docs, checkpoint

**Context**: Automated tests can't catch everything. Create a checklist for Marc to manually validate exit behavior.

**Implementation Steps**:
1. Create manual test checklist in `plans/reliability-phase/e4-manual-tests.md`
2. Include scenarios: overnight run, Ctrl+C at various points, kill -9, budget warning then exhaustion
3. Document expected behavior and what to check (files created, messages shown)
4. Include recovery steps if something goes wrong

**Acceptance Criteria**:
- [ ] Checklist covers all exit scenarios
- [ ] Each scenario has clear pass/fail criteria
- [ ] Recovery steps documented for failures
- [ ] Checklist is actionable by non-developer

**Files**: plans/reliability-phase/e4-manual-tests.md

---

## Epic: cub-orphan-13 - reliability-phase #2: Circuit Breaker

Priority: 0
Labels: phase-2, e5, circuit-breaker

Add timeout monitoring to harness execution. If no harness activity for 30 minutes, trip breaker and stop run with clear message. Prevents overnight runs from wasting hours on stuck tasks.

### Task: cub-orphan-13.1 - Add CircuitBreakerConfig

Priority: 0
Labels: phase-2, model:haiku, complexity:low, config
Blocks: cub-orphan-13.2

**Context**: Configuration must exist before we can implement the circuit breaker. This adds the config model and wires it into CubConfig.

**Implementation Steps**:
1. Add `CircuitBreakerConfig` class to `src/cub/core/config/models.py`
2. Fields: `enabled: bool = True`, `timeout_minutes: int = 30`
3. Add `circuit_breaker: CircuitBreakerConfig` field to `CubConfig`
4. Add environment variable support: `CUB_CIRCUIT_BREAKER_ENABLED`, `CUB_CIRCUIT_BREAKER_TIMEOUT`
5. Update config documentation

**Acceptance Criteria**:
- [ ] CircuitBreakerConfig model exists with enabled and timeout_minutes fields
- [ ] CubConfig includes circuit_breaker field with default
- [ ] Environment variables override config file values
- [ ] Config loads correctly from .cub.json

**Files**: src/cub/core/config/models.py, docs/CONFIG.md

---

### Task: cub-orphan-13.2 - Implement CircuitBreaker class

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, core
Blocks: cub-orphan-13.3

**Context**: The core circuit breaker logic. Uses asyncio timeout to detect hung harness execution.

**Implementation Steps**:
1. Create `src/cub/core/circuit_breaker.py`
2. Implement `CircuitBreaker` class with:
   - `__init__(timeout_minutes, enabled)`
   - `async execute(coro)` - wraps coroutine with `asyncio.wait_for`
   - `record_activity()` - resets timeout (for future activity detection)
   - `is_tripped` property
3. On timeout: raise `CircuitBreakerTripped` exception with clear message
4. Handle graceful cancellation of the wrapped coroutine
5. Write unit tests

**Acceptance Criteria**:
- [ ] CircuitBreaker class implemented with execute() method
- [ ] Timeout triggers CircuitBreakerTripped exception
- [ ] Exception message includes timeout duration and suggestion to use --no-circuit-breaker
- [ ] Disabled circuit breaker passes through without timeout
- [ ] Unit tests cover: normal execution, timeout, disabled mode

**Files**: src/cub/core/circuit_breaker.py, tests/unit/test_circuit_breaker.py

---

### Task: cub-orphan-13.3 - Integrate circuit breaker into run.py

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, integration

**Context**: Wire the circuit breaker into the run loop so harness invocations are timeout-protected.

**Implementation Steps**:
1. Import CircuitBreaker in `src/cub/cli/run.py`
2. Create CircuitBreaker instance from config in run initialization
3. Wrap `_invoke_harness()` call with `circuit_breaker.execute()`
4. Handle `CircuitBreakerTripped` exception: log, update status, exit cleanly with artifacts
5. Add circuit breaker status to run summary output

**Acceptance Criteria**:
- [ ] Harness invocation wrapped with circuit breaker
- [ ] Timeout trips breaker and stops run cleanly
- [ ] Status shows "stopped: circuit breaker tripped"
- [ ] Artifacts preserved on circuit breaker trip
- [ ] Run summary mentions if circuit breaker tripped

**Files**: src/cub/cli/run.py

---

### Task: cub-orphan-13.4 - Add --no-circuit-breaker CLI flag

Priority: 1
Labels: phase-2, model:haiku, complexity:low, cli

**Context**: Users need ability to disable circuit breaker for legitimately long operations.

**Implementation Steps**:
1. Add `--no-circuit-breaker` flag to `cub run` command
2. Flag sets `config.circuit_breaker.enabled = False`
3. Document flag in `cub run --help`
4. Add example to README showing when to use it

**Acceptance Criteria**:
- [ ] `cub run --no-circuit-breaker` disables timeout
- [ ] Flag documented in --help output
- [ ] README mentions flag for long operations

**Files**: src/cub/cli/run.py, README.md

---

### Task: cub-orphan-13.5 - Add "giving up" escape hatch to prompts

Priority: 1
Labels: phase-2, model:haiku, complexity:low, prompt, checkpoint

**Context**: Complement time-based detection with agent self-awareness. Add instruction letting agents signal when they're stuck.

**Implementation Steps**:
1. Update `templates/PROMPT.md` with escape hatch section
2. Add instruction: "If you are stuck and cannot make progress, output: <stuck>REASON</stuck>"
3. Document that this complements (doesn't replace) circuit breaker
4. Consider: should run.py detect this signal? (Future enhancement, document but don't implement)

**Acceptance Criteria**:
- [ ] PROMPT.md includes escape hatch instruction
- [ ] Instruction is clear and actionable for agents
- [ ] Documented as complementary to circuit breaker

**Files**: templates/PROMPT.md

---

## Epic: cub-orphan-15 - reliability-phase #3: Symbiotic Workflow

Priority: 1
Labels: phase-3, e6, symbiotic

Unified audit trail for direct harness sessions. When users run Claude Code/Codex directly, CLAUDE.md/AGENTS.md instructions + hooks ensure ledger captures equivalent records to `cub run`.

### Task: cub-orphan-15.1 - Create direct session CLI commands

Priority: 0
Labels: phase-3, model:sonnet, complexity:medium, cli
Blocks: cub-orphan-15.2, cub-orphan-15.6

**Context**: Direct sessions need commands to record work. These are the integration layer between harness and ledger.

**Implementation Steps**:
1. Create `src/cub/cli/session.py` with Typer app
2. Implement `cub log <message>` - adds timestamped entry to session log
3. Implement `cub done <task-id> [--reason]` - marks task complete, creates ledger entry
4. Implement `cub wip <task-id>` - marks task in-progress
5. Register commands in main CLI app
6. Add `source: "direct_session"` to ledger entries created by these commands

**Acceptance Criteria**:
- [ ] `cub log "message"` creates session log entry
- [ ] `cub done task-id` marks task complete and creates ledger entry
- [ ] `cub wip task-id` marks task in-progress
- [ ] Ledger entries have `source: "direct_session"`
- [ ] Commands work without `cub run` active

**Files**: src/cub/cli/session.py, src/cub/cli/__init__.py

---

### Task: cub-orphan-15.2 - Implement InstructionGenerator

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, core
Blocks: cub-orphan-15.3

**Context**: Generate CLAUDE.md and AGENTS.md with workflow instructions that guide agents to use cub commands.

**Implementation Steps**:
1. Create `src/cub/core/instructions.py`
2. Implement `generate_agents_md(project_dir, config)` - harness-agnostic instructions
3. Implement `generate_claude_md(project_dir, config)` - Claude-specific additions
4. Include sections: finding tasks (`cub status`), claiming work (`cub wip`), completing (`cub done`), logging (`cub log`)
5. Include escape hatch language from E5
6. Make output customizable via config (future: templates)

**Acceptance Criteria**:
- [ ] `generate_agents_md()` produces valid markdown with workflow instructions
- [ ] `generate_claude_md()` includes Claude-specific guidance
- [ ] Instructions reference correct cub commands
- [ ] Output includes escape hatch language

**Files**: src/cub/core/instructions.py, tests/unit/test_instructions.py

---

### Task: cub-orphan-15.3 - Update cub init for AGENTS.md

Priority: 1
Labels: phase-3, model:sonnet, complexity:low, cli

**Context**: `cub init` should create AGENTS.md at project root for cross-harness compatibility.

**Implementation Steps**:
1. Update `src/cub/cli/init_cmd.py` to call InstructionGenerator
2. Generate AGENTS.md at project root (not in .cub/)
3. Generate/update CLAUDE.md at project root
4. Don't overwrite if files exist (or prompt user)
5. Add success message mentioning the files created

**Acceptance Criteria**:
- [ ] `cub init` creates AGENTS.md at project root
- [ ] `cub init` creates/updates CLAUDE.md at project root
- [ ] Existing files not overwritten without confirmation
- [ ] Init output mentions files created

**Files**: src/cub/cli/init_cmd.py

---

### Task: cub-orphan-15.4 - Research Claude Code hooks

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, research
Blocks: cub-orphan-15.5

**Context**: Understand what hooks Claude Code exposes for artifact capture. This informs whether we can auto-capture or must rely on instructions.

**Implementation Steps**:
1. Review Claude Code documentation for hooks system
2. Test available hook events: PreToolUse, PostToolUse, Stop, PermissionRequest
3. Document payload structure for each relevant event
4. Identify: can we detect session start/end? Can we capture plan content?
5. Write findings to `.cub/docs/claude-code-hooks.md`

**Acceptance Criteria**:
- [ ] Document lists available Claude Code hook events
- [ ] Payload structure documented for relevant events
- [ ] Session detection feasibility assessed
- [ ] Plan capture feasibility assessed
- [ ] Findings saved to .cub/docs/

**Files**: .cub/docs/claude-code-hooks.md

---

### Task: cub-orphan-15.5 - Implement hook handlers for artifact capture

Priority: 2
Labels: phase-3, model:sonnet, complexity:medium, hooks

**Context**: Based on hook research, implement handlers to auto-capture artifacts when possible.

**Implementation Steps**:
1. Create `src/cub/core/harness/hooks.py`
2. Implement `handle_hook_event(event_type, payload)` dispatcher
3. For PostToolUse/Write: detect writes to plans/, log to ledger
4. For Stop: capture session end, finalize any open ledger entries
5. Parse payloads defensively (malformed → skip, don't crash)
6. Create hook scripts for `.cub/hooks/` that call these handlers

**Acceptance Criteria**:
- [ ] Hook handler dispatches events to appropriate functions
- [ ] Write events to plans/ are logged
- [ ] Session end captured if detectable
- [ ] Malformed payloads handled gracefully
- [ ] Hook scripts created for Claude Code integration

**Files**: src/cub/core/harness/hooks.py, .cub/hooks/

---

### Task: cub-orphan-15.6 - Manual testing: direct session workflow

Priority: 1
Labels: phase-3, model:haiku, complexity:low, test, checkpoint

**Context**: The ultimate validation: Marc runs Claude Code directly and verifies the ledger captures work naturally.

**Implementation Steps**:
1. Create test protocol in `plans/reliability-phase/e6-manual-tests.md`
2. Scenarios: start direct session, claim task with `cub wip`, do work, complete with `cub done`
3. Verify: ledger entry created, task status updated, session log captured
4. Test friction: is the workflow natural? What's awkward?
5. Document findings and iterate

**Acceptance Criteria**:
- [ ] Test protocol documented
- [ ] Direct session produces ledger entry
- [ ] Task status updates correctly
- [ ] UX friction points identified
- [ ] Findings documented for iteration

**Files**: plans/reliability-phase/e6-manual-tests.md

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-orphan-14 | 4 | P0 | Core Loop Hardening - clean exits on all paths |
| cub-orphan-13 | 5 | P0 | Circuit Breaker - time-based hang detection |
| cub-orphan-15 | 6 | P1 | Symbiotic Workflow - unified audit trail |

**Total**: 3 epics, 15 tasks

**Checkpoints**:
- After cub-orphan-14.4: E4 complete - `cub run` is crash-proof
- After cub-orphan-13.5: E5 complete - hung harness detection works
- After cub-orphan-15.6: E6 complete - direct sessions produce ledger entries

**Ready to start**: cub-orphan-14.1 (Audit run.py exit paths)

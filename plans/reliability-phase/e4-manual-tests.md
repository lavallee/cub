# E4 Manual Testing Protocol: Core Loop Hardening

**Objective:** Validate that `cub run` exits cleanly with preserved artifacts on all paths.

**Audience:** QA testers, Marc (project lead), release team

**Testing Duration:** ~30-45 minutes total across all scenarios

**Prerequisites:**
- Complete `cub-r4h.1` (exit path audit) and `cub-r4h.2` (integration tests)
- Have a test project directory with sample tasks
- Understand basic cub commands and task structure
- Access to terminal with signal handling capabilities (Unix/Linux/macOS)

---

## Test Environment Setup

### 1.1 Create a Test Project

```bash
# Create a clean test directory
mkdir -p /tmp/cub-e4-test
cd /tmp/cub-e4-test

# Initialize git (required by cub)
git init
git config user.email "test@example.com"
git config user.name "E4 Tester"

# Initialize cub with JSONL backend (no dependencies)
cub init --backend jsonl

# Create some test tasks with varying priorities
cub task create "Quick task (1min)" --priority 0
cub task create "Medium task (5min)" --priority 1
cub task create "Long task (15min)" --priority 1
cub task create "Budget test task" --priority 2
```

### 1.2 Verify Setup

```bash
# Confirm tasks created
cub task list

# Confirm directory structure
ls -la .cub/
# Should show: ledger/, status/, tasks.jsonl, .cub.json, CLAUDE.md

# Confirm status.json exists
ls -la .cub/status.json
```

**✓ PASS:** All tasks visible, directory structure correct

---

## Test Scenarios

Each scenario has:
- **Trigger:** How to start the test
- **Expected Behavior:** What should happen
- **Verification Steps:** What to check
- **Pass/Fail Criteria:** Objective success measures

---

### Scenario 1: Normal Completion (Happy Path)

**Purpose:** Baseline test that cub run completes normally without interruption.

**Trigger:**
```bash
# Run single iteration to complete one task
cub run --once --no-monitor
```

**Expected Behavior:**
- Runs harness on available task
- Completes without error
- Exits with code 0
- Displays summary message

**Verification Steps:**

1. **Check exit code:**
   ```bash
   echo $?
   # Should output: 0
   ```

2. **Check status.json updated:**
   ```bash
   cat .cub/status.json | jq '.status'
   # Should show: "completed" or "paused"
   ```

3. **Check run artifact created:**
   ```bash
   ls -la .cub/status/*/run.json
   # Should list a file like: .cub/status/run-2026-01-26T...json
   ```

4. **Verify artifact contains metadata:**
   ```bash
   cat .cub/status/run-*/run.json | jq '.exit_code'
   # Should show: 0
   ```

5. **Check ledger entry (if task closed):**
   ```bash
   ls -la .cub/ledger/
   # May have new entries if task was completed by harness
   ```

**Pass Criteria:**
- [ ] Exit code is 0
- [ ] status.json exists and reflects final state
- [ ] run.json artifact exists in .cub/status/
- [ ] run.json contains `exit_code: 0`
- [ ] All file timestamps are recent (within last minute)

**Fail Recovery:**
- If exit code is non-zero: Check harness logs in `cub status --logs`
- If artifacts missing: Run `cub status` to see detailed state
- If file permissions issue: Check `.cub/` directory ownership with `ls -la .cub/`

---

### Scenario 2: Ctrl+C (SIGINT) During Run

**Purpose:** Verify graceful exit when user presses Ctrl+C.

**Trigger:**
```bash
# Start a run
cub run --no-monitor

# Wait ~3-5 seconds, then press Ctrl+C
# (Or in a script: send SIGINT after delay)
```

**Expected Behavior:**
- Run stops immediately after Ctrl+C
- Displays message: "Interrupted by user"
- Exits with code 130 (standard SIGINT exit code)
- All artifacts preserved

**Verification Steps:**

1. **Check exit code:**
   ```bash
   echo $?
   # Should output: 130 (SIGINT) or 2 (Ctrl+C variation)
   ```

2. **Check status.json:**
   ```bash
   cat .cub/status.json | jq '.status'
   # Should show: "interrupted" or "halted"
   ```

3. **Check run artifact:**
   ```bash
   cat .cub/status/run-*/run.json | jq '.exit_code, .exit_reason'
   # Should show exit_code: 130 (or 2) and exit_reason containing "interrupt" or "SIGINT"
   ```

4. **Verify task state preserved:**
   ```bash
   # Task should still be in-progress or open (not lost)
   cub task list | grep -E "(in_progress|open)"
   ```

5. **Check no partial artifacts:**
   ```bash
   # No truncated or corrupted files
   find .cub/ -type f -size 0
   # Should output nothing (no empty files)
   ```

**Pass Criteria:**
- [ ] Exit code is 130 or 2 (SIGINT)
- [ ] status.json shows "interrupted" state
- [ ] run.json exists with exit_code and exit_reason
- [ ] No empty/corrupted files in .cub/
- [ ] Task state preserved (not deleted)

**Fail Recovery:**
- If exit code is 0: Process may not have received signal. Try running in foreground without redirection.
- If status.json missing/empty: Check `cub status` for errors
- If task lost: Check `.cub/tasks.jsonl` for integrity with `tail -10 .cub/tasks.jsonl`

---

### Scenario 3: SIGTERM (kill -TERM)

**Purpose:** Verify graceful shutdown from external termination signal.

**Trigger:**
```bash
# In one terminal, start run:
cub run --no-monitor

# In another terminal, find the process and send SIGTERM:
ps aux | grep "cub run"
kill -TERM <PID>
```

**Or use scripted approach:**
```bash
# Non-blocking run in background
cub run --no-monitor &
RUN_PID=$!

# Wait 3 seconds
sleep 3

# Send SIGTERM
kill -TERM $RUN_PID

# Wait for completion
wait $RUN_PID
echo "Exit code: $?"
```

**Expected Behavior:**
- Run stops after SIGTERM
- Displays message: "Terminated" or "Shutdown signal received"
- Exits with code 143 (standard SIGTERM exit code)
- All artifacts preserved (same as Ctrl+C)

**Verification Steps:**

1. **Check exit code:**
   ```bash
   echo $?
   # Should output: 143
   ```

2. **Check status.json:**
   ```bash
   cat .cub/status.json | jq '.status'
   # Should show: "terminated" or "halted"
   ```

3. **Check run artifact:**
   ```bash
   cat .cub/status/run-*/run.json | jq '.exit_code, .exit_reason'
   # Should show exit_code: 143 and exit_reason containing "SIGTERM"
   ```

4. **Verify no crash:**
   ```bash
   # Check for error messages in status
   cub status --detailed
   # Should show clean state, not "ERROR" or "CRASHED"
   ```

**Pass Criteria:**
- [ ] Exit code is 143
- [ ] status.json shows "terminated" state
- [ ] run.json exists with proper exit_code and exit_reason
- [ ] No error messages in `cub status`

**Fail Recovery:**
- If exit code is 0: SIGTERM may not be reaching process. Check process tree with `pstree`
- If signal ineffective: Harness may be unresponsive. Proceed to scenario 4 (SIGKILL)

---

### Scenario 4: SIGKILL (kill -9) - Force Termination

**Purpose:** Verify system behavior when process is forcefully killed (cannot be caught).

**Warning:** This is a destructive test. Use only after scenarios 1-3 pass.

**Trigger:**
```bash
# In background:
cub run --no-monitor &
RUN_PID=$!

# Wait 2 seconds
sleep 2

# Send SIGKILL (cannot be caught, process dies immediately)
kill -9 $RUN_PID

# Check what happened
wait $RUN_PID 2>/dev/null
echo "Exit code: $?"
```

**Expected Behavior:**
- Process killed immediately (cannot gracefully shutdown)
- Exit code 137 (128 + 9 for SIGKILL)
- Status/artifacts may be incomplete (this is unavoidable with SIGKILL)
- Status.json should still exist from before kill

**Verification Steps:**

1. **Check exit code:**
   ```bash
   echo $?
   # Should output: 137 (SIGKILL)
   ```

2. **Check status.json still exists:**
   ```bash
   cat .cub/status.json | jq '.status'
   # Should show previous state (not updated due to force kill)
   ```

3. **Verify run.json from last successful iteration:**
   ```bash
   # Last run artifact should exist
   ls -la .cub/status/run-*json | tail -1
   ```

4. **Check no database corruption:**
   ```bash
   # JSONL format should still be valid
   head -1 .cub/tasks.jsonl | jq . > /dev/null
   # If this succeeds, format is OK
   ```

**Pass Criteria:**
- [ ] Exit code is 137
- [ ] status.json exists from before kill
- [ ] tasks.jsonl still valid JSON lines (not corrupted)
- [ ] No partial/truncated run files

**Acceptable Failure:**
- Artifacts may be incomplete (this is expected with SIGKILL)
- Status may not show "killed" (graceful update not possible)
- This is testing system behavior, not cub bug

**Fail Recovery:**
- If tasks.jsonl corrupted: Restore from git with `git checkout .cub/tasks.jsonl`
- If status.json corrupted: Run `cub doctor` to repair

---

### Scenario 5: Budget Exhaustion (Token Limit)

**Purpose:** Verify run stops cleanly when token budget is exceeded.

**Setup:**
```bash
# Create a low budget config
cat > /tmp/cub-e4-test/.cub.json <<'EOF'
{
  "harness": {
    "name": "mock",
    "priority": ["mock"]
  },
  "budget": {
    "max_total_cost": 0.001,
    "max_tokens_per_task": 50
  },
  "loop": {
    "max_iterations": 10
  },
  "state": {
    "require_clean": false
  },
  "mock_harness": {
    "task_token_cost": 100
  }
}
EOF
```

**Trigger:**
```bash
# Run with mock harness that uses tokens
cub run --harness mock --no-monitor --budget 0.0005
```

**Expected Behavior:**
- Runs 1-2 tasks until budget exhausted
- Displays clear message: "Budget exhausted: spent $X.XX of $X.XX limit"
- Exits with code 0 (clean budget exhaustion, not error)
- Artifacts created showing budget state

**Verification Steps:**

1. **Check exit code:**
   ```bash
   echo $?
   # Should output: 0 (budget exhaustion is clean shutdown)
   ```

2. **Check status message:**
   ```bash
   cat .cub/status.json | jq '.message'
   # Should contain "budget" or "exhausted"
   ```

3. **Check run artifact:**
   ```bash
   cat .cub/status/run-*/run.json | jq '.reason, .budget_used'
   # Should show reason containing "budget" and budget_used field populated
   ```

4. **Verify task not partially run:**
   ```bash
   # Last task should be either completed or untouched (not in-progress)
   cub task list | grep in_progress
   # Should be empty or show completed tasks
   ```

**Pass Criteria:**
- [ ] Exit code is 0
- [ ] status.json contains budget exhaustion message
- [ ] run.json shows budget_used and reason
- [ ] No tasks left in "in_progress" state
- [ ] Message clearly explains budget exceeded

**Fail Recovery:**
- If exit code is non-zero: Check budget calculation in `cub status`
- If message unclear: Check stderr output with `cub run 2>&1 | tail -20`
- If task stuck in progress: `cub task update <id> --status open` to reset

---

### Scenario 6: Iteration Limit Reached

**Purpose:** Verify run stops when maximum iterations hit.

**Setup:**
```bash
# Config with low iteration limit
cat > /tmp/cub-e4-test/.cub.json <<'EOF'
{
  "harness": {
    "name": "mock",
    "priority": ["mock"]
  },
  "budget": {
    "max_total_cost": 100.0,
    "max_tokens_per_task": 1000
  },
  "loop": {
    "max_iterations": 2
  },
  "state": {
    "require_clean": false
  }
}
EOF
```

**Trigger:**
```bash
# Create 5 tasks so limit is hit before all complete
for i in {1..5}; do
  cub task create "Task $i"
done

# Run with iteration limit
cub run --no-monitor
```

**Expected Behavior:**
- Runs exactly 2 iterations (2 tasks processed)
- Displays message: "Iteration limit reached (2/2)"
- Exits with code 0 (not an error condition)
- Remaining tasks stay "open" (not touched)

**Verification Steps:**

1. **Check exit code:**
   ```bash
   echo $?
   # Should output: 0
   ```

2. **Check iteration count in status:**
   ```bash
   cat .cub/status.json | jq '.iterations_completed, .max_iterations'
   # Should show: 2, 2
   ```

3. **Check run artifact:**
   ```bash
   cat .cub/status/run-*/run.json | jq '.iterations, .reason'
   # Should show iterations: 2 and reason containing "limit"
   ```

4. **Verify untouched tasks:**
   ```bash
   # Count remaining open tasks
   cub task list | grep -c "open"
   # Should be 3 or more (5 created - 2 processed)
   ```

5. **Check log output:**
   ```bash
   cat .cub/status.json | jq '.message'
   # Should mention iteration limit
   ```

**Pass Criteria:**
- [ ] Exit code is 0
- [ ] Exactly max_iterations tasks were processed
- [ ] Remaining tasks still "open" (not touched)
- [ ] Message clearly states iteration limit reached
- [ ] run.json shows iterations field

**Fail Recovery:**
- If wrong number of iterations: Check loop config in `.cub.json`
- If message missing: Check status logs with `cub status --verbose`

---

### Scenario 7: Task Failure Handling

**Purpose:** Verify graceful handling when a task fails or encounters error.

**Setup:**
```bash
# Create a task that will fail
cub task create "Intentional failure task" --priority 0

# Use mock harness configured to fail
cat > /tmp/cub-e4-test/.cub.json <<'EOF'
{
  "harness": {
    "name": "mock",
    "priority": ["mock"]
  },
  "budget": {
    "max_total_cost": 100.0
  },
  "loop": {
    "max_iterations": 5,
    "on_task_failure": "continue"
  },
  "state": {
    "require_clean": false
  },
  "mock_harness": {
    "failure_mode": "error"
  }
}
EOF
```

**Trigger:**
```bash
# Run with continue-on-error
cub run --harness mock --no-monitor
```

**Expected Behavior:**
- Task fails, error logged
- Run continues to next task (per `on_task_failure: continue`)
- Displays warning about failed task
- Exits cleanly with code 0

**Verification Steps:**

1. **Check exit code:**
   ```bash
   echo $?
   # Should output: 0 (even though task failed)
   ```

2. **Check task status:**
   ```bash
   cub task show <task-id> | jq '.status'
   # Should show: "error" or "failed" (not "in_progress")
   ```

3. **Check run artifact:**
   ```bash
   cat .cub/status/run-*/run.json | jq '.failures'
   # Should list the failed task
   ```

4. **Check error logging:**
   ```bash
   # Check ledger for error entry
   grep -l "error" .cub/ledger/*
   # Should find at least one ledger entry with error
   ```

5. **Verify continued processing:**
   ```bash
   # Check that other tasks were processed
   cub task list | grep -E "(completed|closed)" | wc -l
   # Should be > 0 (at least one task processed after failure)
   ```

**Pass Criteria:**
- [ ] Exit code is 0 (clean shutdown despite failure)
- [ ] Failed task marked with error status
- [ ] run.json documents failure
- [ ] Following tasks still processed (continue behavior)
- [ ] Error logged to ledger

**Alternative: Stop on Failure**

If config has `on_task_failure: stop`:

```bash
# Change config
cat > /tmp/cub-e4-test/.cub.json <<'EOF'
{
  "loop": {
    "on_task_failure": "stop"
  }
}
EOF

# Run again
cub run --harness mock --no-monitor
```

**Expected:** Run stops after first failure, exits with code 1 (error)

**Pass Criteria (stop mode):**
- [ ] Exit code is 1 (error condition)
- [ ] status.json shows "error" or "failed" state
- [ ] run.json includes error message

**Fail Recovery:**
- If task not marked failed: Check harness logs with `cub status --logs`
- If run doesn't stop: Verify `on_task_failure` setting in config

---

### Scenario 8: Overnight Run (Extended Test)

**Purpose:** Verify robustness over extended time with multiple tasks.

**Warning:** This scenario takes time. Optional for full test suite.

**Setup:**
```bash
# Create 10 tasks to simulate realistic workload
for i in {1..10}; do
  cub task create "Production task $i" --priority $((i % 3))
done

# Set moderate budget and iteration limit
cat > /tmp/cub-e4-test/.cub.json <<'EOF'
{
  "harness": {
    "name": "mock",
    "priority": ["mock"]
  },
  "budget": {
    "max_total_cost": 50.0
  },
  "loop": {
    "max_iterations": 10
  },
  "state": {
    "require_clean": false
  }
}
EOF
```

**Trigger:**
```bash
# Run with monitor to watch progress
timeout 300 cub run --no-circuit-breaker &
MONITOR_PID=$!

# Optionally watch status
watch -n 2 'cub status'

# Let it run for a while (5+ minutes), then stop
# After timeout or manual interrupt
wait $MONITOR_PID
echo "Final exit code: $?"
```

**Expected Behavior:**
- Processes multiple tasks sequentially
- Status updates visible with each iteration
- Maintains stable memory/CPU (no resource leaks)
- Eventually hits budget or iteration limit
- Exits cleanly

**Verification Steps:**

1. **Check run completed:**
   ```bash
   cub status | grep -E "(completed|paused|halted)"
   # Should show final state
   ```

2. **Verify progress:**
   ```bash
   cat .cub/status.json | jq '.tasks_processed'
   # Should be > 0
   ```

3. **Check resource usage:**
   ```bash
   # If run is still going, check memory
   ps aux | grep "cub run" | grep -v grep
   # Should show reasonable memory usage (< 100MB typical)
   ```

4. **Verify no file corruption:**
   ```bash
   # Test JSONL validity
   jq -s '.' .cub/tasks.jsonl > /dev/null
   # Should succeed without JSON errors
   ```

5. **Check ledger:**
   ```bash
   ls -la .cub/ledger/ | wc -l
   # Should have entries for each processed task
   ```

**Pass Criteria:**
- [ ] Run completes without crash
- [ ] All artifacts present and valid
- [ ] Tasks processed successfully
- [ ] Memory/CPU usage reasonable
- [ ] No file corruption detected

**Fail Recovery:**
- If hung: Send SIGTERM (scenario 3)
- If memory leak: Check `cub status --diagnostics` for resource usage
- If file corruption: Restore from git

---

## Summary Checklist

Use this table to track all test results:

| Scenario | Pass/Fail | Notes | Run Date |
|----------|-----------|-------|----------|
| 1. Normal completion | [ ] | | |
| 2. Ctrl+C (SIGINT) | [ ] | | |
| 3. SIGTERM (kill -TERM) | [ ] | | |
| 4. SIGKILL (kill -9) | [ ] | | |
| 5. Budget exhaustion | [ ] | | |
| 6. Iteration limit | [ ] | | |
| 7. Task failure | [ ] | | |
| 8. Overnight run | [ ] | Optional | |

**Overall Result:**
- [ ] All critical scenarios (1-7) passed
- [ ] At least one extended test run (scenario 8)
- [ ] No data corruption detected
- [ ] Recovery procedures tested if needed

---

## Troubleshooting Guide

### Common Issues

**"Exit code is wrong"**
- Check platform (macOS/Linux may differ slightly)
- Verify signal is reaching process: `kill -l` to list signals
- Try sending from different terminal

**"Artifacts missing"**
- Check permissions: `ls -la .cub/`
- Check disk space: `df -h`
- Run `cub doctor` to diagnose issues

**"Status.json not updating"**
- Verify status writer running: `cub status --verbose`
- Check file permissions: `ls -la .cub/status.json`
- Ensure cub process has write access to .cub/

**"Tasks disappearing"**
- Check tasks.jsonl format: `jq . .cub/tasks.jsonl`
- Restore from git if corrupted: `git checkout .cub/tasks.jsonl`
- Check for concurrent access issues

**"Process doesn't respond to signal"**
- Verify process is running: `ps aux | grep cub`
- Check if process is in uninterruptible state: `ps -l | grep cub`
- Try SIGKILL as last resort (will lose graceful shutdown)

### Getting Help

If a test fails:

1. **Capture diagnostics:**
   ```bash
   cub doctor > /tmp/diag.txt
   cub status --detailed >> /tmp/diag.txt
   cat .cub/status.json >> /tmp/diag.txt
   tail -20 .cub/status/run-*/run.json >> /tmp/diag.txt
   ```

2. **Check logs:**
   ```bash
   # View full cub logs
   cub monitor --logs

   # Or check ledger
   cat .cub/ledger/* | tail -20
   ```

3. **Review code audit:**
   Consult `.cub/docs/run-exit-paths.md` (from cub-r4h.1) to understand expected behavior

---

## Sign-Off

When all tests pass, record results:

```bash
# Create completion record
cat > /tmp/e4-test-results.txt <<'EOF'
E4 Manual Testing - Completion Record
======================================

Date: $(date)
Tester: $(whoami)
Environment: $(uname -s) $(uname -r)

All Scenarios Passed: YES / NO

Critical Failures (if any):
- [List any failures]

Recovery Actions Taken:
- [List actions]

Sign-off: ___________________
EOF

cat /tmp/e4-test-results.txt
```

---

## Appendix: Mock Harness Configuration

For reproducible testing, use the mock harness with various failure modes:

```bash
# Normal behavior
"mock_harness": { "mode": "normal" }

# Simulate token usage
"mock_harness": { "mode": "tokens", "tokens_per_task": 500 }

# Simulate failure
"mock_harness": { "mode": "fail", "fail_after": 3 }

# Simulate slow tasks
"mock_harness": { "mode": "slow", "seconds_per_task": 10 }
```

---

**Document Version:** 1.0
**Last Updated:** 2026-01-26
**Related:** [Audit Results](./e4-audit-results.md) | [Integration Tests](../../tests/integration/test_run_exits.py) | [Run Exit Paths](../../.cub/docs/run-exit-paths.md)

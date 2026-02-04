# E6 Manual Testing Protocol: Direct Session Workflow

**Objective:** Validate that direct harness sessions (Claude Code, Codex, OpenCode) can naturally claim and complete tasks using `cub` commands, with all work captured in the ledger.

**Audience:** QA testers, Marc (project lead), release team

**Testing Duration:** ~45-60 minutes total across all scenarios

**Prerequisites:**
- Complete `cub-r6s.1` (direct session CLI commands) implementation
- Have a test project directory with cub initialized
- Understand basic cub commands: `cub session wip`, `cub session done`, `cub session log`
- Access to Claude Code, Codex, or OpenCode harness (Marc's environment)
- Familiarity with task status transitions (open → in-progress → closed)

---

## Test Environment Setup

### 1.1 Create a Test Project

```bash
# Create a clean test directory
mkdir -p /tmp/cub-e6-test
cd /tmp/cub-e6-test

# Initialize git (required by cub)
git init
git config user.email "test@example.com"
git config user.name "E6 Tester"

# Initialize cub (use local test instance or installed version)
cub init --backend jsonl

# Create some test tasks for direct session work
cub task create "E6 Test: Feature implementation" --type feature --priority 1
cub task create "E6 Test: Bug fix" --type bug --priority 1
cub task create "E6 Test: Test coverage" --type task --priority 2
cub task create "E6 Test: Documentation update" --type task --priority 2
```

### 1.2 Verify Setup

```bash
# Confirm tasks created
cub task list

# Confirm directory structure
ls -la .cub/
# Should show: ledger/, session.log, .cub.json, tasks.jsonl

# Verify task backend is working
cub task list --json | jq '.[0]'
```

**✓ PASS:** All tasks visible, can list tasks in JSON, directory structure correct

---

## Test Scenarios

Each scenario has:
- **Purpose:** What aspect of direct session workflow is being validated
- **Setup:** Preparation steps
- **Workflow:** Steps a user/agent takes in direct harness
- **Expected Behavior:** What should happen
- **Verification Steps:** How to check success
- **Pass/Fail Criteria:** Objective success measures

---

### Scenario 1: Basic Direct Session - Claim and Complete a Task

**Purpose:** Validate the happy path—an agent/user claims a task and completes it with the cub commands.

**Setup:**
```bash
# Ensure tasks exist
cub task list | grep "E6 Test"
# Should show at least 3-4 tasks in "open" status
```

**Workflow (simulate in direct harness session):**

1. **Start session and log initial activity:**
   ```bash
   cub session log "Starting E6 manual test session"
   cub session log "Task: E6 Test: Feature implementation"
   ```

2. **Claim a task:**
   ```bash
   # Find an open task ID (from cub task list)
   TASK_ID="cub-XXXX"  # Replace with actual ID
   cub session wip $TASK_ID
   ```

3. **Do some work (simulate with log entries):**
   ```bash
   cub session log "Analyzed requirements for feature"
   cub session log "Created implementation plan"
   cub session log "Implemented core logic"
   cub session log "Added tests and documentation"
   ```

4. **Complete the task:**
   ```bash
   cub session done $TASK_ID --reason "Implemented feature with tests and docs"
   ```

5. **Log completion:**
   ```bash
   cub session log "Task completed successfully"
   ```

**Expected Behavior:**
- All `cub session` commands succeed with green checkmarks
- Task status transitions: open → in-progress → closed
- Session log file created and appended to
- Ledger entry created for the completed task
- No errors in output

**Verification Steps:**

1. **Check session log file created:**
   ```bash
   cat .cub/session.log
   # Should contain all log entries with timestamps
   ```

2. **Verify task status changed:**
   ```bash
   cub task show $TASK_ID
   # Should show status: "closed"
   ```

3. **Check ledger entry exists:**
   ```bash
   ls -la .cub/ledger/by-task/
   # Should have a file like: $TASK_ID.json
   ```

4. **Verify ledger content:**
   ```bash
   cat .cub/ledger/by-task/$TASK_ID.json | jq '.outcome.success'
   # Should show: true
   ```

5. **Verify completion reason captured:**
   ```bash
   cat .cub/ledger/by-task/$TASK_ID.json | jq '.outcome.approach'
   # Should contain the reason provided
   ```

6. **Check metadata in ledger:**
   ```bash
   cat .cub/ledger/by-task/$TASK_ID.json | jq '.outcome.final_model'
   # Should show: "direct-session"
   ```

**Pass Criteria:**
- [ ] Session log created with all entries and timestamps
- [ ] Task status changed from "open" to "closed"
- [ ] Ledger entry exists in .cub/ledger/by-task/
- [ ] Ledger entry shows `outcome.success: true`
- [ ] Ledger entry shows `outcome.final_model: "direct-session"`
- [ ] Completion reason captured in ledger
- [ ] Ledger file is valid JSON
- [ ] No error messages in output

**Fail Recovery:**
- If task status doesn't change: Check `cub task show` output for error
- If ledger entry missing: Run `cub ledger query $TASK_ID` to debug
- If ledger malformed: Check `.cub/ledger/by-task/$TASK_ID.json` manually

---

### Scenario 2: Claim Task Without Completing (WIP-only)

**Purpose:** Validate that `cub session wip` alone works—task should be marked in-progress but not closed.

**Workflow:**

1. **Claim a task:**
   ```bash
   TASK_ID="cub-XXXX"  # Another task ID
   cub session wip $TASK_ID
   cub session log "Starting investigation of bug..."
   ```

2. **Do NOT call `cub session done`**

3. **Leave session**

**Expected Behavior:**
- Task marked as "in-progress"
- No ledger entry created (work is in progress)
- Session log has entry recording the claim

**Verification Steps:**

1. **Check task status:**
   ```bash
   cub task show $TASK_ID | jq '.status'
   # Should show: "in_progress"
   ```

2. **Verify no ledger entry yet:**
   ```bash
   ls .cub/ledger/by-task/$TASK_ID.json 2>/dev/null
   # Should NOT exist (file not found)
   ```

3. **Check session log:**
   ```bash
   grep $TASK_ID .cub/session.log
   # Should show "Started work on..." entry
   ```

**Pass Criteria:**
- [ ] Task status is "in_progress"
- [ ] No ledger entry exists yet
- [ ] Session log records the work start

**Fail Recovery:**
- If ledger entry created: Check logic in `cub session wip` command

---

### Scenario 3: Update WIP Task Status and Complete

**Purpose:** Validate that a task claimed with `wip` can later be completed, creating a ledger entry.

**Setup:**
- Use the task from Scenario 2 that is in-progress

**Workflow:**

1. **Resume work (in a "later" session):**
   ```bash
   TASK_ID="cub-XXXX"  # Same task from scenario 2
   cub session log "Continuing investigation..."
   cub session log "Found root cause"
   cub session log "Implemented fix"
   ```

2. **Complete the task:**
   ```bash
   cub session done $TASK_ID --reason "Bug fixed: root cause was X, solution implemented"
   ```

**Expected Behavior:**
- Task transitions from in-progress → closed
- Ledger entry created (may update existing entry if one was started)
- Reason reflects the work done

**Verification Steps:**

1. **Check final task status:**
   ```bash
   cub task show $TASK_ID | jq '.status'
   # Should show: "closed"
   ```

2. **Verify ledger entry:**
   ```bash
   cat .cub/ledger/by-task/$TASK_ID.json | jq '.outcome.success, .outcome.approach'
   # Should show: true, "Bug fixed: ..."
   ```

3. **Check completion timestamp:**
   ```bash
   cat .cub/ledger/by-task/$TASK_ID.json | jq '.completed_at'
   # Should have a recent timestamp
   ```

**Pass Criteria:**
- [ ] Task closed successfully
- [ ] Ledger entry created with success=true
- [ ] Reason captured accurately

---

### Scenario 4: Complete Task with Files Changed

**Purpose:** Validate that `--file` flag captures list of changed files.

**Workflow:**

```bash
TASK_ID="cub-XXXX"  # Another open task

# Claim and do work
cub session wip $TASK_ID
cub session log "Creating implementation files"

# Simulate file changes (create dummy files for testing)
touch src/new_feature.py
touch tests/test_new_feature.py

# Complete with file list
cub session done $TASK_ID \
  --reason "Implemented new feature" \
  --file src/new_feature.py \
  --file tests/test_new_feature.py
```

**Expected Behavior:**
- Task marked complete
- Files recorded in ledger entry
- Ledger shows files in `outcome.files_changed`

**Verification Steps:**

1. **Check files captured in ledger:**
   ```bash
   cat .cub/ledger/by-task/$TASK_ID.json | jq '.outcome.files_changed'
   # Should show: ["src/new_feature.py", "tests/test_new_feature.py"]
   ```

2. **Verify format is correct:**
   ```bash
   cat .cub/ledger/by-task/$TASK_ID.json | jq '.outcome.files_changed | length'
   # Should show: 2
   ```

**Pass Criteria:**
- [ ] Ledger entry has `files_changed` array with correct file paths
- [ ] File count is accurate

---

### Scenario 5: Session Log Capture (No Task Completion)

**Purpose:** Validate that `cub session log` creates a running session log independent of task completion.

**Workflow:**

```bash
# Log various session events without claiming tasks
cub session log "Session started at 10:30 AM"
cub session log "Reviewed codebase architecture"
cub session log "Analyzed performance bottleneck in user service"
cub session log "Documented findings in internal wiki"
cub session log "Session ended"
```

**Expected Behavior:**
- Session log file updated with all entries
- Entries have ISO timestamps
- No task status changes
- No ledger entries created

**Verification Steps:**

1. **Check session log content:**
   ```bash
   cat .cub/session.log | tail -10
   # Should show all recent log entries with timestamps
   ```

2. **Verify timestamp format:**
   ```bash
   head -1 .cub/session.log
   # Should show: [YYYY-MM-DD HH:MM:SS UTC] message
   ```

3. **Count log entries:**
   ```bash
   wc -l .cub/session.log
   # Should show multiple lines
   ```

4. **Verify no task changes:**
   ```bash
   cub task list | grep -c in_progress
   # Should be same as before logging
   ```

**Pass Criteria:**
- [ ] Session log appended with all entries
- [ ] Timestamps in ISO format (YYYY-MM-DD HH:MM:SS UTC)
- [ ] No tasks marked in-progress
- [ ] No ledger entries created

---

### Scenario 6: Error Handling - Nonexistent Task

**Purpose:** Validate graceful error handling when trying to operate on a task that doesn't exist.

**Workflow:**

```bash
# Try to claim a nonexistent task
cub session wip nonexistent-task-12345

# Try to complete a nonexistent task
cub session done nonexistent-task-67890 --reason "Test error"
```

**Expected Behavior:**
- Commands fail with clear error message
- Error message identifies the problem (task not found)
- Exit code is non-zero
- Session log not affected
- No corrupted ledger entries created

**Verification Steps:**

1. **Check error message:**
   ```bash
   cub session wip nonexistent-task 2>&1
   # Should show: "Task not found: nonexistent-task"
   ```

2. **Verify exit code:**
   ```bash
   cub session wip nonexistent-task; echo "Exit: $?"
   # Should show: "Exit: 1"
   ```

3. **Check session log unaffected:**
   ```bash
   tail -1 .cub/session.log
   # Should not contain error message
   ```

4. **Verify no bad ledger entries:**
   ```bash
   ls .cub/ledger/by-task/nonexistent* 2>/dev/null
   # Should show nothing (file not found)
   ```

**Pass Criteria:**
- [ ] Error message clearly identifies task not found
- [ ] Exit code is 1
- [ ] Session log not corrupted
- [ ] No partial/invalid ledger entries created

---

### Scenario 7: Already Completed Task Handling

**Purpose:** Validate behavior when trying to complete a task that's already closed.

**Setup:**
- Use a task from Scenario 1 that is already closed

**Workflow:**

```bash
# Try to complete an already-closed task
cub session done $CLOSED_TASK_ID --reason "Try again"
```

**Expected Behavior:**
- Command warns task is already closed
- May update existing ledger entry (with warning)
- Exits with code 0 (not an error, just a warning)
- Session log notes the action

**Verification Steps:**

1. **Check output:**
   ```bash
   cub session done $CLOSED_TASK_ID --reason "Retry" 2>&1
   # Should show: "Task $CLOSED_TASK_ID is already closed"
   ```

2. **Verify task still closed:**
   ```bash
   cub task show $CLOSED_TASK_ID | jq '.status'
   # Should show: "closed"
   ```

3. **Check ledger not duplicated:**
   ```bash
   cat .cub/ledger/by-task/$CLOSED_TASK_ID.json | jq '.outcome.success'
   # Should still show: true (from original completion)
   ```

**Pass Criteria:**
- [ ] Warning message shown
- [ ] Task remains closed
- [ ] No duplicate ledger entries
- [ ] Exit code 0 (not treated as error)

---

### Scenario 8: Multiple Tasks in Single Session

**Purpose:** Validate workflow where multiple tasks are worked on and completed in a single session.

**Workflow:**

```bash
# Log session start
cub session log "Starting multi-task session"

# Task 1
TASK1="cub-XXXX"
cub session log "Working on Task 1"
cub session wip $TASK1
cub session log "Task 1 implementation complete"
cub session done $TASK1 --reason "Feature A implemented"

# Task 2
TASK2="cub-YYYY"
cub session log "Working on Task 2"
cub session wip $TASK2
cub session log "Task 2 implementation complete"
cub session done $TASK2 --reason "Feature B implemented"

# Session end
cub session log "Session complete"
```

**Expected Behavior:**
- Both tasks marked completed
- Ledger entries created for both
- Session log shows activity for both
- No interference between task completions

**Verification Steps:**

1. **Verify both tasks closed:**
   ```bash
   cub task show $TASK1 | jq '.status'
   cub task show $TASK2 | jq '.status'
   # Both should show: "closed"
   ```

2. **Verify both ledger entries:**
   ```bash
   ls .cub/ledger/by-task/ | grep -E "($TASK1|$TASK2)"
   # Should show both files
   ```

3. **Check session log sequence:**
   ```bash
   grep -E "(Task 1|Task 2)" .cub/session.log
   # Should show both tasks logged in order
   ```

4. **Verify independent ledger entries:**
   ```bash
   cat .cub/ledger/by-task/$TASK1.json | jq '.outcome.approach'
   cat .cub/ledger/by-task/$TASK2.json | jq '.outcome.approach'
   # Should show different reasons
   ```

**Pass Criteria:**
- [ ] Both tasks completed independently
- [ ] Both ledger entries exist and are valid JSON
- [ ] Session log captures both workflows
- [ ] No cross-contamination between tasks

---

### Scenario 9: Friction Testing - Natural Workflow

**Purpose:** The ultimate test—does the workflow feel natural to use?

**Execution:**

Perform the entire workflow from Scenario 1, and as you work, note:

1. **Command discoverability:**
   - Can you easily discover `cub session` commands?
   - Is help text (`cub session --help`) clear?
   - Are examples intuitive?

2. **Workflow smoothness:**
   - Do commands provide clear confirmation?
   - Are error messages actionable?
   - Is the mental model (wip → do work → done) intuitive?

3. **Integration with cub:**
   - Does `cub task list` show accurate status?
   - Does ledger data feel complete?
   - Are timestamps correct?

4. **Friction points to document:**
   - What felt awkward?
   - What required clarification?
   - What would make it better?

**Recording Observations:**

```bash
# Document findings
cat > /tmp/e6-friction-notes.txt <<'EOF'
## E6 Friction Testing Notes

### What Worked Well:
- [List aspects that felt natural]

### Friction Points:
- [List any awkward parts]

### Suggested Improvements:
- [Improvements for UX]

### Questions Raised:
- [Open questions or uncertainties]
EOF

cat /tmp/e6-friction-notes.txt
```

**Pass Criteria:**
- [ ] Workflow is intuitive (no major confusion)
- [ ] Commands provide clear feedback
- [ ] Error messages are helpful
- [ ] Friction points documented for improvement

---

## Summary Checklist

Use this table to track all test results:

| Scenario | Pass/Fail | Notes | Run Date |
|----------|-----------|-------|----------|
| 1. Basic claim + complete | [ ] | | |
| 2. Claim without complete (WIP) | [ ] | | |
| 3. WIP then complete | [ ] | | |
| 4. Complete with files changed | [ ] | | |
| 5. Session log capture | [ ] | | |
| 6. Error handling (nonexistent) | [ ] | | |
| 7. Already completed task | [ ] | | |
| 8. Multiple tasks in session | [ ] | | |
| 9. Friction testing (natural use) | [ ] | | |

**Overall Result:**
- [ ] All scenarios 1-8 passed
- [ ] Friction testing documented
- [ ] Ledger integrity verified
- [ ] Session log captures work naturally

---

## Expected Ledger Structure

After successful tests, the ledger should have entries like:

```bash
.cub/ledger/
├── by-task/
│   ├── cub-XXXX.json      # Task 1 ledger entry
│   ├── cub-YYYY.json      # Task 2 ledger entry
│   └── ...
├── session.log             # Session activity log
└── by-run/                 # (Empty for direct sessions)
```

Each `by-task/*.json` file should contain:
- Task metadata (title, description, type)
- Outcome (success: true, approach/reason)
- Attempt info (harness: "direct-session", model: "direct-session")
- Files changed (if provided)
- Completion timestamp

---

## Troubleshooting Guide

### Common Issues

**"Task not found"**
- Verify task ID with: `cub task list`
- Ensure task exists in backend: `cub task show <id>`

**"Ledger entry not created"**
- Check if ledger is enabled: `cat .cub/.cub.json | jq '.ledger.enabled'`
- Verify ledger directory exists: `ls -la .cub/ledger/`
- Check disk permissions: `ls -la .cub/`

**"Session log not appending"**
- Check file permissions: `ls -la .cub/session.log`
- Ensure .cub directory is writable: `touch .cub/test.txt`
- Check disk space: `df -h`

**"Task status not updating"**
- Verify task backend: `cat .cub/.cub.json | jq '.tasks'`
- Check task manually: `cub task show <task-id> --json`
- Ensure write permission to .cub/

**"Ledger JSON malformed"**
- Check file format: `cat .cub/ledger/by-task/<task-id>.json | jq '.'`
- Look for incomplete writes (file size): `ls -la .cub/ledger/by-task/`
- Check for concurrent access issues (multiple harnesses writing)

### Getting Help

If a test fails:

1. **Capture state:**
   ```bash
   # Create diagnostics bundle
   mkdir -p /tmp/e6-diagnostics
   cub task list > /tmp/e6-diagnostics/tasks.txt
   cub status --detailed > /tmp/e6-diagnostics/status.txt
   cat .cub/session.log > /tmp/e6-diagnostics/session.log
   find .cub/ledger -type f -name "*.json" -exec ls -la {} \; > /tmp/e6-diagnostics/ledger-files.txt
   tar -czf /tmp/e6-diag.tar.gz /tmp/e6-diagnostics/
   ```

2. **Check logs:**
   ```bash
   # View detailed command output
   cub session log "Debug test" --debug
   ```

3. **Review implementation:**
   - Check `src/cub/cli/session.py` for command logic
   - Check `src/cub/core/ledger/integration.py` for ledger creation
   - Review `.cub/agent.md` for instructions provided to agents

---

## Sign-Off

When all tests pass, record results:

```bash
cat > /tmp/e6-test-results.txt <<'EOF'
E6 Manual Testing - Completion Record
======================================

Date: $(date)
Tester: $(whoami)
Environment: $(uname -s) $(uname -r)

All Scenarios Passed: YES / NO

Critical Failures (if any):
- [List any failures]

Friction Issues Documented:
- [List friction points]

Improvements for Next Iteration:
- [List suggested improvements]

Sign-off: ___________________
EOF

cat /tmp/e6-test-results.txt
```

---

## Related Documentation

- [E4 Manual Tests](./e4-manual-tests.md) - Core loop exit path testing
- [Architecture](./architecture.md) - System design and components
- [Orientation](./orientation.md) - Problem statement and vision
- [CLI Session Commands](../../src/cub/cli/session.py) - Implementation

---

**Document Version:** 1.0
**Last Updated:** 2026-01-26
**Task:** cub-r6s.6 - Manual testing: direct session workflow

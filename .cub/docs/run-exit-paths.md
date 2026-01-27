# Run.py Exit Path Audit

**Date:** 2024-01-26
**File:** `src/cub/cli/run.py`
**Purpose:** Document all exit paths in the main run command and their artifact-preservation status.

## Executive Summary

This audit identifies **31 distinct exit paths** in `run.py`, categorized into:
- **Early validation exits** (13 paths) - Flag validation, setup failures
- **Direct/GH-issue mode exits** (4 paths) - Alternative execution modes
- **Main loop exits** (8 paths) - Normal and error termination
- **Sandbox mode exits** (3 paths) - Docker sandbox-specific
- **Parallel mode exits** (3 paths) - Parallel execution-specific

### Critical Findings

**✅ GOOD:** The main `run()` function has comprehensive artifact preservation via `finally` block (lines 1893-2012).

**⚠️ GAPS IDENTIFIED:**
1. **Direct mode (`_run_direct`)** - No run artifact creation
2. **GH-issue mode (`_run_gh_issue`)** - No run artifact creation
3. **Sandbox mode (`_run_in_sandbox`)** - No run artifact creation
4. **Parallel mode (`_run_parallel`)** - No run artifact creation
5. **Early validation exits** - No artifacts created (by design, but could track failed attempts)

---

## Exit Path Categories

### 1. Early Validation Exits (13 paths)

These occur before harness execution begins. **Status persistence:** ❌ None

| Line | Trigger | Exit Code | Artifact Created? | Status Persisted? |
|------|---------|-----------|-------------------|-------------------|
| 830 | `--no-network` without `--sandbox` | USER_ERROR | ❌ No | ❌ No |
| 837 | `--sandbox-keep` without `--sandbox` | USER_ERROR | ❌ No | ❌ No |
| 846 | `--direct` + `--task` conflict | USER_ERROR | ❌ No | ❌ No |
| 852 | `--direct` + `--epic` conflict | USER_ERROR | ❌ No | ❌ No |
| 858 | `--direct` + `--label` conflict | USER_ERROR | ❌ No | ❌ No |
| 864 | `--direct` + `--ready` conflict | USER_ERROR | ❌ No | ❌ No |
| 870 | `--direct` + `--parallel` conflict | USER_ERROR | ❌ No | ❌ No |
| 879 | `--gh-issue` + `--task` conflict | USER_ERROR | ❌ No | ❌ No |
| 885 | `--gh-issue` + `--epic` conflict | USER_ERROR | ❌ No | ❌ No |
| 891 | `--gh-issue` + `--label` conflict | USER_ERROR | ❌ No | ❌ No |
| 897 | `--gh-issue` + `--ready` conflict | USER_ERROR | ❌ No | ❌ No |
| 903 | `--gh-issue` + `--parallel` conflict | USER_ERROR | ❌ No | ❌ No |
| 909 | `--gh-issue` + `--direct` conflict | USER_ERROR | ❌ No | ❌ No |
| 927 | Running on main/master without `--main-ok` | USER_ERROR | ❌ No | ❌ No |
| 978 | Failed to create branch | 1 | ❌ No | ❌ No |
| 1004 | Docker not available | USER_ERROR | ❌ No | ❌ No |
| 1085 | Worktree creation failed | 1 | ❌ No | ❌ No |
| 1187 | Task backend initialization failed | 1 | ❌ No | ❌ No |
| 1217 | Harness setup failed | 1 | ❌ No | ❌ No |

**Analysis:** These are user errors or environment issues. No artifacts expected (nothing ran). However, could be useful to track failed run attempts for debugging.

---

### 2. Direct Mode Exits (2 paths)

Function: `_run_direct()` (lines 2015-2135)

| Line | Trigger | Exit Code | Artifact Created? | Status Persisted? |
|------|---------|-----------|-------------------|-------------------|
| 2050 | Invalid config type | 1 | ❌ No | ❌ No |
| 2056 | Failed to read direct input | 1 | ❌ No | ❌ No |
| 2060 | Empty task content | 1 | ❌ No | ❌ No |
| 2068 | Harness setup failed | 1 | ❌ No | ❌ No |
| 2122 | Harness invocation exception | 1 | ⚠️ Partial (prompt.md only) | ❌ No |
| 2131 | Success | 0 | ⚠️ Partial (prompt.md, harness.log) | ❌ No |
| 2134 | Task failed | exit_code or 1 | ⚠️ Partial (prompt.md, harness.log) | ❌ No |

**Gap:** Direct mode creates `prompt.md` and `harness.log` but **NO run.json artifact**. Budget tracking, timing, and final status are lost.

---

### 3. GH-Issue Mode Exits (2 paths)

Function: `_run_gh_issue()` (lines 2137-2278)

| Line | Trigger | Exit Code | Artifact Created? | Status Persisted? |
|------|---------|-----------|-------------------|-------------------|
| 2173 | Invalid config type | 1 | ❌ No | ❌ No |
| 2180 | GitHub client error | 1 | ❌ No | ❌ No |
| 2189 | Harness setup failed | 1 | ❌ No | ❌ No |
| 2252 | Harness invocation exception | 1 | ⚠️ Partial (prompt.md only) | ❌ No |
| 2274 | Success | 0 | ⚠️ Partial (prompt.md, harness.log) | ❌ No |
| 2277 | Task failed | exit_code or 1 | ⚠️ Partial (prompt.md, harness.log) | ❌ No |

**Gap:** Like direct mode, GH-issue mode **lacks run.json artifact** for budget/timing tracking.

---

### 4. Main Loop Exits (8 paths)

Function: `run()` main loop (lines 1326-1892)

| Line | Trigger | Exit Code | Artifact Created? | Status Persisted? |
|------|---------|-----------|-------------------|-------------------|
| 1195 | `--ready` flag (list tasks only) | 0 | ❌ No | ❌ No |
| 1212 | `--parallel` flag (delegates to parallel) | 0 | Handled by `_run_parallel` | See Parallel section |
| 1321 | Pre-loop hook failed + fail_fast | 1 | ❌ No (no finally yet) | ⚠️ status.json only |
| 1332 | Interrupt signal (Ctrl+C) | 0 or 1 | ✅ Yes (via finally) | ✅ Yes |
| 1339 | Budget exhausted | 0 | ✅ Yes (via finally) | ✅ Yes |
| 1357 | Specific task not found | 1 | ✅ Yes (via finally) | ✅ Yes |
| 1361 | Specific task already closed | 0 | ✅ Yes (via finally) | ✅ Yes |
| 1380 | All tasks complete | 0 | ✅ Yes (via finally) | ✅ Yes |
| 1393 | No ready tasks (blocked) | 0 | ✅ Yes (via finally) | ✅ Yes |
| 1422 | Pre-task hook failed + fail_fast | 1 | ✅ Yes (via finally) | ✅ Yes |
| 1590 | Harness invocation failed + stop policy | 1 | ✅ Yes (via finally) | ✅ Yes |
| 1838 | Task failed + stop policy | 1 | ✅ Yes (via finally) | ✅ Yes |
| 1876 | Specific task completed (--task mode) | 0 or 1 | ✅ Yes (via finally) | ✅ Yes |
| 1886 | Max iterations reached | 0 | ✅ Yes (via finally) | ✅ Yes |
| 1891 | Unexpected exception | raises | ✅ Yes (via finally) | ✅ Yes |
| 2011-2012 | Final exit after finally block | 0 or 1 | ✅ Yes | ✅ Yes |

**Analysis:** Main loop is **well-covered** by the `finally` block (lines 1893-2012):
- Lines 1930-1935: `status_writer.write_run_artifact()` called
- Lines 1945-1989: Cleanup service runs
- Lines 1992-2007: Worktree cleanup
- Line 2010-2012: Exit with proper code

**Exception:** Line 1321 (pre-loop hook failure) exits **before** entering try block, so `finally` never runs. Status.json may be written but no run artifact.

---

### 5. Signal Handler Exit (1 path)

Function: `_signal_handler()` (lines 364-373)

| Line | Trigger | Exit Code | Artifact Created? | Status Persisted? |
|------|---------|-----------|-------------------|-------------------|
| 370 | Second SIGINT (force exit) | 130 | ❌ No (bypasses finally) | ❌ No |

**Gap:** Force-exit via second Ctrl+C calls `sys.exit(130)` immediately, **bypassing finally block**. No artifact created.

---

### 6. Sandbox Mode Exits (3 paths)

Function: `_run_in_sandbox()` (lines 2472-2664)

| Line | Trigger | Exit Code | Artifact Created? | Status Persisted? |
|------|---------|-----------|-------------------|-------------------|
| 2548 | Failed to get Docker provider | 1 | ❌ No | ❌ No |
| 2629 | Normal completion or failure | 0 or exit_code | ❌ No | ❌ No |
| 2640 | KeyboardInterrupt | 130 | ❌ No | ❌ No |
| 2648 | Exception during sandbox setup/run | 1 | ❌ No | ❌ No |

**Gap:** Sandbox mode **never creates run artifacts**. The sandbox executes `cub run` internally, which creates artifacts *inside* the container, but they're not exposed to the host unless explicitly configured.

---

### 7. Parallel Mode Exits (3 paths)

Function: `_run_parallel()` (lines 2330-2424)

| Line | Trigger | Exit Code | Artifact Created? | Status Persisted? |
|------|---------|-----------|-------------------|-------------------|
| 2362 | Invalid task backend | 1 | ❌ No | ❌ No |
| 2389 | No ready tasks | 0 | ❌ No | ❌ No |
| 2422 | Some tasks failed | 1 | ❌ No (per-worker logs only) | ❌ No |
| 2424 | All tasks succeeded | 0 | ❌ No (per-worker logs only) | ❌ No |

**Gap:** Parallel mode displays summary but **does not create a unified run artifact** tracking all parallel workers. Individual workers may create their own artifacts in their worktrees.

---

## Artifact Creation Analysis

### What Gets Created (Main Loop)

When the main loop runs successfully, the `finally` block creates:

1. **status.json** (line 1930)
   - Via `status_writer.write(status)`
   - Contains current run state

2. **run.json** (line 1935)
   - Via `status_writer.write_run_artifact(run_artifact)`
   - Contains budget totals, timing, completion status
   - **This is the key forensic artifact**

3. **prompt.md** (per task, line 1481)
   - Via `status_writer.write_prompt()`
   - Captures system + task prompt

4. **harness.log** (per task, lines 1516-1519)
   - Captured during harness invocation
   - Full output of harness execution

5. **task.json** (per task, lines 1655, 1780)
   - Via `status_writer.write_task_artifact()`
   - Per-task timing, tokens, exit code

6. **Cleanup commit** (optional, lines 1945-1989)
   - Via `CleanupService.cleanup()`
   - Commits artifacts if configured

### What Gets Missed

| Mode | Missing Artifacts | Impact |
|------|-------------------|--------|
| Direct mode | run.json, task.json | No budget/timing tracking |
| GH-issue mode | run.json, task.json | No budget/timing tracking |
| Sandbox mode | Host-side run.json | Forensics lost if container deleted |
| Parallel mode | Unified run.json | No aggregate view of parallel run |
| Pre-loop hook failure | run.json | Failed runs not tracked |
| Force SIGINT | run.json | Interrupt leaves no trace |

---

## Status Persistence Analysis

### Status Writer Usage

The `StatusWriter` class is responsible for creating artifacts:

- **Initialized at line 1247** (main loop)
- **Initialized at line 2086** (direct mode)
- **Initialized at line 2224** (gh-issue mode)
- **NOT initialized** in sandbox or parallel modes

### Key Methods

1. `status_writer.write(status)` - Writes status.json (current state)
2. `status_writer.write_run_artifact(artifact)` - Writes run.json (final summary)
3. `status_writer.write_prompt(task_id, sys_prompt, task_prompt)` - Writes prompt.md
4. `status_writer.write_task_artifact(task_id, artifact)` - Writes task.json
5. `status_writer.get_harness_log_path(task_id)` - Gets path for harness.log

### Coverage Gaps

- **Direct mode:** Uses StatusWriter but only calls `write_prompt()` and logs harness output. Never calls `write_run_artifact()`.
- **GH-issue mode:** Same as direct mode.
- **Sandbox mode:** No StatusWriter at all.
- **Parallel mode:** No unified StatusWriter (workers have their own).

---

## Recommendations

### Priority 1: Add run artifacts to alternate modes

**Direct mode (_run_direct):**
```python
# After line 2123, before return statements:
run_status = RunStatus(
    run_id=direct_session_id,
    phase=RunPhase.COMPLETED if result.success else RunPhase.FAILED,
    # ... populate fields
)
run_artifact = create_run_artifact(run_status, config_dict)
status_writer.write_run_artifact(run_artifact)
```

**GH-issue mode (_run_gh_issue):** Similar approach.

**Sandbox mode:** Expose run.json from container or create host-side summary artifact.

**Parallel mode:** Create unified run.json summarizing all workers.

### Priority 2: Fix pre-loop hook failure path

Move pre-loop hook check **inside** the try block (after line 1326) so finally block always runs.

### Priority 3: Handle force SIGINT gracefully

Consider using `atexit` or signal handler that ensures `write_run_artifact()` is called before sys.exit().

### Priority 4: Track early validation failures (optional)

Create lightweight "run attempt" log for failed validation to help users debug setup issues.

---

## Testing Implications

When writing tests for E4 (clean exits), ensure coverage for:

1. ✅ Main loop exits (already covered by finally)
2. ❌ Direct mode exits (needs artifact creation)
3. ❌ GH-issue mode exits (needs artifact creation)
4. ❌ Sandbox mode exits (needs artifact creation)
5. ❌ Parallel mode exits (needs artifact creation)
6. ⚠️ Force SIGINT (currently bypasses finally)
7. ⚠️ Pre-loop hook failure (currently before try block)

---

## Summary Table: Exit Path Coverage

| Category | Total Paths | Artifacts Created | Status Persisted | Notes |
|----------|-------------|-------------------|------------------|-------|
| Early validation | 19 | 0 | 0 | By design (no work done) |
| Direct mode | 7 | 7 (partial) | 0 | Missing run.json |
| GH-issue mode | 6 | 6 (partial) | 0 | Missing run.json |
| Main loop | 16 | 15 | 15 | ⚠️ Pre-loop hook failure misses finally |
| Sandbox mode | 4 | 0 | 0 | Container has artifacts, host doesn't |
| Parallel mode | 4 | 0 | 0 | Workers create own artifacts |
| Signal handler | 1 | 0 | 0 | Force SIGINT bypasses cleanup |
| **TOTAL** | **57** | **28** | **15** | **26% fully covered** |

---

## Conclusion

The main `run()` function has **excellent** artifact preservation via its `finally` block, covering most normal and error cases. However, **alternate execution modes** (direct, gh-issue, sandbox, parallel) lack run artifact creation, leaving gaps in forensic tracking.

**Next Steps:**
1. Implement run artifact creation in alternate modes
2. Fix pre-loop hook failure path
3. Improve force SIGINT handling
4. Write tests validating artifact creation on all exit paths

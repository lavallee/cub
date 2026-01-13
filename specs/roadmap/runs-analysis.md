# Runs Analysis & Intelligence

**Source:** Original feature for cub
**Dependencies:** None (uses existing run artifacts)
**Complexity:** Medium-High

## Overview

Analyze completed cub runs to extract actionable insights about:
1. **Instruction clarity** - Where prompts/task descriptions cause confusion
2. **Task quality** - Where task structure or content could be improved
3. **Hook opportunities** - Where hooks could automate recurring patterns
4. **Delegation gaps** - Where agents improvise instead of using cub commands
5. **Spec-implementation skew** - Where actual code diverges from task specs

This turns run history into a feedback loop for continuous improvement.

## Problem Statement

Agents leave traces of their work:
- Harness output logs
- Git commits and diffs
- Artifact summaries
- progress.txt updates (inconsistent formats)
- Failed attempts and retries

These traces contain valuable signals about:
- What instructions are unclear
- What patterns repeat unnecessarily
- What could be automated
- What tasks were under/over-specified
- Whether implementations match intentions

Currently this intelligence is lost. Runs Analysis extracts and surfaces it.

---

## Analysis Dimensions

### 1. Instruction Clarity Analysis

**Goal:** Identify where PROMPT.md, AGENT.md, or task descriptions cause agent confusion.

**Signals of unclear instructions:**
- Agent asks clarifying questions
- Agent makes assumptions explicitly ("I'll assume...")
- Agent backtracks ("Actually, let me reconsider...")
- Multiple iterations on same task without progress
- Agent misinterprets requirements (detected via review)

**Detection:**

```bash
analyze_instruction_clarity() {
  # Parse harness output for confusion signals
  local confusion_patterns=(
    "I'll assume"
    "I'm not sure if"
    "Could you clarify"
    "Let me reconsider"
    "On second thought"
    "I think you mean"
    "Assuming that"
    "If I understand correctly"
  )

  # Find instances in run logs
  for pattern in "${confusion_patterns[@]}"; do
    grep -r "$pattern" .cub/runs/*/tasks/*/harness_output.log
  done

  # Correlate with task descriptions
  # Identify which instructions triggered confusion
}
```

**Output:**

```json
{
  "instruction_issues": [
    {
      "source": "PROMPT.md",
      "section": "Testing Requirements",
      "issue": "Agent confused about test coverage expectations",
      "evidence": ["run-123/task-abc: 'I'll assume 80% coverage is sufficient'"],
      "suggestion": "Add explicit coverage threshold: 'Maintain >80% test coverage'"
    },
    {
      "source": "task beads-xyz",
      "field": "acceptance_criteria",
      "issue": "Criteria ambiguous - agent interpreted differently than intended",
      "evidence": ["Implementation doesn't match 'user can see history'"],
      "suggestion": "Specify: 'User can see last 10 history entries in sidebar'"
    }
  ]
}
```

---

### 2. Task Quality Analysis

**Goal:** Identify patterns in task structure that correlate with success/failure.

**Metrics:**
- Tasks completed in 1 iteration vs multiple
- Tasks that required human intervention
- Tasks with scope creep (touched unexpected files)
- Tasks with incomplete acceptance criteria coverage

**Analysis:**

```bash
analyze_task_quality() {
  # For each completed task
  for task_dir in .cub/runs/*/tasks/*/; do
    local task_id=$(basename "$task_dir")
    local iterations=$(ls "$task_dir"/iteration_*.log 2>/dev/null | wc -l)
    local files_touched=$(git log --oneline --name-only | grep "$task_id" | wc -l)

    # Compare to task spec
    local expected_files=$(jq -r '.files_involved[]' "$task_dir/task.json")
    local unexpected_files=$(comm -23 <(sort actual_files) <(sort expected_files))

    # Score task quality
    calculate_task_quality_score "$iterations" "$unexpected_files" "$task_dir"
  done
}
```

**Task Quality Indicators:**

| Indicator | Good Sign | Bad Sign |
|-----------|-----------|----------|
| Iterations | 1-2 | >3 |
| Files touched | Match spec | Many unexpected |
| Acceptance criteria | All checked | Some skipped |
| Description length | 100-500 words | <50 or >1000 |
| Dependencies | Correctly ordered | Circular or missing |

**Output:**

```json
{
  "task_quality_patterns": {
    "successful_patterns": [
      "Tasks with 3-5 specific acceptance criteria complete faster",
      "Tasks with 'Files Involved' section have less scope creep",
      "Tasks with implementation hints reduce iterations by 40%"
    ],
    "problematic_patterns": [
      "Tasks with vague descriptions ('improve X') average 4.2 iterations",
      "Tasks without acceptance criteria have 60% higher rework rate",
      "Epic-level tasks without subtask breakdown often stall"
    ],
    "recommendations": [
      {"task_type": "feature", "suggestion": "Always include 'Files Likely Involved'"},
      {"task_type": "bug", "suggestion": "Include reproduction steps in description"}
    ]
  }
}
```

---

### 3. Hook Opportunity Analysis

**Goal:** Identify recurring manual actions that could be automated via hooks.

**Patterns to detect:**

```bash
analyze_hook_opportunities() {
  # Pattern: Agent manually runs tests after changes
  if grep -r "npm test\|pytest\|go test\|bats" harness_output.log; then
    suggest_hook "post-task" "auto_run_tests.sh"
  fi

  # Pattern: Agent manually formats code
  if grep -r "prettier\|black\|gofmt" harness_output.log; then
    suggest_hook "post-task" "auto_format.sh"
  fi

  # Pattern: Agent manually updates changelog
  if grep -r "CHANGELOG\|changelog" harness_output.log; then
    suggest_hook "post-task" "auto_changelog.sh"
  fi

  # Pattern: Agent manually commits with specific format
  if detect_commit_pattern_variation; then
    suggest_hook "post-task" "standardize_commits.sh"
  fi
}
```

**Common Hook Opportunities:**

| Pattern Detected | Suggested Hook | Trigger |
|------------------|----------------|---------|
| Manual test runs | `auto_test.sh` | post-task |
| Code formatting | `auto_format.sh` | post-task |
| Changelog updates | `auto_changelog.sh` | post-task (if type=feature) |
| Version bumps | `auto_version.sh` | pre-close (if milestone) |
| Notification | `notify_slack.sh` | post-task, on-error |
| Backup/snapshot | `auto_snapshot.sh` | pre-task |

**Output:**

```json
{
  "hook_recommendations": [
    {
      "pattern": "Agent ran 'npm test' in 87% of tasks",
      "current_state": "Manual execution in harness",
      "recommendation": "Enable post-task hook: auto_run_tests.sh",
      "benefit": "Consistent test runs, cleaner harness output",
      "sample_hook": "#!/bin/bash\nnpm test || exit 1"
    },
    {
      "pattern": "Agent manually formatted code in 45% of tasks",
      "current_state": "Inconsistent formatting application",
      "recommendation": "Enable post-task hook: auto_format.sh",
      "benefit": "Consistent code style, reduced iteration"
    }
  ],
  "hooks_to_disable": [
    {
      "hook": "verbose_logging.sh",
      "reason": "Adding 2+ minutes per task, output rarely reviewed",
      "recommendation": "Disable or make conditional"
    }
  ]
}
```

---

### 4. Delegation Gap Analysis

**Goal:** Identify where agents improvise solutions that cub should provide as commands.

**The Problem:**

Agents often:
- Update progress.txt in inconsistent formats
- Create their own tracking files (@progress.txt, NOTES.md, etc.)
- Manually manage state that cub could track
- Reinvent patterns that hooks/commands could handle

**Detection:**

```bash
analyze_delegation_gaps() {
  # Pattern: Inconsistent progress tracking
  local progress_patterns=$(grep -r "progress\|Progress\|PROGRESS" harness_output.log | \
    extract_file_references | sort | uniq -c | sort -rn)

  if [[ $(echo "$progress_patterns" | wc -l) -gt 2 ]]; then
    suggest_command "cub progress" "Standardized progress tracking"
  fi

  # Pattern: Agent creating tracking files
  local tracking_files=$(git diff --name-only | grep -E "(TODO|NOTES|progress|tracking)")
  if [[ -n "$tracking_files" ]]; then
    suggest_command "cub notes" "Structured note-taking"
  fi

  # Pattern: Agent manually checking task status
  if grep -r "bd list\|bd show\|bd ready" harness_output.log; then
    # Agent is calling beads directly - could use cub wrapper
    suggest_delegation "Use 'cub tasks' instead of 'bd' for consistent interface"
  fi

  # Pattern: Agent manually managing git
  if grep -r "git add\|git commit\|git push" harness_output.log; then
    suggest_command "cub commit" "Standardized commit with task context"
  fi
}
```

**Common Delegation Gaps:**

| Agent Behavior | Problem | Suggested Command |
|----------------|---------|-------------------|
| Updates progress.txt inconsistently | Format drift, lost context | `cub progress add "message"` |
| Creates @progress.txt, NOTES.md | Multiple tracking files | `cub notes add "message"` |
| Manually runs bd commands | Bypasses cub orchestration | `cub tasks list/show/update` |
| Manual git commits | Inconsistent format | `cub commit "message"` |
| Checks own work | No standard process | `cub verify` |
| Asks about project context | Repeats exploration | `cub context` (cached) |

**Output:**

```json
{
  "delegation_gaps": [
    {
      "pattern": "progress_tracking",
      "observed_behaviors": [
        "Updated progress.txt in 34% of tasks",
        "Created @progress.txt in 12% of tasks",
        "Created NOTES.md in 8% of tasks",
        "Inconsistent formats across all"
      ],
      "impact": "Lost context, hard to review, format drift",
      "suggested_command": {
        "name": "cub progress",
        "interface": "cub progress add 'Completed auth flow implementation'",
        "implementation_notes": "Append to .cub/progress.jsonl with timestamp, task_id, model"
      }
    },
    {
      "pattern": "direct_beads_access",
      "observed_behaviors": [
        "Agent called 'bd show' 47 times across runs",
        "Agent called 'bd list' 23 times",
        "Inconsistent flag usage"
      ],
      "impact": "Bypasses cub logging, inconsistent interface",
      "suggested_command": {
        "name": "cub tasks",
        "interface": "cub tasks show <id>, cub tasks list --ready",
        "implementation_notes": "Wrapper with logging, consistent output format"
      }
    }
  ],
  "new_commands_proposed": [
    {
      "command": "cub progress",
      "subcommands": ["add", "show", "clear"],
      "rationale": "78% of runs had some form of progress tracking attempt"
    },
    {
      "command": "cub context",
      "subcommands": ["show", "refresh"],
      "rationale": "Agent repeatedly explored same files for context"
    }
  ]
}
```

---

### 5. Spec-Implementation Skew Analysis

**Goal:** Detect drift between task specifications and actual implementations.

**What to check:**

```bash
analyze_spec_implementation_skew() {
  for task_id in $(get_closed_tasks); do
    local spec=$(get_task_spec "$task_id")
    local implementation=$(get_task_implementation "$task_id")  # Git diff

    # Check acceptance criteria coverage
    local criteria=$(echo "$spec" | jq -r '.acceptanceCriteria[]')
    for criterion in $criteria; do
      if ! implementation_satisfies_criterion "$implementation" "$criterion"; then
        report_skew "$task_id" "acceptance_criteria" "$criterion"
      fi
    done

    # Check file scope
    local expected_files=$(echo "$spec" | jq -r '.files_involved[]')
    local actual_files=$(echo "$implementation" | get_changed_files)
    local unexpected=$(comm -23 <(echo "$actual_files" | sort) <(echo "$expected_files" | sort))
    if [[ -n "$unexpected" ]]; then
      report_skew "$task_id" "scope_creep" "$unexpected"
    fi

    # Check for incomplete implementation
    local todos_introduced=$(echo "$implementation" | grep -c "TODO\|FIXME\|HACK")
    if [[ $todos_introduced -gt 0 ]]; then
      report_skew "$task_id" "incomplete" "$todos_introduced TODOs introduced"
    fi
  done
}
```

**AI-Assisted Skew Detection:**

```bash
ai_analyze_skew() {
  local task_spec=$1
  local implementation_diff=$2

  local prompt="Compare this task specification to its implementation.

TASK SPEC:
$task_spec

IMPLEMENTATION (git diff):
$implementation_diff

Identify:
1. Acceptance criteria that appear unmet
2. Functionality that was added but not specified
3. Scope creep (files changed that weren't mentioned)
4. Quality concerns (TODOs, incomplete error handling)
5. Whether this task should be considered truly complete

Output JSON with: {skew_detected: bool, issues: [...], recommendation: string}"

  invoke_harness --prompt "$prompt" --model haiku
}
```

**Output:**

```json
{
  "spec_implementation_skew": [
    {
      "task_id": "beads-abc123",
      "task_title": "Implement user authentication",
      "skew_type": "incomplete_criteria",
      "details": {
        "criterion": "Session persists across page refresh",
        "implementation_status": "Not found in diff",
        "evidence": "No localStorage or sessionStorage code added"
      },
      "recommendation": "Revivify task or create follow-up: 'Add session persistence'"
    },
    {
      "task_id": "beads-def456",
      "task_title": "Refactor config loading",
      "skew_type": "scope_creep",
      "details": {
        "expected_files": ["lib/config.sh"],
        "actual_files": ["lib/config.sh", "lib/logging.sh", "lib/harness.sh"],
        "unexpected": ["lib/logging.sh", "lib/harness.sh"]
      },
      "recommendation": "Review if changes to logging/harness were necessary; consider splitting task"
    },
    {
      "task_id": "beads-ghi789",
      "task_title": "Add error handling to API",
      "skew_type": "incomplete_implementation",
      "details": {
        "todos_introduced": 3,
        "locations": ["src/api.js:45", "src/api.js:67", "src/api.js:89"]
      },
      "recommendation": "Create follow-up task to address TODOs"
    }
  ],
  "tasks_to_revivify": [
    {
      "original_task": "beads-abc123",
      "reason": "Session persistence not implemented",
      "suggested_new_task": {
        "title": "Add session persistence to authentication",
        "description": "...",
        "depends_on": []
      }
    }
  ],
  "new_tasks_suggested": [
    {
      "reason": "Scope creep in beads-def456 touched logging",
      "suggested_task": {
        "title": "Review and document logging changes from config refactor",
        "type": "chore"
      }
    }
  ]
}
```

---

## CLI Interface

```bash
# Run full analysis on recent runs
cub analyze

# Analyze specific run
cub analyze --run <session-id>

# Analyze specific dimension
cub analyze --instructions    # Instruction clarity
cub analyze --tasks           # Task quality
cub analyze --hooks           # Hook opportunities
cub analyze --delegation      # Delegation gaps
cub analyze --skew            # Spec-implementation skew

# Output formats
cub analyze --format summary  # Human-readable (default)
cub analyze --format json     # Machine-readable
cub analyze --format report   # Full markdown report

# Generate improvements
cub analyze --generate-tasks  # Create tasks for identified issues
cub analyze --update-prompts  # Suggest PROMPT.md updates
cub analyze --suggest-hooks   # Generate hook scripts

# Scope
cub analyze --last 10         # Last 10 runs
cub analyze --since 2026-01-01
cub analyze --task <task-id>  # Specific task across runs
```

---

## Output: Unified Report

```
CUB RUNS ANALYSIS
═══════════════════════════════════════════════════════════════════

Analyzed: 15 runs, 47 tasks, 2026-01-01 to 2026-01-15

INSTRUCTION CLARITY                                    Score: B-
───────────────────────────────────────────────────────────────────
  ⚠ 12 instances of agent confusion detected
  ⚠ PROMPT.md "Testing" section caused 4 clarification attempts
  ⚠ 3 tasks had ambiguous acceptance criteria

  Top Issues:
  1. "Test coverage requirements unclear" (4 occurrences)
  2. "File location conventions not specified" (3 occurrences)

TASK QUALITY                                           Score: B
───────────────────────────────────────────────────────────────────
  ✓ 78% of tasks completed in ≤2 iterations
  ⚠ 15% of tasks had scope creep
  ⚠ 8% of tasks missing acceptance criteria

  Patterns:
  • Tasks with "Files Involved" had 40% less scope creep
  • Tasks >500 words took 2x longer to complete

HOOK OPPORTUNITIES                                     Score: C+
───────────────────────────────────────────────────────────────────
  ✗ Agent manually ran tests in 87% of tasks
  ✗ Agent manually formatted code in 45% of tasks
  ⚠ Verbose logging hook adding 2min/task with low utility

  Recommendations:
  1. [HIGH] Add post-task hook: auto_run_tests.sh
  2. [MEDIUM] Add post-task hook: auto_format.sh
  3. [LOW] Disable/optimize verbose_logging.sh

DELEGATION GAPS                                        Score: C
───────────────────────────────────────────────────────────────────
  ✗ Progress tracking inconsistent (3 different files used)
  ✗ Agent called 'bd' directly 70 times (bypassing cub)
  ⚠ Agent manually managed git commits

  Proposed Commands:
  1. cub progress add/show - Standardized progress tracking
  2. cub tasks - Wrapper for beads with logging
  3. cub commit - Standardized commits with task context

SPEC-IMPLEMENTATION SKEW                               Score: B-
───────────────────────────────────────────────────────────────────
  ⚠ 4 tasks have unmet acceptance criteria
  ⚠ 6 tasks introduced TODOs (follow-up needed)
  ⚠ 2 tasks had significant scope creep

  Tasks to Revivify:
  1. beads-abc123: Session persistence not implemented
  2. beads-def456: Error handling incomplete

  New Tasks Suggested: 3

═══════════════════════════════════════════════════════════════════

PRIORITY ACTIONS:
1. [HIGH] Add test automation hook (saves ~5min/task)
2. [HIGH] Implement 'cub progress' command (reduce format drift)
3. [MEDIUM] Clarify PROMPT.md testing section
4. [MEDIUM] Create follow-up tasks for skew issues
5. [LOW] Optimize verbose logging hook

Full report: .cub/analysis/2026-01-15.json
Generate tasks: cub analyze --generate-tasks
```

---

## Generated Artifacts

### Suggested PROMPT.md Updates

```markdown
## Suggested Updates to PROMPT.md

### Current (line 45-50):
> Make sure tests pass before completing tasks.

### Suggested:
> ## Testing Requirements
> - Run `npm test` after any code changes
> - Maintain test coverage above 80%
> - Add tests for new functions (at least happy path + one error case)
> - Do NOT mark task complete if tests fail

### Rationale:
Agent showed confusion about test expectations in 4/15 runs.
Specific thresholds and commands reduce ambiguity.
```

### Generated Hook Scripts

```bash
# Suggested: .cub/hooks/post-task.d/auto_test.sh
#!/bin/bash
# Auto-generated by cub analyze
# Pattern: Agent ran tests manually in 87% of tasks

echo "Running automated tests..."
npm test || {
  echo "Tests failed - task may need revision"
  exit 1
}
```

### Generated Follow-up Tasks

```json
[
  {
    "title": "Add session persistence to authentication",
    "description": "Follow-up from beads-abc123. The original task implemented login/logout but session persistence was not completed.\n\n## Acceptance Criteria\n- [ ] Session survives page refresh\n- [ ] Session expires after 24h of inactivity",
    "type": "task",
    "priority": 1,
    "depends_on": [],
    "labels": ["follow-up", "auth", "from:beads-abc123"]
  }
]
```

---

## Configuration

```json
{
  "analysis": {
    "enabled": true,
    "auto_run": "after_session",
    "dimensions": {
      "instruction_clarity": true,
      "task_quality": true,
      "hook_opportunities": true,
      "delegation_gaps": true,
      "spec_implementation_skew": true
    },
    "thresholds": {
      "confusion_patterns_per_task": 2,
      "max_iterations_normal": 3,
      "scope_creep_file_ratio": 1.5
    },
    "ai_assisted": {
      "enabled": true,
      "model": "haiku",
      "for_dimensions": ["spec_implementation_skew"]
    },
    "output": {
      "dir": ".cub/analysis/",
      "keep_history": 20
    }
  }
}
```

---

## Implementation Notes

### Data Sources

| Source | What It Provides |
|--------|------------------|
| `.cub/runs/*/` | Run metadata, task outcomes |
| `harness_output.log` | Agent reasoning, confusion signals |
| `task.json` | Task specs for comparison |
| `changes.patch` | Actual implementation diff |
| Git history | Commit patterns, file changes |
| `progress.txt` (if exists) | Progress tracking attempts |

### Analysis Pipeline

```
1. Collect run data
   └─> .cub/runs/*/tasks/*

2. Parse harness output
   └─> Extract confusion signals, patterns

3. Compare specs to implementations
   └─> Git diff analysis, criteria matching

4. Detect patterns across runs
   └─> Aggregate statistics, identify trends

5. Generate recommendations
   └─> Prioritize by impact and frequency

6. Output report + artifacts
   └─> JSON, markdown, suggested tasks
```

---

## Acceptance Criteria

### Phase 1: Basic Analysis
- [ ] Instruction clarity analysis (pattern detection)
- [ ] Task quality metrics (iterations, scope)
- [ ] Summary report generation
- [ ] JSON output format

### Phase 2: Actionable Insights
- [ ] Hook opportunity detection
- [ ] Delegation gap analysis
- [ ] Spec-implementation skew detection
- [ ] Generated follow-up tasks

### Phase 3: Automation
- [ ] Auto-run after sessions
- [ ] PROMPT.md update suggestions
- [ ] Hook script generation
- [ ] Integration with `cub audit`

---

## Future Enhancements

- Real-time analysis during runs (not just post-hoc)
- ML-based pattern detection across many runs
- Team-level analysis (patterns across developers)
- Integration with verification (did skew cause bugs?)
- Predictive task difficulty scoring
- Automatic PROMPT.md evolution based on learnings

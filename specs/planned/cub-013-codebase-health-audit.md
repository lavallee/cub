---
status: planned
priority: medium
complexity: medium
dependencies: []
created: 2026-01-10
updated: 2026-01-19
readiness:
  score: 6
  blockers:
  - Partial implementation exists, needs completion
  questions:
  - Which health metrics to track?
  - How to integrate with existing cub audit?
  decisions_needed:
  - Define complete health metric set
  - Extend existing cub audit command
  tools_needed:
  - Competitive Analysis Tool (existing audit tools)
  - Trade-off Analyzer (which metrics to track)
  - Implementation Path Generator (extend partial impl)
notes: |
  Partial implementation exists (cub audit).
  Needs expansion and metric definition.
source: cub original
spec_id: cub-013
---
# Codebase Health Audit

**Source:** Original feature for cub
**Dependencies:** None (can run anytime)
**Complexity:** Medium
**Timing:** Flexible - before major work, after migrations, or as maintenance

## Overview

Systematic analysis of code, documentation, and tests to identify dead paths, stale docs, and coverage gaps. Designed to run at various points in the development lifecycle, acknowledging that the codebase may shift significantly between when this spec is written and when it's implemented.

## Problem Statement

Codebases accumulate cruft:
- **Dead code:** Unreachable functions, unused exports, orphaned files
- **Stale docs:** README sections that describe removed features, outdated examples
- **Test gaps:** New code without tests, tests for removed code, flaky tests
- **Inconsistencies:** Naming conventions drift, patterns diverge

This is especially true during major transitions (like language migration or feature integration).

## Design Principles

### 1. Point-in-Time Analysis

This audit runs against the codebase **as it exists when executed**, not against a fixed target. The spec describes *what to analyze* and *how*, not *what the codebase should look like*.

### 2. Language-Aware

Post-migration, cub may contain:
- Bash scripts (hooks, CLI, utilities)
- Go binaries (core engine)
- Python modules (pipeline, plugins)
- Markdown docs
- BATS tests + Go tests + Python tests

The audit must handle all of these.

### 3. Actionable Output

Results should be:
- Specific (file:line, not vague warnings)
- Prioritized (critical vs nice-to-have)
- Actionable (clear remediation steps)
- Optional auto-fix where safe

---

## Audit Dimensions

### 1. Dead Code Detection

#### Bash

```bash
# Detect unused functions
audit_bash_dead_functions() {
  # Find all function definitions
  # Find all function calls
  # Report functions defined but never called
}

# Detect unreachable code
audit_bash_unreachable() {
  # Find code after unconditional return/exit
  # Find branches that can never execute
}

# Detect unused variables
audit_bash_unused_vars() {
  # Find variable assignments
  # Find variable references
  # Report assigned but never read
}

# Detect orphan files
audit_bash_orphan_files() {
  # Find .sh files not sourced by any other file
  # Check against known entry points
}
```

**Tools:** shellcheck (--enable=all), custom AST analysis

#### Go (post-migration)

```go
// Use go/ast and go/types for analysis
// Or leverage: deadcode, unused, staticcheck

audit_go_dead_code() {
  // Unreachable functions
  // Unused struct fields
  // Unexported and uncalled functions
  // Dead assignments
}
```

**Tools:** `staticcheck`, `deadcode`, `unused`, `go vet`

#### Python (if applicable)

```python
# Use vulture for dead code detection
# Use pylint for unused imports/variables

def audit_python_dead_code():
    # Unused imports
    # Unreachable code
    # Unused functions/classes
    # Dead assignments
```

**Tools:** `vulture`, `pylint`, `pyflakes`

#### Cross-Language

```bash
# Detect orphan files across languages
audit_orphan_files() {
  # List all source files
  # Build dependency graph
  # Find files with no incoming edges (not imported/sourced/called)
  # Exclude known entry points
}
```

---

### 2. Documentation Freshness

#### README Analysis

```bash
audit_readme() {
  # Extract code blocks
  # Try to execute/validate them
  # Check for referenced files that don't exist
  # Check for referenced commands that don't work
  # Identify sections that may be stale
}
```

**Checks:**
- [ ] Code examples are syntactically valid
- [ ] Referenced files exist
- [ ] CLI commands shown actually work
- [ ] Version numbers are current
- [ ] Links are not broken
- [ ] Installation instructions work

#### Inline Documentation

```bash
audit_inline_docs() {
  # Find functions without docstrings/comments
  # Find docstrings that don't match function signature
  # Find TODO/FIXME/HACK comments older than N days
  # Find comments referencing removed code
}
```

#### Generated Documentation

```bash
audit_generated_docs() {
  # If using godoc, rustdoc, pydoc, etc.
  # Check for undocumented public APIs
  # Check for broken cross-references
}
```

#### Changelog/Version Consistency

```bash
audit_changelog() {
  # CHANGELOG.md mentions version X
  # version file says Y
  # git tags say Z
  # Check consistency
}
```

---

### 3. Test Coverage Analysis

#### Coverage Metrics

```bash
audit_test_coverage() {
  # Run tests with coverage
  # Report overall coverage percentage
  # Identify files with <50% coverage
  # Identify functions with 0% coverage
  # Track coverage trend over time
}
```

**Per-language:**

| Language | Tool | Command |
|----------|------|---------|
| Bash | kcov or bashcov | `kcov --bash-method=DEBUG coverage/ bats tests/` |
| Go | go test -cover | `go test -coverprofile=coverage.out ./...` |
| Python | coverage.py | `coverage run -m pytest && coverage report` |

#### Test Quality

```bash
audit_test_quality() {
  # Tests without assertions (always pass)
  # Duplicate test names
  # Tests that never fail (suspicious)
  # Tests that test nothing (empty body)
  # Flaky tests (different results on re-run)
}
```

#### Test-Code Alignment

```bash
audit_test_alignment() {
  # Source files without corresponding test files
  # Test files for removed source files
  # Tests referencing removed functions
  # Tests using deprecated APIs
}
```

**Naming convention detection:**
```
Source: lib/tasks.sh      → Test: tests/tasks.bats
Source: pkg/tasks/tasks.go → Test: pkg/tasks/tasks_test.go
Source: cub_pipeline/triage.py → Test: tests/test_triage.py
```

#### Test Isolation

```bash
audit_test_isolation() {
  # Tests that depend on execution order
  # Tests that leave state behind
  # Tests that require network
  # Tests that depend on specific environment
}
```

---

### 4. Consistency Analysis

#### Naming Conventions

```bash
audit_naming() {
  # Function naming (snake_case vs camelCase)
  # Variable naming
  # File naming
  # Report deviations from dominant pattern
}
```

#### Pattern Consistency

```bash
audit_patterns() {
  # Error handling patterns
  # Logging patterns
  # Configuration access patterns
  # Report inconsistencies
}
```

#### API Consistency

```bash
audit_api_consistency() {
  # Similar functions with different signatures
  # Inconsistent return types
  # Inconsistent error handling
}
```

---

## Output Format

### Summary Report

```
CUB CODEBASE HEALTH AUDIT
═════════════════════════════════════════════════════════════

Run: 2026-01-15 14:30:00
Commit: abc123
Languages: Bash (65%), Go (30%), Python (5%)

DEAD CODE                                           Score: B+
─────────────────────────────────────────────────────────────
  ✓ No orphan files detected
  ⚠ 3 unused functions in lib/harness.sh
  ⚠ 2 unused variables in lib/config.sh
  ✓ Go code clean (staticcheck passed)

DOCUMENTATION                                       Score: C
─────────────────────────────────────────────────────────────
  ✗ README.md: 2 broken code examples
  ⚠ CHANGELOG.md: Missing entries for v0.13
  ⚠ 12 functions without docstrings
  ✓ All links valid

TEST COVERAGE                                       Score: B
─────────────────────────────────────────────────────────────
  Overall: 73% (target: 80%)
  ✗ lib/artifacts.sh: 45% coverage
  ✗ pkg/harness/: 52% coverage
  ✓ lib/tasks.sh: 89% coverage
  ⚠ 3 test files for removed code

CONSISTENCY                                         Score: A-
─────────────────────────────────────────────────────────────
  ✓ Naming conventions consistent
  ⚠ 2 different error handling patterns in harness code
  ✓ Logging patterns consistent

OVERALL HEALTH: B
═════════════════════════════════════════════════════════════

PRIORITY FIXES:
1. [HIGH] Fix broken README examples (2 issues)
2. [MEDIUM] Add tests for lib/artifacts.sh (+35% coverage needed)
3. [LOW] Remove unused functions in lib/harness.sh

Full report: .cub/audit/2026-01-15-143000.json
```

### Detailed JSON Report

```json
{
  "audit_time": "2026-01-15T14:30:00Z",
  "commit": "abc123",
  "summary": {
    "dead_code": {"score": "B+", "issues": 5},
    "documentation": {"score": "C", "issues": 15},
    "test_coverage": {"score": "B", "percentage": 73},
    "consistency": {"score": "A-", "issues": 2}
  },
  "dead_code": {
    "unused_functions": [
      {"file": "lib/harness.sh", "line": 234, "name": "legacy_invoke", "last_called": null},
      {"file": "lib/harness.sh", "line": 456, "name": "deprecated_parse", "last_called": null}
    ],
    "unused_variables": [...],
    "orphan_files": []
  },
  "documentation": {
    "broken_examples": [
      {"file": "README.md", "line": 45, "code": "cub run --old-flag", "error": "Unknown flag"}
    ],
    "missing_docstrings": [...],
    "stale_todos": [...]
  },
  "test_coverage": {
    "overall": 73,
    "by_file": [
      {"file": "lib/artifacts.sh", "coverage": 45, "uncovered_lines": [23, 45, 67]},
      ...
    ],
    "orphan_tests": [
      {"file": "tests/old_feature.bats", "reason": "Tests removed lib/old_feature.sh"}
    ]
  },
  "consistency": {
    "naming_issues": [],
    "pattern_issues": [
      {"pattern": "error_handling", "locations": ["harness.sh:100", "harness.sh:200"], "note": "Different approaches"}
    ]
  },
  "recommendations": [
    {"priority": "high", "category": "documentation", "action": "Fix README examples", "effort": "30m"},
    {"priority": "medium", "category": "coverage", "action": "Add tests for artifacts.sh", "effort": "2h"}
  ]
}
```

---

## CLI Interface

```bash
# Run full audit
cub audit

# Run specific dimension
cub audit --dead-code
cub audit --docs
cub audit --coverage
cub audit --consistency

# Output formats
cub audit --format summary    # Default, human-readable
cub audit --format json       # Machine-readable
cub audit --format markdown   # For GitHub issues/PRs

# Auto-fix where possible
cub audit --fix              # Apply safe fixes
cub audit --fix --dry-run    # Show what would be fixed

# CI integration
cub audit --ci               # Exit non-zero if score below threshold
cub audit --ci --threshold B # Require at least B grade

# Historical comparison
cub audit --compare          # Compare to last audit
cub audit --trend            # Show trend over time
```

---

## Auto-Fix Capabilities

### Safe Auto-Fixes

| Issue | Auto-Fix | Safety |
|-------|----------|--------|
| Unused imports | Remove import line | Safe |
| Trailing whitespace | Remove | Safe |
| Missing newline at EOF | Add | Safe |
| Unused local variables | Remove or comment | Safe with review |
| Orphan test files | Move to `tests/archive/` | Safe |

### Unsafe (Manual Review Required)

| Issue | Why Manual |
|-------|------------|
| Unused functions | May be called dynamically |
| Unused exported symbols | May be used by external code |
| Stale documentation | Needs human judgment |
| Low coverage areas | Need to write tests |

---

## Integration Points

### Pre-Commit Hook

```bash
# .cub/hooks/pre-commit.d/audit.sh
cub audit --quick --ci --threshold B
```

### CI Pipeline

```yaml
# GitHub Actions
- name: Codebase Audit
  run: |
    cub audit --ci --format json > audit.json
    cub audit --format markdown > audit.md

- name: Comment on PR
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v6
  with:
    script: |
      const audit = require('./audit.json');
      // Post summary as PR comment
```

### Scheduled Runs

```bash
# Weekly audit cron job
0 9 * * 1 cd /path/to/project && cub audit --format json >> audit-history.jsonl
```

---

## Handling Shifting Ground

This spec is written with awareness that the codebase will change significantly:

### Before Language Migration

- Focus on Bash analysis (shellcheck, custom scripts)
- BATS test coverage
- Identify code that will be migrated vs retired

### During Language Migration

- Track which Bash code has Go equivalents
- Identify orphaned Bash after Go takes over
- Ensure tests migrate with code

### After Language Migration

- Full multi-language analysis
- Go static analysis (staticcheck, golangci-lint)
- Python analysis if applicable
- Cross-language dead code detection

### Adaptation Strategy

```bash
audit_detect_languages() {
  # Dynamically detect what's in the codebase
  # Adjust analysis accordingly

  if [[ -d "cmd/" ]] || [[ -f "go.mod" ]]; then
    RUN_GO_ANALYSIS=true
  fi

  if [[ -d "python/" ]] || [[ -f "pyproject.toml" ]]; then
    RUN_PYTHON_ANALYSIS=true
  fi

  if ls lib/*.sh &>/dev/null; then
    RUN_BASH_ANALYSIS=true
  fi
}
```

### Version-Aware Analysis

```json
{
  "audit_config": {
    "bash": {
      "enabled": true,
      "paths": ["lib/", "bin/"],
      "exclude": ["lib/legacy/"]
    },
    "go": {
      "enabled": "auto",
      "min_version": "1.21"
    },
    "python": {
      "enabled": "auto",
      "min_version": "3.10"
    }
  }
}
```

---

## Configuration

```json
{
  "audit": {
    "enabled": true,
    "schedule": "weekly",
    "thresholds": {
      "coverage": 80,
      "grade": "B"
    },
    "ignore": {
      "files": ["lib/vendor/*", "*.generated.go"],
      "rules": ["unused-parameter"]
    },
    "auto_fix": {
      "enabled": false,
      "safe_only": true
    },
    "languages": {
      "bash": {"enabled": true},
      "go": {"enabled": "auto"},
      "python": {"enabled": "auto"}
    },
    "output": {
      "dir": ".cub/audit/",
      "keep_history": 10
    }
  }
}
```

---

## Implementation Notes

### Phased Implementation

**Phase 1: Basic Analysis**
- Dead code detection (single language)
- Basic documentation checks
- Test coverage reporting
- Summary output

**Phase 2: Multi-Language**
- Go analysis (post-migration)
- Python analysis (if applicable)
- Cross-language orphan detection

**Phase 3: Advanced**
- Auto-fix capabilities
- CI integration
- Historical trends
- PR comments

### Tool Dependencies

| Language | Tools Required |
|----------|---------------|
| Bash | shellcheck, kcov (optional) |
| Go | go, staticcheck, golangci-lint |
| Python | pylint, vulture, coverage |
| Docs | markdown-link-check |

### Performance Considerations

- Cache analysis results
- Incremental analysis (only changed files)
- Parallel analysis per language
- Skip analysis if no changes

---

## Acceptance Criteria

### Phase 1
- [ ] Dead function detection for Bash
- [ ] README validation (code blocks, links)
- [ ] Test coverage reporting (BATS)
- [ ] Summary report generation
- [ ] JSON output format

### Phase 2
- [ ] Go static analysis integration
- [ ] Multi-language orphan detection
- [ ] Documentation freshness scoring
- [ ] Historical comparison

### Phase 3
- [ ] Auto-fix for safe issues
- [ ] CI integration (exit codes, thresholds)
- [ ] PR comment generation
- [ ] Trend visualization

---

## Example Scenarios

### Scenario 1: Pre-Migration Cleanup

Before starting Go migration, run audit to:
- Identify truly dead Bash code (don't migrate it)
- Find undocumented functions (document or remove)
- Establish coverage baseline

### Scenario 2: Post-Migration Verification

After migrating tasks.sh to Go:
- Detect orphaned Bash (tasks.sh now unused)
- Verify Go has equivalent test coverage
- Check docs reference new commands

### Scenario 3: Routine Maintenance

Weekly audit catches:
- New code without tests
- Stale TODO comments
- Documentation drift

---

## Future Enhancements

- AI-assisted documentation generation
- Automatic test generation for uncovered code
- Architecture drift detection
- Dependency freshness checking
- Security vulnerability scanning integration
- Performance regression detection

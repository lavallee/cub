# Verification Integrations

**Source:** Inspired by [Ramp's Inspect](https://builders.ramp.com/post/why-we-built-our-background-agent)
**Dependencies:** Implementation Review (conceptually related)
**Complexity:** High

## Overview

Connect cub to external services (observability, testing, deployment) so the AI can verify its work against real-world signals, not just static analysis and AI review.

## The Ramp Insight

From Ramp's Inspect post:
> "Inspect closes the loop on verifying its work by having all the context and tools needed to prove it."

They connect to: Sentry, Datadog, LaunchDarkly, Braintree, GitHub, Slack, Buildkite.

This enables the agent to:
- Check if errors increased after a change
- Verify feature flags are correctly configured
- Confirm builds pass in CI
- See real telemetry from preview deployments

## The Core Question: Is This Cub or Something Else?

### Option A: Verification as Part of Cub

Cub directly integrates with external services.

**Pros:**
- Single tool, unified experience
- Tight integration with task lifecycle
- Simpler for users (one thing to configure)

**Cons:**
- Scope creep (cub becomes "everything")
- Every integration is cub's maintenance burden
- Different teams have wildly different stacks
- Auth/secrets management complexity

### Option B: Verification as Separate Tool

A dedicated verification service/tool that cub calls via hooks.

**Pros:**
- Separation of concerns
- Verification tool can evolve independently
- Could be used by other AI agents (not just cub)
- Teams can build custom verification for their stack
- Cub stays focused on orchestration

**Cons:**
- Two tools to install/configure
- Integration overhead
- Potential for version mismatches

### Option C: Hybrid - Cub Provides Hooks, Ecosystem Provides Verifiers

Cub defines a verification interface. Verification implementations are plugins/external tools.

**Pros:**
- Best of both worlds
- Community can build verifiers
- Teams can build internal verifiers
- Cub stays lean but extensible

**Cons:**
- Requires well-designed interface
- Bootstrap problem (need initial verifiers)

---

## Recommendation: Option C (Hybrid)

Cub should:
1. Define a **Verification Protocol** (interface for verifiers)
2. Provide **hooks** at key points in the task lifecycle
3. Ship with **basic built-in verifiers** (tests pass, build succeeds, lint clean)
4. Allow **external verifiers** via the protocol

This keeps cub focused while enabling rich verification ecosystems.

---

## Verification Protocol

### Verifier Interface

A verifier is any executable that:
1. Receives context about what changed
2. Performs verification checks
3. Returns structured results

```bash
# Verifier contract
# Input: JSON on stdin
# Output: JSON on stdout
# Exit code: 0 = pass, 1 = fail, 2 = error

# Input schema
{
  "task_id": "beads-abc123",
  "task_type": "feature",
  "changes": {
    "files": ["src/auth.js", "src/auth.test.js"],
    "diff": "...",
    "commits": ["abc123"]
  },
  "context": {
    "branch": "feature/auth",
    "base_branch": "main",
    "environment": "preview-123"
  }
}

# Output schema
{
  "verifier": "sentry-error-check",
  "version": "1.0.0",
  "status": "pass" | "fail" | "warn" | "skip",
  "checks": [
    {
      "name": "No new errors",
      "status": "pass",
      "message": "Error rate unchanged (0.02%)",
      "details": { ... }
    },
    {
      "name": "No regressions",
      "status": "pass",
      "message": "All existing errors still below threshold"
    }
  ],
  "summary": "Sentry verification passed",
  "blocking": false
}
```

### Verifier Discovery

```bash
# Built-in verifiers
~/.config/cub/verifiers/
├── tests.sh          # Run test suite
├── build.sh          # Run build
└── lint.sh           # Run linter

# Project verifiers (override or extend)
.cub/verifiers/
├── tests.sh          # Project-specific test runner
├── e2e.sh            # E2E tests
└── sentry.sh         # Sentry integration

# External verifiers (installed separately)
# Discovered via PATH or explicit config
cub-verify-sentry
cub-verify-datadog
cub-verify-lighthouse
```

### Verifier Configuration

```json
{
  "verification": {
    "enabled": true,
    "run_on": ["task_complete", "before_close"],
    "verifiers": {
      "tests": {
        "enabled": true,
        "blocking": true,
        "command": "npm test"
      },
      "build": {
        "enabled": true,
        "blocking": true
      },
      "sentry": {
        "enabled": true,
        "blocking": false,
        "command": "cub-verify-sentry",
        "config": {
          "org": "my-org",
          "project": "my-project",
          "error_threshold": 0.01
        }
      },
      "lighthouse": {
        "enabled": false,
        "blocking": false,
        "config": {
          "performance_threshold": 90
        }
      }
    },
    "require_all_pass": false,
    "require_blocking_pass": true
  }
}
```

---

## Cub's Verification Hooks

### Hook Points

```
Task Lifecycle:

  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │  Start   │───>│Implement │───>│ Verify   │───>│  Close   │
  │  Task    │    │          │    │          │    │  Task    │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘
       │               │               │               │
       ▼               ▼               ▼               ▼
   pre-task      post-iteration   verification    pre-close
                                     hook           hook

Verification can run:
- After each iteration (continuous feedback)
- On task completion (before closing)
- On demand (cub verify <task-id>)
```

### Hook Implementation

```bash
# lib/hooks/verification.sh

run_verification() {
  local task_id=$1
  local trigger=$2  # "iteration" | "complete" | "manual"

  local context
  context=$(build_verification_context "$task_id")

  local results=()
  local any_blocking_failed=false

  # Run each enabled verifier
  for verifier in $(get_enabled_verifiers); do
    local result
    result=$(run_verifier "$verifier" "$context")

    results+=("$result")

    local status
    status=$(echo "$result" | jq -r '.status')

    local blocking
    blocking=$(echo "$result" | jq -r '.blocking')

    if [[ "$status" == "fail" && "$blocking" == "true" ]]; then
      any_blocking_failed=true
    fi

    log_event "verification_result" "verifier=$verifier status=$status"
  done

  # Aggregate results
  local summary
  summary=$(aggregate_verification_results "${results[@]}")

  # Store for task record
  store_verification_results "$task_id" "$summary"

  # Return overall status
  if [[ "$any_blocking_failed" == "true" ]]; then
    return 1
  fi
  return 0
}

run_verifier() {
  local verifier=$1
  local context=$2

  local command
  command=$(get_verifier_command "$verifier")

  local config
  config=$(get_verifier_config "$verifier")

  # Merge config into context
  local full_context
  full_context=$(echo "$context" | jq --argjson cfg "$config" '. + {config: $cfg}')

  # Run with timeout
  local result
  if result=$(echo "$full_context" | timeout 300 $command 2>&1); then
    echo "$result"
  else
    # Verifier failed to run
    jq -n --arg v "$verifier" '{
      verifier: $v,
      status: "error",
      message: "Verifier failed to execute",
      blocking: false
    }'
  fi
}
```

### Verification Results in Task Record

```json
{
  "task_id": "beads-abc123",
  "status": "closed",
  "verification": {
    "ran_at": "2026-01-13T15:30:00Z",
    "trigger": "complete",
    "overall_status": "pass",
    "results": [
      {
        "verifier": "tests",
        "status": "pass",
        "duration_ms": 4500
      },
      {
        "verifier": "build",
        "status": "pass",
        "duration_ms": 12000
      },
      {
        "verifier": "sentry",
        "status": "warn",
        "message": "Error rate slightly elevated (0.03% vs 0.02%)",
        "blocking": false
      }
    ]
  }
}
```

---

## Built-in Verifiers

Cub ships with basic verifiers:

### 1. Tests Verifier

```bash
#!/usr/bin/env bash
# verifiers/tests.sh

run_tests() {
  local context=$1
  local config
  config=$(echo "$context" | jq -r '.config // {}')

  local command
  command=$(echo "$config" | jq -r '.command // "npm test"')

  local output
  local exit_code
  output=$(eval "$command" 2>&1)
  exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    jq -n '{
      verifier: "tests",
      status: "pass",
      message: "All tests passed",
      blocking: true
    }'
  else
    jq -n --arg output "$output" '{
      verifier: "tests",
      status: "fail",
      message: "Tests failed",
      details: {output: $output},
      blocking: true
    }'
  fi
}

run_tests "$(cat)"
```

### 2. Build Verifier

```bash
#!/usr/bin/env bash
# verifiers/build.sh

# Similar structure - runs build command, reports pass/fail
```

### 3. Lint Verifier

```bash
#!/usr/bin/env bash
# verifiers/lint.sh

# Runs linter, reports issues as warnings or failures
```

---

## External Verifier Examples

### Sentry Verifier

A separate tool (installed via npm/brew/etc.):

```bash
#!/usr/bin/env bash
# cub-verify-sentry

# Reads context from stdin
context=$(cat)
config=$(echo "$context" | jq '.config')

org=$(echo "$config" | jq -r '.org')
project=$(echo "$config" | jq -r '.project')
threshold=$(echo "$config" | jq -r '.error_threshold // 0.01')

# Get current error rate from Sentry API
error_rate=$(curl -s "https://sentry.io/api/0/projects/${org}/${project}/stats/" \
  -H "Authorization: Bearer ${SENTRY_AUTH_TOKEN}" | jq '.error_rate')

# Compare to threshold
if (( $(echo "$error_rate < $threshold" | bc -l) )); then
  jq -n --arg rate "$error_rate" '{
    verifier: "sentry",
    status: "pass",
    message: "Error rate \($rate) below threshold",
    blocking: false
  }'
else
  jq -n --arg rate "$error_rate" --arg thresh "$threshold" '{
    verifier: "sentry",
    status: "warn",
    message: "Error rate \($rate) above threshold \($thresh)",
    blocking: false
  }'
fi
```

### Datadog Verifier

```bash
#!/usr/bin/env bash
# cub-verify-datadog

# Check for anomalies in metrics after deployment
# Uses Datadog API to compare before/after
```

### Lighthouse Verifier

```bash
#!/usr/bin/env bash
# cub-verify-lighthouse

# Run Lighthouse on preview URL
# Check performance/accessibility scores
```

### Preview Deployment Verifier

```bash
#!/usr/bin/env bash
# cub-verify-preview

# Deploy to preview environment
# Run smoke tests
# Check for console errors
# Take screenshots
```

---

## Integration with Implementation Review

Verification complements Implementation Review:

| Aspect | Implementation Review | Verification |
|--------|----------------------|--------------|
| **What** | Code quality | Runtime behavior |
| **How** | AI analysis | Real tool execution |
| **When** | After implementation | After deployment/run |
| **Signals** | DRY, patterns, style | Errors, perf, tests |

Both can be required before task closure:

```json
{
  "review": {
    "auto_impl": true,
    "require_pass": true
  },
  "verification": {
    "enabled": true,
    "require_blocking_pass": true
  },
  "gating": {
    "require_review": true,
    "require_verification": true
  }
}
```

---

## Verification in Sandbox Mode

When running in sandbox, verification can:
1. Run inside the sandbox (tests, build, lint)
2. Run against sandbox preview URL (if exposed)
3. Run on host after export (before apply)

```bash
# Verify inside sandbox
cub sandbox verify

# Verify then apply if pass
cub sandbox apply --verify-first
```

---

## CLI Interface

```bash
# Run verification manually
cub verify <task-id>
cub verify --all-open

# List available verifiers
cub verify --list

# Run specific verifier
cub verify <task-id> --only tests,build

# Skip verification
cub close <task-id> --skip-verification

# Verification status
cub status <task-id> --verification
```

---

## Future: Verification Service

If verification grows complex enough, it could become a standalone service:

```
┌─────────┐     ┌──────────────────┐     ┌──────────────┐
│   cub   │────>│ Verification     │────>│  Sentry      │
│         │     │ Service          │     │  Datadog     │
│         │<────│                  │<────│  etc.        │
└─────────┘     └──────────────────┘     └──────────────┘

Benefits:
- Centralized auth for external services
- Caching of verification results
- Async verification with webhooks
- Shared verification across team
- Historical verification data
```

Cub would call the service instead of individual verifiers:

```bash
# Instead of running verifiers locally
curl -X POST https://verify.example.com/run \
  -d '{"task_id": "abc", "changes": {...}}'

# Poll or webhook for results
```

This is a natural evolution if verification becomes critical infrastructure.

---

## Configuration

```json
{
  "verification": {
    "enabled": true,
    "run_on": ["task_complete"],
    "timeout": 300,
    "parallel": true,
    "verifiers": {
      "tests": {"enabled": true, "blocking": true},
      "build": {"enabled": true, "blocking": true},
      "lint": {"enabled": true, "blocking": false}
    },
    "external_verifiers": [
      {
        "name": "sentry",
        "command": "cub-verify-sentry",
        "blocking": false,
        "config": {"org": "...", "project": "..."}
      }
    ],
    "service": {
      "enabled": false,
      "url": "https://verify.example.com"
    }
  }
}
```

---

## Acceptance Criteria

### Phase 1: Hook Infrastructure
- [ ] Verification hook points in task lifecycle
- [ ] Verifier interface specification
- [ ] Built-in verifiers (tests, build, lint)
- [ ] Verification results in task records
- [ ] `cub verify` CLI command

### Phase 2: External Verifiers
- [ ] External verifier discovery
- [ ] Verifier configuration
- [ ] Example external verifiers documented
- [ ] Blocking vs non-blocking verifiers

### Phase 3: Advanced
- [ ] Verification in sandbox mode
- [ ] Parallel verifier execution
- [ ] Verification service protocol (for future)
- [ ] Integration with gating

---

## Summary: Is This Cub or Something Else?

**Cub's role:**
- Define the verification protocol
- Provide hook points in task lifecycle
- Ship basic built-in verifiers
- Store/report verification results

**External tools' role:**
- Implement verifiers for specific services
- Handle auth/API complexity for those services
- Potentially: centralized verification service

This keeps cub lean while enabling verification ecosystems to develop.

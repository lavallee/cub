---
status: planned
priority: medium
complexity: medium
dependencies: []
created: 2026-01-10
updated: 2026-01-19
readiness:
  score: 7
  blockers:
  - Harness abstraction in research phase (spec exists)
  questions:
  - Which models to use for review?
  - How to aggregate review results?
  - Weight reviews by model capabilities?
  decisions_needed:
  - Define review aggregation strategy (consensus, voting, weighted)
  - Choose initial models for review (Claude + GPT-4 + ?)
  - Design review comparison UI/output
  tools_needed:
  - Trade-off Analyzer (which models to use when)
  - API Design Validator (review aggregation API)
notes: |
  Harness abstraction spec now exists (researching/harness-abstraction.md).
  Can implement once harness abstraction reaches planned/implementation phase.
  Core approach: Run same task on multiple harnesses, compare outputs.
source: cub original
spec_id: cub-018
---
# Multi-Model Review

**Source:** [gmickel-claude-marketplace](https://github.com/gmickel/gmickel-claude-marketplace) (Flow-Next)
**Dependencies:** Implementation Review
**Complexity:** High

## Overview

Cross-validate implementation work using different AI models to catch issues that single-model review might miss.

## Reference Implementation

From Flow-Next:
> "Multi-model reviews via RepoPrompt for cross-validation"

Different models have different strengths/weaknesses; consensus provides higher confidence.

## Problem Statement

Single-model review limitations:
- Model-specific blind spots
- Consistent biases in assessment
- May miss issues another model would catch
- No second opinion on ambiguous cases

Multi-model review provides:
- Diverse perspectives
- Higher confidence through consensus
- Catch model-specific blind spots
- Better coverage of edge cases

## Proposed Solution

Run implementation reviews through multiple AI models and synthesize results.

## Proposed Interface

```bash
# Multi-model review of task
cub review <task-id> --multi-model
cub review <task-id> --models "sonnet,opus,haiku"

# Require consensus for approval
cub review <task-id> --require-consensus

# Configure default models
cub config set review.models '["sonnet", "opus"]'

# View comparison
cub review <task-id> --multi-model --compare
```

## Review Strategy

### Model Selection

Different models for different purposes:

```yaml
model_roles:
  primary:
    model: "sonnet"
    purpose: "Balanced review - correctness and quality"

  secondary:
    model: "opus"
    purpose: "Deep analysis - architecture and edge cases"

  fast:
    model: "haiku"
    purpose: "Quick checks - obvious issues"
```

### Review Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Model A   │     │   Model B   │     │   Model C   │
│   (Sonnet)  │     │   (Opus)    │     │   (Haiku)   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
   Review A            Review B            Review C
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   Synthesizer   │
                  │  (Aggregate &   │
                  │    Compare)     │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Final Verdict  │
                  └─────────────────┘
```

## Implementation

### Parallel Review Execution

```bash
run_multi_model_review() {
  local task_id=$1
  local models=${2:-"sonnet opus"}

  local reviews=()
  local pids=()

  # Launch reviews in parallel
  for model in $models; do
    run_single_model_review "$task_id" "$model" > "/tmp/review_${model}.json" &
    pids+=($!)
  done

  # Wait for all to complete
  for pid in "${pids[@]}"; do
    wait "$pid"
  done

  # Collect results
  for model in $models; do
    reviews+=("$(cat "/tmp/review_${model}.json")")
  done

  # Synthesize
  synthesize_reviews "${reviews[@]}"
}

run_single_model_review() {
  local task_id=$1
  local model=$2

  local diff
  diff=$(get_task_diff "$task_id")

  local task_json
  task_json=$(task_get "$task_id")

  local prompt="Review this implementation:

## Task
$(echo "$task_json" | jq '.')

## Changes
\`\`\`diff
$diff
\`\`\`

## Review
Provide your assessment:
VERDICT: APPROVE | REQUEST_CHANGES | BLOCK
CONFIDENCE: 1-5
ISSUES: [list any issues]
STRENGTHS: [list strengths]
CONCERNS: [list concerns]"

  invoke_harness --prompt "$prompt" --model "$model" --output json
}
```

### Result Synthesis

```bash
synthesize_reviews() {
  local reviews=("$@")

  # Parse each review
  local verdicts=()
  local all_issues=()
  local all_strengths=()
  local all_concerns=()

  for review in "${reviews[@]}"; do
    local model
    model=$(echo "$review" | jq -r '.model')

    local verdict
    verdict=$(echo "$review" | jq -r '.verdict')
    verdicts+=("$model:$verdict")

    # Collect issues
    echo "$review" | jq -r '.issues[]' | while read -r issue; do
      all_issues+=("$model: $issue")
    done

    # Collect strengths/concerns similarly
  done

  # Determine consensus
  local consensus
  consensus=$(determine_consensus "${verdicts[@]}")

  # Build synthesis report
  jq -n \
    --argjson reviews "$(printf '%s\n' "${reviews[@]}" | jq -s '.')" \
    --arg consensus "$consensus" \
    --argjson issues "$(printf '%s\n' "${all_issues[@]}" | jq -R . | jq -s '.')" \
    '{
      consensus: $consensus,
      reviews: $reviews,
      all_issues: $issues,
      agreement_level: (if $consensus == "unanimous" then "high" else "mixed" end)
    }'
}

determine_consensus() {
  local verdicts=("$@")

  local approve_count=0
  local changes_count=0
  local block_count=0

  for v in "${verdicts[@]}"; do
    case "${v#*:}" in
      APPROVE) ((approve_count++)) ;;
      REQUEST_CHANGES) ((changes_count++)) ;;
      BLOCK) ((block_count++)) ;;
    esac
  done

  local total=${#verdicts[@]}

  if [[ $approve_count -eq $total ]]; then
    echo "unanimous_approve"
  elif [[ $block_count -gt 0 ]]; then
    echo "blocked"
  elif [[ $changes_count -gt 0 ]]; then
    echo "changes_requested"
  else
    echo "mixed"
  fi
}
```

### Disagreement Handling

When models disagree:

```bash
handle_disagreement() {
  local synthesis=$1

  local consensus
  consensus=$(echo "$synthesis" | jq -r '.consensus')

  case "$consensus" in
    "unanimous_approve")
      echo "VERDICT: APPROVE (all models agree)"
      ;;
    "blocked")
      echo "VERDICT: BLOCK (at least one model blocks)"
      # Show blocking model's concerns
      ;;
    "changes_requested")
      echo "VERDICT: REQUEST_CHANGES"
      # Aggregate all requested changes
      ;;
    "mixed")
      echo "VERDICT: MANUAL_REVIEW_NEEDED"
      # Show comparison for human decision
      show_disagreement_comparison "$synthesis"
      ;;
  esac
}

show_disagreement_comparison() {
  local synthesis=$1

  echo "Model Comparison:"
  echo ""

  echo "$synthesis" | jq -r '.reviews[] | "[\(.model)] \(.verdict) (confidence: \(.confidence))"'

  echo ""
  echo "Differing Points:"

  # Show issues unique to each model
  echo "$synthesis" | jq -r '
    .reviews as $reviews |
    ($reviews | map(.issues) | add | unique) as $all |
    $all[] as $issue |
    "\($issue): found by \([$reviews[] | select(.issues | contains([$issue])) | .model] | join(", "))"
  '
}
```

## Consensus Strategies

### Strict Consensus

All models must agree:

```json
{
  "review": {
    "consensus_strategy": "strict",
    "require_all_approve": true
  }
}
```

### Majority Consensus

Majority rules:

```json
{
  "review": {
    "consensus_strategy": "majority",
    "majority_threshold": 0.5
  }
}
```

### Weighted Consensus

Weight by model capability:

```json
{
  "review": {
    "consensus_strategy": "weighted",
    "weights": {
      "opus": 2.0,
      "sonnet": 1.0,
      "haiku": 0.5
    }
  }
}
```

### Any Block

Any model can block (strictest):

```json
{
  "review": {
    "consensus_strategy": "any_block",
    "block_on_any_concern": true
  }
}
```

## Output Format

### Comparison View

```
Multi-Model Review: task-123 "Implement authentication"

┌─────────────┬─────────────┬─────────────┐
│   Sonnet    │    Opus     │   Haiku     │
├─────────────┼─────────────┼─────────────┤
│  APPROVE    │  APPROVE    │  APPROVE    │
│  Conf: 4/5  │  Conf: 5/5  │  Conf: 3/5  │
├─────────────┼─────────────┼─────────────┤
│ Issues:     │ Issues:     │ Issues:     │
│ - None      │ - Edge case │ - None      │
│             │   in line 42│             │
├─────────────┼─────────────┼─────────────┤
│ Strengths:  │ Strengths:  │ Strengths:  │
│ - Clean API │ - Good tests│ - Simple    │
│ - DRY       │ - Secure    │             │
└─────────────┴─────────────┴─────────────┘

Consensus: APPROVE WITH NOTES (2/3 clean approve, 1 minor concern)

Aggregated Issues:
- [Opus] Edge case handling missing in validatePassword (line 42)

Recommendation: Address Opus concern, then approve.
```

## Configuration

```json
{
  "review": {
    "multi_model": {
      "enabled": false,
      "default_models": ["sonnet", "opus"],
      "consensus_strategy": "any_block",
      "parallel_execution": true,
      "timeout_per_model": 60000,
      "fallback_on_timeout": true,
      "show_comparison": true
    }
  }
}
```

## Cost Considerations

Multi-model review multiplies token cost. Mitigations:

1. **Selective use**: Only for important/complex tasks
2. **Tiered approach**: Haiku first, escalate to Sonnet/Opus if issues found
3. **Budget allocation**: Reserve multi-model budget for critical features
4. **Caching**: Cache review results for unchanged code

```json
{
  "review": {
    "multi_model": {
      "budget_limit": 100000,
      "use_for_types": ["feature"],
      "skip_for_types": ["docs", "chore"],
      "tiered_review": true
    }
  }
}
```

## Acceptance Criteria

- [ ] Run reviews through multiple models in parallel
- [ ] Synthesize results into unified report
- [ ] Support consensus strategies (strict, majority, weighted)
- [ ] Handle disagreements with comparison view
- [ ] Aggregate issues from all models
- [ ] Configurable model selection
- [ ] Cost-conscious options (tiered, selective)
- [ ] Timeout handling per model

## Future Enhancements

- Model disagreement learning (which model was right historically)
- Automatic model selection based on task type
- External model support (GPT-4, Gemini)
- Review quality scoring over time
- Cost/benefit analysis per review

# Budget & Guardrails

Autonomous AI coding sessions can consume significant resources quickly. Cub provides robust budget management and safety guardrails to help you maintain control over costs, iterations, and sensitive data.

## Why Budget Management Matters

When running AI coding assistants autonomously, costs can spiral unexpectedly:

- **Token consumption**: Each task iteration can use 50K-500K+ tokens
- **Iteration loops**: A confused AI might retry the same failing task repeatedly
- **Session length**: Long-running sessions accumulate costs over time

Cub's budget system provides multiple layers of protection:

```
+------------------+
|   Hard Limits    |  <-- Absolute stops (tokens, cost, iterations)
+------------------+
|  Warning Zones   |  <-- Alerts before hitting limits
+------------------+
|  Task Limits     |  <-- Per-task protections
+------------------+
```

## Budget Types

Cub tracks multiple budget dimensions:

| Budget Type | What It Tracks | Default Limit |
|-------------|----------------|---------------|
| **Tokens** | Total tokens consumed | None (unlimited) |
| **Cost** | USD spent on API calls | None (unlimited) |
| **Tasks** | Number of tasks completed | None (unlimited) |
| **Iterations** | Loop cycles completed | 100 per run |
| **Task Iterations** | Retries per task | 3 per task |

## Quick Configuration

Set budgets in your `.cub.json` or global config:

```json
{
  "budget": {
    "max_tokens_per_task": 500000,
    "max_tasks_per_session": 10,
    "max_total_cost": 5.0
  },
  "guardrails": {
    "max_task_iterations": 3,
    "max_run_iterations": 50,
    "iteration_warning_threshold": 0.8
  }
}
```

Or via CLI flags:

```bash
# Set a $5 budget for this run
cub run --budget 5.0

# Set a token limit
cub run --budget-tokens 1000000
```

## Budget Status

Monitor budget usage during a run:

```bash
# View current run status
cub status

# Watch live dashboard
cub run --monitor
```

The status shows:

```
Budget Status
+------------------+------------+
| Metric           | Value      |
+------------------+------------+
| Tokens Used      | 245,892    |
| Tokens Limit     | 500,000    |
| Cost             | $1.23      |
| Cost Limit       | $5.00      |
| Tasks Completed  | 3          |
+------------------+------------+
```

## What Happens When Limits Are Reached

When a budget limit is hit:

1. **Current task completes** - The AI finishes its current work
2. **Run stops gracefully** - No abrupt termination
3. **Status logged** - Budget exhaustion recorded in logs
4. **Summary displayed** - Final statistics shown

```bash
[yellow]Budget exhausted. Stopping.[/yellow]

Run Summary
+------------------+------------+
| Duration         | 847.3s     |
| Iterations       | 12         |
| Tasks Completed  | 8          |
| Tokens Used      | 1,000,000  |
| Final Phase      | completed  |
+------------------+------------+
```

## Guardrails Overview

Beyond budgets, guardrails provide additional safety:

| Guardrail | Purpose | Default |
|-----------|---------|---------|
| **Max Task Iterations** | Prevents infinite retry loops | 3 |
| **Max Run Iterations** | Caps total loop cycles | 50 |
| **Warning Threshold** | Alerts at percentage of limit | 80% |
| **Secret Patterns** | Redacts sensitive data in logs | Enabled |

## Next Steps

<div class="grid cards" markdown>

-   :material-currency-usd: **Token Management**

    ---

    Deep dive into token tracking across different harnesses.

    [:octicons-arrow-right-24: Tokens](tokens.md)

-   :material-counter: **Iteration Limits**

    ---

    Configure task and run iteration limits.

    [:octicons-arrow-right-24: Limits](limits.md)

-   :material-shield-lock: **Secret Redaction**

    ---

    Protect sensitive data in logs and output.

    [:octicons-arrow-right-24: Secrets](secrets.md)

</div>

# Session Layer Specification (Parking Lot)

> **Status**: Idea captured for future consideration
> **Created**: 2025-01-19
> **Context**: Discovered during prompt/guidance audit

## Problem

Currently, each task invokes a harness from scratch, repeating ~707 tokens of boilerplate instructions:
- System prompt (workflow, rules): 478 tokens
- Task boilerplate + backend instructions: 229 tokens

For multi-task runs, this adds up:
- 10 tasks = 7,070 tokens of repeated instructions
- 50 tasks = 35,350 tokens (17.5% of 200k context)

## Proposed Solution

Introduce a **session** layer between `run` and `task`:

```
run (orchestrator)
  └── session (batches tasks, manages context)
        └── task 1
        └── task 2
        └── task N (until context budget reached)
  └── session (new context)
        └── task N+1
        ...
```

### Session Responsibilities

1. **One-time setup**: Inject system prompt + backend instructions once per session
2. **Task streaming**: Feed tasks sequentially within the session
3. **Context monitoring**: Track token usage, exit before compaction needed
4. **Graceful handoff**: Return to run loop when session should end

### Token Savings

| Tasks | Current | Session Approach | Savings |
|-------|---------|------------------|---------|
| 5 | 3,535 | 1,207 | 66% |
| 10 | 7,070 | 1,707 | 76% |
| 50 | 35,350 | 5,707 | 84% |

## Complexity Concerns

1. **Forward-looking estimation**: Hard to predict response size for next task
2. **Compaction detection**: Knowing when context is getting tight
3. **Mid-session failures**: State management if task N fails
4. **Harness support**: Not all harnesses may support multi-turn sessions

## Simpler Alternative

Start with fixed heuristics rather than dynamic context management:

- **Fixed batch size**: Run 3-5 small tasks per session
- **Task size classification**: Small/medium/large based on description length
- **Conservative exit**: Exit after any task if >50% of estimated budget used

## Questions to Resolve

1. How do harnesses report token usage mid-session?
2. Can we detect compaction events from harness output?
3. What's the failure recovery model for mid-session task failures?
4. Should session state persist across run invocations?

## Related

- `src/cub/cli/run.py` - Current task loop implementation
- `src/cub/core/harness/` - Harness interface definitions

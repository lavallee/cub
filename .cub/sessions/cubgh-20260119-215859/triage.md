# Triage Report: Harness Abstraction

**Date:** 2026-01-19
**Triage Depth:** Standard
**Status:** Approved

---

## Executive Summary

This feature replaces Cub's current shell-out harness implementation with a unified abstraction layer that supports multiple LLM providers (Claude, OpenAI, Gemini, local) while enabling provider-specific features like Claude Agent SDK hooks. The MVP is a full abstraction layer with all 4 providers, async-only API, and graceful degradation for missing features.

## Problem Statement

Cub is currently tightly coupled to Claude via shell-out. To support multi-model review, cost optimization, and provider-specific features (like hooks for circuit breakers), we need a harness abstraction that provides a common interface while allowing special capabilities when running Claude.

**Who has this problem:** Cub users who want to use multiple LLM providers, optimize costs by routing simple tasks to cheaper models, or leverage advanced features like circuit breakers via SDK hooks.

## Refined Vision

Build a harness abstraction layer that:
1. Provides a unified async interface (`run_task`, `stream_task`, `supports_feature`)
2. Uses Claude Agent SDK for full hook and tool support
3. Uses SDK for OpenAI, shell-out for others
4. Degrades gracefully when features aren't available
5. Preserves backward compatibility via `--harness claude-legacy`

## Requirements

### P0 - Must Have

- **Core Harness interface** - Abstract base class with `run_task()`, `stream_task()`, `supports_feature()` methods
- **Claude SDK harness** - Full implementation using Claude Agent SDK with hooks, custom tools, and complete feature set
- **OpenAI SDK harness** - SDK-based implementation with basic completion support
- **Generic shell-out harness** - Fallback for Gemini, local models, and any CLI
- **Async-only API** - All harness methods are async; callers must update
- **Feature detection** - Runtime `supports_feature()` query for capabilities
- **SDK fallback** - If Claude SDK fails, automatically fall back to shell-out

### P1 - Should Have

- **Hook system** - PRE_TASK, POST_TASK, PRE_TOOL_USE, POST_TOOL_USE, ON_ERROR, ON_MESSAGE hooks
- **Custom MCP tool registration** - For harnesses that support it (Claude)
- **Token/cost tracking** - Include usage in TaskResult.metadata
- **Legacy flag** - `--harness claude-legacy` for shell-out during transition period

### P2 - Nice to Have

- **Gemini SDK harness** - If Gemini SDK becomes available, use it instead of shell-out
- **Session management** - create_session(), fork_session() for Claude
- **HarnessSelector** - Automatic provider selection based on task requirements

## Constraints

- Must use Claude Agent SDK for the Claude harness (primary constraint)
- Async-only API (no sync wrappers for backwards compatibility)
- Breaking changes acceptable (this is a major version change)
- `--harness claude-legacy` available during transition for users who need shell-out behavior

## Assumptions

- Claude Agent SDK is stable enough for production use
- OpenAI SDK provides sufficient functionality (even without full agent loop)
- Users accept that non-Claude providers will have fewer features
- Hook system overhead is negligible compared to LLM latency
- Existing cub callers can be updated to async without major issues

## Open Questions / Experiments

| Unknown | Experiment |
|---------|------------|
| Is Claude SDK production-ready? | Try SDK first, implement fallback to shell-out if issues arise |
| Will users understand feature fragmentation? | Document feature matrix per provider clearly in README |
| Is async migration disruptive? | Audit affected call sites before implementing; measure scope |
| What errors are retryable vs fatal? | Define error taxonomy during implementation |

## Out of Scope

- Perfect feature parity across providers (explicitly accepted)
- Supporting every possible LLM (start with top 4: Claude, OpenAI, Gemini, local)
- Building SDKs or agent wrappers for providers that don't have them
- Complex dependency resolution between harnesses
- Multi-tenant API key management

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Claude SDK has bugs or missing features | High | Fallback to shell-out via `--harness claude-legacy` |
| Feature fragmentation confuses users | Medium | Clear documentation with feature matrix per provider |
| Async migration breaks existing callers | Medium | Phased migration; audit call sites first |
| OpenAI/Gemini harnesses feel incomplete | Low | Set expectations in docs; Claude is the primary harness |
| Hook execution slows down task execution | Low | Measure overhead; hooks are async and non-blocking |

## MVP Definition

Full abstraction layer with:
- 4 providers (Claude SDK, OpenAI SDK, Gemini shell-out, local shell-out)
- Async-only interface
- Hook system for Claude (PRE_TASK, POST_TASK, PRE_TOOL_USE, ON_ERROR, ON_MESSAGE)
- Feature detection via `supports_feature()`
- `--harness claude-legacy` fallback during transition

## Related Specs

This feature blocks several downstream specs:
- `multi-model-review.md` - Requires harness abstraction to run multiple providers
- `tools-registry.md` - Custom tools registered via harness
- `workflow-management.md` - Workflows use harness abstraction
- `toolsmith.md` - Tool discovery needs harness feature detection

---

**Next Step:** Run `cub architect` to proceed to technical design.

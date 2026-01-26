# Cub — Product Thesis (draft)

## One-sentence promise (working)
Cub helps **solo builders** who already use AI coding harnesses make **solid, confidence-building progress** by turning fuzzy intent into **PR-ready changes** without getting trapped in **LLM thrash**.

## Who Cub is for
- **Solo builders** shipping real software.
- Already using one or more AI coding harnesses (Codex/Claude Code/Cursor/Aider/etc.).
- Comfortable enough to operate in a repo, but not necessarily power-CLI users.
- They want to use AI for leverage, but they’re running into reliability, drift, and review/correctness bottlenecks.

## Who Cub is *not* for (non-goals)
- People who want a fully autonomous, unsupervised coding bot.
- Teams that primarily need Jira-style coordination rather than quality/traceability.
- Users who don’t want repo-local artifacts (Cub assumes “the repo is the project memory”).

## Day-0 trigger (why they try Cub)
They feel **overwhelmed keeping agents fed with work** and managing all the moving parts:
- Product complexity balloons faster than they can keep a coherent plan in their head.
- Agents finish quickly, producing lots of code—but not always the right code.
- Manual review becomes a bottleneck and a source of anxiety.

## The “never again” pitfall Cub targets
**LLM thrash:** repeated cycles where the model redoes/undoes work over time, leaving other components broken and the user unsure what’s true anymore.

Common thrash modes (to design against):
- Requirement/spec drift and “interpretation creep.”
- Partial implementations and placeholders that accumulate.
- Regressions caused by local fixes that break adjacent areas.
- Tests being “made to pass” rather than validating behavior.
- Context loss across sessions (the agent forgets what it decided yesterday).
- Overengineering/reinventing wheels in the name of robustness.

## The v1 “win”: one confident change
In a short working session, Cub should reliably help the user produce **one solid piece of progress** (size-independent) that feels safe to move forward with—ideally to a **PR-ready** state.

**“Confidence” signals (candidates):**
- Clear written intent (what/why) attached to the change.
- A bounded plan (what will change + what won’t).
- A reviewable diff with a human-readable change summary.
- Automated checks (tests/lint/build) + a report.
- Regression surface area called out (files, modules, APIs touched).
- Traceability: link from intent → tasks → commits → outputs.

## Core product stance
Cub is not primarily a faster code generator; it’s the **workflow + artifact layer** that reduces entropy at the beginning and end of AI-assisted development so the builder can keep moving forward.

## Messaging hooks (rough)
- “Stop babysitting agents. Start shipping.”
- “From fuzzy intent to PR-ready—with receipts.”
- “Make one confident change at a time.”
- “Less thrash, more progress.”

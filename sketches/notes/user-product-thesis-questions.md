# Cub — User/Product Thesis (working notes)

## Target user (current articulation)
- Someone who is **conversant with AI coding** (agentic coding tools / LLM-assisted dev).
- Often comfortable with **CLIs**, but not necessarily.
- They are **struggling with the pitfalls** of AI-assisted development.
- They want help especially at the **beginning** (idea/spec/planning) and **end** (assessment/review/ship/maintain) of the process.

## “Pitfalls” to explicitly name (prompt for discussion)
- Spec/intent drift; incomplete implementation; placeholders.
- Hidden regressions; brittle tests; test-was-made-to-pass.
- Overengineering / reinventing wheels.
- Lack of traceability: why a change was made, what assumptions were used.
- Cost/runaway loops: token/time budget surprises.
- Messy artifacts: scattered notes, prompts, partial plans.
- Low confidence to ship: review burden, uncertainty, fear of breaking things.

## Value proposition (hypothesis)
Cub is the **workflow+artifact layer** that makes AI-assisted product development:
- More **predictable** (reliability + guardrails)
- More **economical** (budgets + routing)
- More **traceable/observable** (end-to-end provenance)
- Better at the **front-end** (clarifying what to build) and **back-end** (knowing what you built, verifying it, shipping it)

## Foundational questions to answer (product thesis)
1. What is the user’s *moment of pain* that triggers trying Cub? (the “day 0” story)
2. What is the *first 15 minutes* win Cub delivers?
3. What does success look like after 1 week of use? After 1 month?
4. Which parts of the lifecycle are must-have for v1 (beginning/end), and what is explicitly out of scope?
5. What does Cub do that a coding agent harness + good discipline *does not*?
6. What are the key trust builders? (sandboxing, budgets, traceability, review aids, etc.)
7. What is Cub’s “shape” in the user’s head: product manager, release engineer, copilot, build system, or ledger?

## Lighthouse users (discovery hypothesis)
- There are active **Twitter/X** and **Reddit** users of adjacent products/tools who can function as lighthouse users.
- Goal: find users who (a) build with agents regularly, (b) have scars/pitfalls, (c) want a more structured workflow.

## Discovery plan (lightweight)
- Identify 15–30 candidate lighthouse users across X + Reddit.
- For each: capture handle/link, tool stack, recurring pain points, notable quotes.
- Synthesize 5–7 common pain themes and 3–4 user archetypes.
- Use themes to tighten Cub’s v1 scope + messaging.

## Next: questions for Marc
- Which agentic coding tools are they likely already using? (Claude Code, Codex, Cursor, Aider, etc.)
- What is the single most common pitfall you want Cub to prevent?
- When does Cub “enter” the workflow: before any code is written, or once the repo exists?
- Are we aiming at solo builders first, or small teams?

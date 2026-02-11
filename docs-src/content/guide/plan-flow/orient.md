# Orient Stage

Orient is the first stage of the plan flow. It ensures product clarity before any technical work begins by refining requirements, identifying gaps, and producing a clear specification that the Architect can work from.

## What Orient Does

The orient stage:

- Reviews your vision document (or gathers requirements through interview)
- Identifies gaps, ambiguities, and unstated assumptions
- Challenges unclear requirements
- Produces a prioritized requirements document

```mermaid
flowchart LR
    A[Vision/Idea] --> B[Orient Agent]
    B --> C{Gaps Found?}
    C -->|Yes| D[Clarifying Questions]
    D --> B
    C -->|No| E[orientation.md]

    style A fill:#FFC107
    style E fill:#4CAF50,color:white
```

## Running Orient

### Interactive Mode (Recommended)

Start a new orient session:

```bash
cub plan orient
```

This launches Claude Code with the orient skill, which conducts an interactive interview to refine your requirements.

### Non-Interactive Mode

For automated workflows:

```bash
cub plan orient --non-interactive --vision VISION.md
```

!!! warning "Best-Effort"
    Non-interactive mode makes assumptions when details are missing. The output may include a "Needs Human Input" section with blocking questions.

## The Orient Interview

The orient agent asks these key questions:

### Question 1: Orient Depth

> How thorough should this product review be?
>
> - **Light**: Quick coherence check (~5 min)
> - **Standard**: Full product review (~15 min)
> - **Deep**: Include market/feasibility analysis (~30 min)

### Question 2: Core Problem

> In one sentence, what problem does this solve? Who has this problem?

### Question 3: Success Criteria

> How will you know this project succeeded? What's the measurable outcome?

### Question 4: Constraints

> Are there any hard constraints? (timeline, budget, tech stack, regulations)

### Question 5: MVP Definition

> What's the MVP - the smallest thing that would be useful?

### Question 6: Concerns

> What are you most worried about or uncertain about?

## Gap Analysis

Based on the orient depth, the agent analyzes your vision for:

### Light Orient
- Is there a clear problem statement?
- Is there enough detail to start building?
- Are there obvious contradictions?

### Standard Orient (includes Light)
- **Completeness**: Missing user stories, edge cases, error handling
- **Clarity**: Ambiguous terms that could mean multiple things
- **Assumptions**: Unstated assumptions
- **Dependencies**: External factors the project relies on
- **Risks**: What could go wrong

### Deep Orient (includes Standard)
- **Desirability**: Is there evidence users want this?
- **Feasibility**: Can this be built with reasonable effort?
- **Viability**: Should this be built? Opportunity cost?
- **Competition**: What else exists? How is this different?

## Positioning Unknowns

For things that can't be answered upfront, orient frames them as experiments:

> "We don't know if users will prefer X or Y. We can build this as an A/B test and let data decide."

This keeps the project moving while acknowledging uncertainty.

## Output: orientation.md

Orient produces a structured requirements document:

```markdown
# Orientation Report: {Project Name}

**Date:** 2026-01-17
**Orient Depth:** standard
**Status:** Approved

---

## Executive Summary

Brief summary of what we're building and why.

## Problem Statement

Clear articulation of the problem being solved and who has it.

## Refined Vision

Unambiguous statement of what will be built.

## Requirements

### P0 - Must Have
- Requirement with rationale

### P1 - Should Have
- Requirement with rationale

### P2 - Nice to Have
- Requirement with rationale

## Constraints

- Timeline constraint and impact
- Technical constraint and impact

## Assumptions

- Assumption we're proceeding with

## Open Questions / Experiments

- Unknown -> Experiment: how we'll learn

## Out of Scope

- Explicitly excluded item

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Risk description | H/M/L | Strategy |

## MVP Definition

The smallest useful thing we can build.

---

**Next Step:** Run `cub plan architect` to proceed to technical design.
```

## Vision Document Discovery

Orient looks for vision documents in this order:

1. **Explicit path**: `cub plan orient --vision path/to/doc.md`
2. **VISION.md**: In project root
3. **docs/PRD.md**: Product requirements document
4. **README.md**: Fallback

If no document is found, the orient agent will ask you to describe your idea.

## Example Orient Session

```
$ cub plan orient

Starting orient...

[Claude Code launches with /cub:orient skill]

Orient Agent: I found VISION.md in your project root.
Let me ask a few questions to refine the requirements...

How thorough should this product review be?
- Light: Quick coherence check (~5 min)
- Standard: Full product review (~15 min)
- Deep: Include market/feasibility analysis (~30 min)

> standard

In one sentence, what problem does this solve?

> Users can't easily track their daily habits across devices.

How will you know this project succeeded?

> 1000 daily active users within 3 months of launch.

[... more questions ...]

Here's the orientation report. Please review:

[Shows orientation.md content]

Reply with:
- approved to save and proceed
- revise: [feedback] to make changes

> approved

Orient complete!
Output saved to: plans/myproject/orientation.md

Next step: cub plan architect
```

## Handling "Needs Human Input"

If orient cannot proceed without critical information, it marks the output as needing human input:

```
Orient needs human input before continuing.
Output: plans/myproject/orientation.md

## Needs Human Input

1. What authentication method should be used? (OAuth, email/password, magic links)
2. Is there a specific database requirement?
3. What's the target deployment environment?
```

Answer these questions in the orientation.md file or re-run orient to provide the answers interactively.

## CLI Reference

```
Usage: cub plan orient [OPTIONS]

Stage 1: Requirements Refinement

Options:
  --vision PATH        Vision/input markdown file
  --non-interactive    Run without interactive Claude session
  -h, --help           Show this help message

Examples:
  cub plan orient                      # Start new orient
  cub plan orient --vision VISION.md   # Use specific vision file

Output:
  plans/{slug}/orientation.md
```

## Principles

!!! tip "Push Back Constructively"
    Orient's job is to make the vision clearer, not rubber-stamp it.

!!! tip "Ask Why"
    Surface assumptions by asking why things need to be a certain way.

!!! tip "Be Direct"
    If something is unclear or missing, say so plainly.

!!! tip "Frame, Don't Block"
    Position unknowns as experiments rather than blockers.

!!! tip "Stay Product-Focused"
    Technical concerns belong to the Architect phase.

## Next Step

Once orient is complete, proceed to technical design:

```bash
cub plan architect
```

[:octicons-arrow-right-24: Architect Stage](architect.md)

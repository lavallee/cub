# Spec Template

Use this template for all spec files. Frontmatter tracks state and readiness.

## Frontmatter Schema

```yaml
---
status: draft | ready | in-progress | partial | complete | archived
priority: low | medium | high | critical
complexity: low | medium | high
dependencies: []              # List of other specs or systems this depends on
blocks: []                    # List of specs or work this blocks
created: YYYY-MM-DD
updated: YYYY-MM-DD
readiness:
  score: 0-10                 # 0 = many unknowns, 10 = ready to implement
  blockers:                   # What's stopping this from being "ready"?
    - blocker description
  questions:                  # Open questions that need answers
    - question text
  decisions_needed:           # Key decisions that need to be made
    - decision description
  tools_needed:               # Tools we wish we had to answer questions
    - tool description
---
```

### Status Values

- **draft** - Initial thinking, not fully formed
- **ready** - All questions answered, ready to implement
- **in-progress** - Implementation has started
- **partial** - Partially implemented
- **complete** - Fully implemented
- **archived** - No longer relevant or superseded

### Readiness Score Guide

- **0-3**: Many unknowns, major questions unanswered
- **4-6**: Core concept solid, some implementation details unclear
- **7-8**: Most questions answered, minor details remain
- **9-10**: Ready to implement, all decisions made

## Spec Structure

After frontmatter, use this general structure:

```markdown
# Spec Title

## Overview
Brief summary (2-3 sentences)

## Goals
What this achieves

## Non-Goals
What this explicitly doesn't do

## Design / Approach
How it works

## Implementation Notes
Technical details, structure, etc

## Open Questions
(duplicates from frontmatter for visibility in the doc)

## Future Considerations
Things to consider later but out of scope now

---

**Status**: [from frontmatter]
**Last Updated**: [from frontmatter]
```

## Usage

When creating or updating specs:

1. **Add frontmatter** if missing
2. **Update status** based on implementation state
3. **Score readiness** honestly - what don't we know?
4. **List blockers** - what's preventing progress?
5. **Identify questions** - what needs to be answered?
6. **Note decisions needed** - what choices must be made?
7. **Wish for tools** - what tools would help answer questions?

The goal: Make it obvious what's blocking a spec from being actionable.

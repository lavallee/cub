---
status: researching
priority: medium
complexity: high
dependencies:
- ledger-consolidation-and-id-system
blocks: []
created: 2026-02-04
updated: 2026-02-04
readiness:
  score: 4
  blockers:
  - Requires ledger consolidation spec to be implemented first
  questions:
  - Which embedding model balances quality vs speed for code/technical content?
  - What's the right threshold for promoting a lesson to agent.md?
  - Should knowledge decay over time as codebases evolve?
  - Can knowledge transfer across projects?
  - How do we handle contradictory lessons from different contexts?
  decisions_needed:
  - Storage format for knowledge graph (SQLite vs graph DB vs hybrid)
  - Human-in-loop vs fully automatic instruction updates
  tools_needed:
  - Sentence transformer or embedding API
spec_id: cub-049
---
# Knowledge System (Self-Improving Agent)

## Overview

Cub accumulates valuable knowledge during task execution—decisions, lessons learned, successful approaches—that currently sits dormant in ledger entries. This spec transforms cub from a "set and forget" task runner into a self-improving agent that remembers past experience, surfaces relevant knowledge for new tasks, and automatically evolves its own instructions based on patterns.

## Goals

- Build a queryable knowledge graph from ledger data (decisions, lessons, approaches)
- Auto-inject relevant past experience into system prompts for new tasks
- Detect patterns (anti-patterns and success patterns) across task history
- Automatically suggest updates to agent.md based on repeated lessons
- Provide predictive estimation based on historical data (`cub estimate`)

## Non-Goals

- Real-time collaboration or shared knowledge bases
- Integration with external knowledge management tools (Notion, Obsidian)
- Replacing human judgment on architectural decisions
- Building a general-purpose AI knowledge system

## Design / Approach

### Knowledge Graph Entities

- **Decision**: Architectural or implementation choice made during a task
- **Lesson**: Something learned (positive or negative outcome)
- **Approach**: Strategy that succeeded for a problem type
- **Pattern**: Recurring combination of decisions/approaches

### Context-Aware Prompting

When starting a task, query knowledge store for:
- Tasks with similar title/description (embedding similarity)
- Tasks with shared labels/technologies
- Tasks in same epic/spec lineage

Inject relevant lessons as a "Lessons from Related Work" section in the prompt.

### Self-Improving Instructions

Trigger conditions for agent.md updates:
- Same lesson appears 3+ times → candidate for convention
- Decision with high success rate across tasks → candidate for recipe
- Approach that always fails → candidate for anti-pattern warning

Present candidates to human for approval (or auto-apply with flag).

## Implementation Notes

### Phase 1: Knowledge Extraction
- Parse `decisions`, `lessons_learned`, `approach` from ledger entries
- Classify by type using LLM
- Store in `.cub/knowledge/entities.jsonl`

### Phase 2: Knowledge Store
- SQLite schema for entities and relationships
- Optional vector embeddings for semantic search
- Sync via JSONL export to git

### Phase 3: Query System
- Similarity search for relevant knowledge
- Pattern detection queries
- CLI: `cub knowledge search`, `cub knowledge patterns`

### Phase 4: Prompt Injection
- Pre-session hook queries knowledge store
- Format relevant entries as markdown
- Inject into system prompt

### Phase 5: Self-Improvement
- Candidate detection from repeated patterns
- Update generation with provenance tracking
- Human review flow: `cub learn suggest`, `cub learn apply`

## Open Questions

1. Which embedding model balances quality vs speed for code/technical content?
2. What's the right threshold for promoting a lesson to agent.md? 3 occurrences? 5?
3. Should knowledge decay over time as codebases evolve?
4. Can knowledge transfer across projects? A lesson about "always test edge cases" applies everywhere.
5. How do we handle contradictory lessons from different contexts?

## Future Considerations

- Federated knowledge sharing across team members
- Integration with code review feedback loops
- Predictive task assignment based on developer strengths
- Natural language querying of knowledge base

---

**Status**: researching
**Last Updated**: 2026-02-04

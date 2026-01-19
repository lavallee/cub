# Repo as Workbench: Co-locating Constitution, Intentions, and Failures

## Intent

Cub should treat a repo as more than “code + README.” For agentic work (and humans working with agents), the repo should co-locate durable context and operational learning so:

- Agents have the **right defaults** (principles, constraints, preferences).
- Humans can see **why** something exists (intentions, tradeoffs).
- The system learns from **failures** (postmortems, sharp edges, gotchas).

This is aligned with the idea that code is becoming abundant; **good constraints and context** become the scarce resource.

## Design principles

- **Co-located**: stored in-repo, versioned with the project.
- **Layered durability**: separate docs by how fast they rot.
- **Small surface area**: a few canonical files beats many random docs.
- **Machine-readable enough**: light structure helps agents (frontmatter, sections).

## Proposed top-level “constitution set”

These should be small and stable. They are not per-feature specs.

- `CONSTITUTION.md`
  - product principles, non-negotiables, “how we decide”
  - threat model / safety posture (if relevant)

- `INTENTIONS.md`
  - near-term direction and current bets
  - what we are *not* doing right now

- `FAILURES.md`
  - recurring mistakes, sharp edges, regressions
  - “what we learned the hard way”

Optional if needed:
- `DECISIONS/` (or `specs/decisions/`)
  - short ADR-like records for major choices

## Proposed `specs/` layout (extends current Cub conventions)

Cub already has:
- `specs/features/`
- `specs/roadmap/`
- `specs/research/`
- `specs/investigations/`
- `specs/notes/`

Add:
- `specs/constitution/` (if we don’t want top-level files)
- `specs/decisions/` (small, linkable decision records)
- `specs/workbench/`
  - `sessions/` (workbench session state)
  - `frames/`, `maps/`, `tests/` (optional subfolders later)

## Aging / rot model (why PRD-first fails)

A PRD mixes:
- durable: principles, constraints, definitions
- medium-lived: problem framing, decision rationale
- short-lived: acceptance criteria, task decomposition

Those pieces should not be forced into one document lifecycle. Separate storage locations let agents update volatile parts without rewriting the constitution.

## Linking

Any artifact should support lightweight links (frontmatter `links:`) to build an “idea graph.”
This enables:
- a decision to point to evidence
- a task brief to point to a decision + frame
- failures to link back to the originating change

## Recommendation

Start with top-level files (`CONSTITUTION.md`, `INTENTIONS.md`, `FAILURES.md`) because they are:
- obvious to humans
- easy for agents to discover
- low ceremony

If they become noisy, migrate into `specs/constitution/` and keep the top-level files as short pointers.

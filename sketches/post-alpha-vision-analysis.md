# Cub: Post-Alpha Vision Analysis

**Purpose:** Map the full vision (from rationale doc + specs) against what's built, identify gaps, and organize the roadmap beyond 0.30.

---

## The Full Lifecycle Cub Aspires To Cover

From the rationale doc and various specs, Cub aspires to be useful across the **entire product development lifecycle**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        THE CUB LIFECYCLE VISION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  IDEATION        SHAPING         PLANNING        EXECUTION       HARVEST   │
│  ─────────       ───────         ────────        ─────────       ───────   │
│                                                                             │
│  • Capture       • Frame         • Orient        • Run loop      • Review  │
│  • Investigate   • Map options   • Architect     • Verify        • Learn   │
│  • Research      • Test/spike    • Itemize       • Commit        • Ship    │
│  • Audit         • Shape         • Stage         • PR            • Retro   │
│                  • Commit/hold                                             │
│                                                                             │
│  ◀──────────────── PM Multitool ────────────────▶ ◀── Execution Engine ──▶ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Current Coverage Assessment

### What's Built and Working (Alpha)

| Lifecycle Stage | Feature | Status | Notes |
|-----------------|---------|--------|-------|
| **Ideation** | Capture command | ✅ Exists | Basic capture to file |
| **Ideation** | Investigate command | ✅ Exists | Routes to research/audit/spike/etc |
| **Shaping** | Orient/triage | ✅ Exists | Part of `cub plan` pipeline |
| **Planning** | Architect step | ✅ Exists | Part of `cub plan` pipeline |
| **Planning** | Itemize | ✅ Exists | Part of `cub plan` pipeline |
| **Planning** | Bootstrap/stage | ✅ Exists | Imports to task backend |
| **Execution** | Run loop | ✅ Exists | Core value prop |
| **Execution** | Multi-harness | ✅ Exists | Claude, Codex, Gemini, OpenCode |
| **Execution** | Budget/limits | ✅ Exists | Token + time + iteration limits |
| **Execution** | Git integration | ✅ Exists | Branching, commits |
| **Execution** | Hooks | ✅ Exists | 8 lifecycle points |
| **Harvest** | PR creation | ✅ Exists | `cub pr` command |
| **Harvest** | Artifact bundles | ✅ Exists | Per-task outputs |
| **Harvest** | JSONL logging | ✅ Exists | Structured logs |

### What's Spec'd But Not Built

| Lifecycle Stage | Feature | Spec | Gap |
|-----------------|---------|------|-----|
| **Shaping** | Frame artifact | pm-shaping-model.md | No `cub frame` command |
| **Shaping** | Map options (OST-style) | pm-shaping-model.md | No multi-path tracking |
| **Shaping** | Test/spike tracking | pm-shaping-model.md | Spikes don't link back |
| **Shaping** | Shape artifact | pm-shaping-model.md | No boundaries/appetite doc |
| **Shaping** | Unknowns ledger | pm-workbench.md | No explicit unknown tracking |
| **Execution** | Circuit breaker | circuit-breaker.md | Stagnation not detected |
| **Execution** | Receipt-based gating | receipt-based-gating.md | No evidence requirements |
| **Execution** | Sandbox mode | sandbox-mode.md | Not implemented |
| **Harvest** | Completed work ledger | knowledge-retention.md | Gap between run and git |
| **Harvest** | Runs analysis | runs-analysis.md | No aggregate analysis |
| **Harvest** | Self-learning | rationale doc | No auto-guardrail generation |

### What's Missing Entirely (Not Spec'd or Underspec'd)

| Lifecycle Stage | Gap | Impact | Notes |
|-----------------|-----|--------|-------|
| **Ideation** | Multi-source ingestion | Medium | Can't easily pull from Slack, email, meetings |
| **Ideation** | Idea graph / linking | High | Captures are isolated, not connected |
| **Shaping** | PM routing ("what next?") | High | No automatic suggestion of next move |
| **Shaping** | Assumption tracking | Medium | Implicit assumptions not surfaced |
| **Shaping** | Decision logging | Medium | Why did we choose X over Y? |
| **Shaping** | Appetite/scope negotiation | Medium | No explicit "how big is this?" |
| **Planning** | Dependency visualization | Low | Dependencies exist but not visualized |
| **Planning** | Envelope enforcement | High | Bounded change not enforced |
| **Execution** | Symbiotic mode | High | Direct harness work not captured |
| **Execution** | Re-anchoring | Medium | Context reset not automatic |
| **Harvest** | Drift detection | High | Spec vs implementation divergence |
| **Harvest** | Cost attribution | Medium | Can't see cost per feature/epic |
| **Harvest** | Retrospective synthesis | Low | No automated learnings extraction |
| **Cross-cutting** | Constitution/principles | Medium | Project-level constraints scattered |

---

## The Two Halves: PM Multitool vs Execution Engine

Your instinct is right: Cub has two major value propositions that need different treatment.

### The Execution Engine (Alpha Focus)

**What it is:** The run loop, harness orchestration, budget management, git workflow, artifact production.

**Current state:** Reasonably complete. Alpha is about hardening this.

**Value prop:** "Stop babysitting agents. Feed them well-structured tasks, let them run, get PR-ready output."

**Remaining gaps:**
- Circuit breaker (stagnation detection)
- Symbiotic workflow (direct harness capture)
- Envelope enforcement (bounded changes)
- Receipt-based gating (evidence requirements)

### The PM Multitool (Post-Alpha Focus)

**What it is:** Everything that happens *before* tasks exist—turning fuzzy ideas into bounded, executable work.

**Current state:** Foundations exist (capture, investigate, prep pipeline) but not coherent or powerful.

**Value prop:** "Cub helps you figure out *what* to build, not just *how* to build it."

**Major gaps:**

1. **No "What Next?" Engine**
   - The PM workbench/shaping model describes a system that continuously suggests the next most valuable move
   - Currently: user must know what command to run
   - Need: `cub next` or workbench mode that routes automatically

2. **No Unknowns Ledger**
   - Ideas have implicit blockers but they're not tracked explicitly
   - Need: explicit blocker categories (clarity, evidence, decision, dependency)
   - Need: ranked list of "what's preventing promotion?"

3. **No Idea Graph / Linking**
   - Captures, frames, tests, decisions are isolated files
   - No way to see: "this decision was based on this evidence from this test"
   - Need: `links:` frontmatter + visualization

4. **No Frame/Shape Artifacts**
   - The "Frame" (clarified question + constraints) doesn't exist as a first-class artifact
   - The "Shape" (boundaries, appetite, risks, no-gos) doesn't exist
   - These are the key pre-task artifacts that reduce thrash

5. **No Assumption Surfacing**
   - Implicit assumptions in specs are not extracted
   - No way to say "this plan assumes X, Y, Z—have we validated those?"

6. **No Decision Logging**
   - When we choose approach A over B, that rationale is lost
   - Later, agents (or humans) don't know why we're doing it this way

---

## Blind Spots Analysis

### Blind Spot 1: The Input Problem

**Symptom:** Cub assumes work starts from a well-formed idea or spec.

**Reality:** Work starts from:
- Slack messages from stakeholders
- Customer feedback emails
- Analytics dashboards showing problems
- Competitor feature launches
- Shower thoughts

**Gap:** No easy way to:
- Pull in external sources (Slack, email, Notion, etc.)
- Triage multiple inputs at once
- Batch-process a "pile of stuff" into coherent work

**Opportunity:** MCP connectors + `cub ingest` command that handles heterogeneous inputs.

### Blind Spot 2: The Validation Loop

**Symptom:** Cub helps you build things but doesn't help you know if they were the *right* things.

**Reality:** After shipping, you want to know:
- Did this feature get used?
- Did it solve the problem?
- What did we learn?

**Gap:** No:
- Outcome tracking (link feature to metrics)
- Hypothesis validation (we thought X, was it true?)
- Retrospective synthesis (what patterns emerge?)

**Opportunity:** `cub harvest` that pulls post-ship signals and updates the idea graph with evidence.

### Blind Spot 3: The Collaboration Model

**Symptom:** Cub is built for solo builders.

**Reality:** Even solo builders:
- Get input from stakeholders
- Need to explain decisions to others
- Want to share progress

**Gap:** No:
- Shareable state (beyond git)
- Stakeholder-friendly views
- "Here's what I'm working on and why" export

**Opportunity:** Not team workflow (out of scope), but better artifacts for communication.

### Blind Spot 4: The Drift Detection Problem

**Symptom:** Specs and code diverge silently.

**Reality:** After a few iterations:
- The original spec says one thing
- The code does something slightly different
- No one notices until much later

**Gap:** No:
- Spec-to-implementation comparison
- Automatic "does this still match intent?" check
- Acceptance criteria verification

**Opportunity:** `cub verify --against-spec` that uses an LLM to check alignment.

### Blind Spot 5: The "I Just Did Some Work" Problem

**Symptom:** Direct harness use (Claude Code, Cursor, etc.) bypasses Cub entirely.

**Reality:** Users will:
- Jump into Claude Code for a quick fix
- Use Cursor for exploration
- Make changes without going through cub run

**Gap:** No:
- Detection of out-of-band changes
- Way to associate manual work with tasks
- Artifact capture from non-cub sessions

**Opportunity:** `cub reconcile` + git hooks that detect non-cub commits.

### Blind Spot 6: The Cost Visibility Problem

**Symptom:** Token spend is logged but not actionable.

**Reality:** Users want to know:
- How much did this feature cost to build?
- Which tasks are burning tokens inefficiently?
- What's my projected spend for this epic?

**Gap:** No:
- Cost aggregation by epic/feature
- Cost projections
- Cost anomaly detection

**Opportunity:** `cub costs` dashboard with rollups and alerts.

---

## Proposed Feature Organization (Post-Alpha)

### Tier 1: Execution Hardening (0.31)

Complete the execution engine promise.

| Feature | Spec | Why Now |
|---------|------|---------|
| Circuit Breaker | circuit-breaker.md | Prevents wasted iterations |
| Symbiotic Workflow | (new) | Direct harness work captured |
| Envelope Enforcement | v1-scope.md | Anti-thrash core differentiator |
| Receipt-Based Gating | receipt-based-gating.md | Evidence before "done" |
| Drift Detection | (new) | Catch spec/impl divergence |

### Tier 2: PM Multitool Foundation (0.32)

Build the pre-task coherence layer.

| Feature | Spec | Why Now |
|---------|------|---------|
| Frame Artifact | pm-shaping-model.md | First-class "clarified question" |
| Unknowns Ledger | pm-workbench.md | Track what's blocking promotion |
| "What Next?" Routing | pm-workbench.md | Auto-suggest next move |
| Links/Idea Graph | pm-shaping-model.md | Connect captures → decisions → tasks |
| Decision Logging | (new) | Capture why we chose X over Y |

### Tier 3: Knowledge Compounding (0.33)

Make Cub smarter over time.

| Feature | Spec | Why Now |
|---------|------|---------|
| Completed Work Ledger | knowledge-retention.md | Bridge run → git gap |
| Runs Analysis | runs-analysis.md | Patterns across runs |
| Auto-Guardrails | rationale doc (self-learning) | Learn from failures |
| Cost Attribution | (new) | Cost per epic/feature |

### Tier 4: Input/Output Expansion (0.34+)

Broader integration.

| Feature | Spec | Why Now |
|---------|------|---------|
| Multi-Source Ingestion | (new) | Slack, email, Notion → captures |
| Harvest/Validation Loop | (new) | Post-ship outcome tracking |
| Shareable Artifacts | (new) | Export for stakeholders |
| Codebase Health Audit | codebase-health-audit.md | Ongoing hygiene |

---

## The PM Multitool: A Deeper Dive

Since you called this out, here's a more detailed breakdown of what the PM multitool needs to be truly useful.

### Core Concept: The Unknowns-Driven Workflow

The key insight from the PM shaping model is that **work advances by reducing unknowns**, not by filling out templates.

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNKNOWNS-DRIVEN WORKFLOW                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INPUT              UNKNOWNS LEDGER           OUTPUT            │
│  ─────              ───────────────           ──────            │
│                                                                 │
│  • Captures    ──▶  • Clarity gaps       ──▶  • Questions       │
│  • Docs             • Evidence gaps           • Research briefs │
│  • Feedback         • Decision gaps           • Spike plans     │
│  • Ideas            • Dependency gaps         • Shape docs      │
│                                               • TaskBriefs      │
│                                                                 │
│         ▲                   │                       │           │
│         │                   ▼                       │           │
│         │            "WHAT NEXT?"                   │           │
│         │         ───────────────                   │           │
│         │                                           │           │
│         │     System proposes next move:            │           │
│         │     • Ask X (clarify)                     │           │
│         │     • Check Y (test)                      │           │
│         │     • Choose A/B (decide)                 │           │
│         │     • Promote now (execute)               │           │
│         │                                           │           │
│         └───────────────────────────────────────────┘           │
│                         (loop until promotion)                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Required Components

1. **Unknown Types** (the taxonomy)
   - `clarity`: missing context, ambiguous scope
   - `evidence`: needs validation/research
   - `decision`: multiple paths, need to choose
   - `dependency`: blocked on external factors

2. **Artifacts** (the outputs)
   - `Capture`: raw signal (exists)
   - `Frame`: clarified question + constraints (new)
   - `Test`: hypothesis + method + expected signal (new)
   - `Evidence`: what we learned (new)
   - `Shape`: boundaries, appetite, risks, no-gos (new)
   - `Decision`: choice made + rationale (new)
   - `TaskBrief`: execution-ready plan (exists, but not linked)

3. **Routing Engine** (the "what next?" logic)
   - Input: current unknowns + their scores
   - Output: single recommended action
   - Types: ask, research, audit, spike, promote

4. **Links** (the connective tissue)
   - `refines`: Capture → Frame
   - `supports`: Evidence → Decision
   - `tests`: Test → Assumption
   - `promotes_to`: Decision → TaskBrief

### MVP Implementation Path

**Phase 1: Add Unknown Tracking to Captures**
```yaml
# In capture frontmatter
blockers:
  - type: clarity
    description: "What user segment is affected?"
  - type: decision
    description: "Should we optimize for speed or completeness?"
```

**Phase 2: Add `cub next` Command**
- Scans captures for blockers
- Ranks by severity/age
- Proposes: "Your top unknown is X. Recommended action: Y."

**Phase 3: Add Frame/Shape Generators**
- `cub frame <capture>` → generates Frame artifact with clarifying questions
- `cub shape <frame>` → generates Shape artifact with boundaries/appetite

**Phase 4: Add Links and Visualization**
- Frontmatter `links:` support
- `cub graph <epic>` → shows idea graph as mermaid/ASCII

---

## Missing Pieces Summary

| Category | Gap | Priority | Effort |
|----------|-----|----------|--------|
| **PM Multitool** | No "what next?" routing | High | Medium |
| **PM Multitool** | No unknowns ledger | High | Low |
| **PM Multitool** | No Frame artifact | Medium | Low |
| **PM Multitool** | No Shape artifact | Medium | Low |
| **PM Multitool** | No decision logging | Medium | Low |
| **PM Multitool** | No idea graph/links | Medium | Medium |
| **Execution** | No symbiotic workflow | High | Medium |
| **Execution** | No envelope enforcement | High | Medium |
| **Execution** | No drift detection | High | Medium |
| **Harvest** | No completed work ledger | Medium | High |
| **Harvest** | No cost attribution | Medium | Medium |
| **Harvest** | No outcome tracking | Low | High |
| **Input** | No multi-source ingestion | Low | High |
| **Cross-cutting** | No assumption surfacing | Medium | Medium |

---

## Recommendations

1. **For 0.30 (Alpha):** Stay focused on execution hardening. Ship what works.

2. **For 0.31:** Add circuit breaker + symbiotic workflow + envelope enforcement. These complete the "anti-thrash" story.

3. **For 0.32:** Build the PM multitool foundation:
   - Unknown tracking in captures
   - `cub next` routing command
   - Frame + Shape artifacts
   - Links in frontmatter

4. **For 0.33+:** Knowledge compounding and broader integration.

5. **Ongoing:** Document the PM workflow clearly. The mental model (unknowns-driven, not template-driven) is as important as the features.

---

## Open Questions

1. **How much PM tooling is "Cub" vs a separate product?**
   - Risk: Cub becomes too big, unfocused
   - Opportunity: Single tool for "idea to shipped code"

2. **Should the PM multitool have a separate UI?**
   - CLI works for execution
   - PM work might benefit from visual (kanban, graph)

3. **How to handle multi-project/portfolio view?**
   - Cub is repo-centric
   - PMs often work across multiple projects

4. **Integration vs. native implementation?**
   - Could integrate with Linear/Notion/etc. for PM
   - Or build native, repo-local PM artifacts

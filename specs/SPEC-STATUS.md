# Spec Status Overview

Summary of all specs, their current state, and what needs to happen to make them actionable.

Generated: 2026-01-19

---

## Summary Stats

- **Total specs:** 38
- **Complete:** ~8
- **Partial:** ~6
- **Ready (not started):** ~4
- **Draft (needs work):** ~20

---

## By Category

### Features (In Cub Repo)

| Spec | Status | Readiness | Notes |
|------|--------|-----------|-------|
| `capture.md` | **partial** | 7/10 | Core implemented, imports/organize pending. Needs URL capture, promotion features. |
| `capture-workflow.md` | **draft** | 4/10 | Depends on capture being complete. Needs workflow engine. |
| `investigate-command.md` | **complete** | 10/10 | Implemented and working. |
| `pm-workbench.md` | **draft** | 3/10 | Vision doc. Needs breaking down into smaller specs. |

### Investigations (Research Reports)

These are outputs of `cub investigate`, not specs to implement:

- `cap-001-research.md` - Research on parallel clones
- `cap-b04hr9-research.md` - Research artifact
- `cap-e14fu7-design.md` - Design artifact
- `cap-lvu73k-audit.md` - Audit artifact
- `cap-v7b6ly-research.md` - Research artifact

**Action:** No changes needed. These are artifacts, not specs.

---

### Research (Strategic/Exploratory)

| Spec | Status | Readiness | Notes |
|------|--------|-----------|-------|
| `ai-assisted-pm-shaping-model.md` | **draft** | 5/10 | Strong conceptual model. Needs operationalization into specific features. |
| `external-tools-analysis.md` | **draft** | N/A | Analysis doc, not implementation spec. |

---

### Roadmap (Planned Features)

#### High Priority / Quick Wins

| Spec | Status | Readiness | Needs |
|------|--------|-----------|-------|
| `guardrails-system.md` | **ready** | 9/10 | Ready to implement. Clear design from Ralph. |
| `circuit-breaker.md` | **ready** | 8/10 | Clear pattern. Needs thresholds defined. |
| `receipt-based-gating.md` | **ready** | 8/10 | Similar to guardrails, straightforward. |
| `fresh-context-mode.md` | **draft** | 6/10 | Concept clear. Needs implementation approach. |

**Recommended:** Start with guardrails, circuit-breaker, receipt-based-gating.

#### Medium Priority

| Spec | Status | Readiness | Needs |
|------|--------|-----------|-------|
| `advanced-error-detection.md` | **draft** | 5/10 | Needs error taxonomy. What patterns to detect? |
| `dual-condition-exit.md` | **draft** | 6/10 | Simple concept. Needs config format. |
| `implementation-review.md` | **draft** | 6/10 | Process spec. Needs workflow definition. |
| `interview-mode.md` | **draft** | 5/10 | Interaction design needed. What questions to ask? |
| `multi-model-review.md` | **draft** | 4/10 | Depends on harness abstraction. Needs review protocol. |
| `plan-review.md` | **draft** | 6/10 | Process spec. Needs review criteria. |
| `re-anchoring.md` | **draft** | 5/10 | Concept clear. Needs trigger conditions. |
| `runs-analysis.md` | **draft** | 6/10 | Needs metrics definition. What to analyze? |
| `sandbox-mode.md` | **draft** | 7/10 | Docker-based. Implementation path clear. |

#### Lower Priority / Bigger Efforts

| Spec | Status | Readiness | Needs |
|------|--------|-----------|-------|
| `codebase-health-audit.md` | **draft** | 4/10 | Needs health metrics definition. Integration with existing tools. |
| `language-migration.md` | **draft** | 3/10 | Large project. Needs phasing plan. |
| `live-dashboard.md` | **draft** | 5/10 | UI spec. Needs tech stack decision (TUI vs web). |
| `onboarding-and-organization.md` | **draft** | 6/10 | Documentation/process. Needs content writing. |
| `prd-import.md` | **draft** | 4/10 | Needs parser for various PRD formats. Template extraction. |
| `verification-integrations.md` | **draft** | 5/10 | Needs integration design per tool (pytest, jest, etc). |
| `vision-to-tasks-pipeline.md` | **draft** | 4/10 | Large feature. Overlaps with PM shaping model. Needs consolidation. |

---

## New Specs (Root Level)

| Spec | Status | Readiness | Notes |
|------|--------|-----------|-------|
| `specs/research/tools-registry.md` | **draft** | 6/10 | Created 2026-01-19. Needs format decisions. |
| `specs/research/workflow-management.md` | **draft** | 7/10 | Created 2026-01-19. Needs expression language choice. |

---

## Key Blockers Across Specs

### Architectural Decisions Needed

1. **Harness abstraction** - Many specs assume ability to swap LLM providers
   - Blocks: multi-model-review, tools-registry, workflow-management
   - **Tool needed:** Harness interface design validator

2. **Workflow engine** - Multiple specs need orchestration
   - Blocks: capture-workflow, interview-mode, pm-shaping implementation
   - **Tool needed:** Workflow simulator/validator

3. **State management** - How to persist agent state across sessions
   - Blocks: re-anchoring, fresh-context-mode, workflow-management
   - **Tool needed:** State schema designer

### Design Questions

4. **Error taxonomy** - What failure patterns should we detect?
   - Blocks: advanced-error-detection, circuit-breaker tuning
   - **Tool needed:** Error pattern analyzer (scan run logs for common failures)

5. **Metrics/observability** - What should we measure?
   - Blocks: runs-analysis, live-dashboard, codebase-health-audit
   - **Tool needed:** Metrics discovery tool (suggest what to track)

6. **Human handoff UX** - How to pause and ask for input?
   - Blocks: workflow-management, interview-mode, plan-review
   - **Tool needed:** UX prototyper for CLI/notifications

### Integration Points

7. **MCP protocol** - Need stable MCP integration
   - Blocks: tools-registry, verification-integrations
   - **Tool needed:** MCP discovery/test harness

8. **External tools** - Integration with pytest, jest, git, gh, etc
   - Blocks: verification-integrations, tools-registry
   - **Tool needed:** Tool capability mapper

---

## Recommended Next Steps

### Immediate (This Week)

1. **Add frontmatter to all roadmap specs** - Use SPEC-TEMPLATE.md
2. **Update existing specs with status/readiness scores**
3. **Implement quick wins:**
   - Guardrails system (clear spec, high value)
   - Circuit breaker (clear pattern)
   - Receipt-based gating (similar to guardrails)

### Short Term (Next 2 Weeks)

4. **Resolve harness abstraction** - Critical blocker
   - Design harness interface
   - Implement Claude harness
   - Add config for harness selection

5. **Build minimal workflow engine** - Unblocks many features
   - Start with simple sequential workflows (YAML)
   - Add conditional branching
   - Implement tool execution layer

6. **Define core metrics** - Needed for observability specs
   - What to track per run
   - Success/failure criteria
   - Performance indicators

### Medium Term (Next Month)

7. **Implement capture workflow** - Builds on capture feature
8. **Add interview mode** - Improves UX for ambiguous tasks
9. **Build runs analysis** - Uses metrics from #6

---

## Tools We Need (From Wishlist)

To move specs from draft → ready, we need:

**High Priority:**
- Complexity Estimator (scope specs realistically)
- Trade-off Analyzer (decide between approaches)
- Dependency Analyzer (understand spec relationships)
- Readiness Score Calculator (objective assessment)

**Medium Priority:**
- Technical Feasibility Checker (validate approaches)
- Risk Scorer (identify high-risk changes)
- Design Pattern Matcher (find proven solutions)

See `TOOLS-WISHLIST.md` for full list.

---

## Spec Health Issues

### Stale Specs
- `pm-workbench.md` - Too broad, needs breaking down
- `vision-to-tasks-pipeline.md` - Overlaps with PM shaping model

### Missing Specs
- Harness abstraction spec (critical dependency)
- Autonomy model spec (referenced but doesn't exist)
- MCP integration spec (assumed by tools-registry)

### Consolidation Needed
- `pm-workbench.md` + `ai-assisted-pm-shaping-model.md` + `vision-to-tasks-pipeline.md` - Similar concepts, should be unified

---

**Action Items:**

1. ✅ Create SPEC-TEMPLATE.md
2. ✅ Create TOOLS-WISHLIST.md  
3. ✅ Create SPEC-STATUS.md (this doc)
4. ⏳ Add frontmatter to all cub/specs/ files
5. ⏳ Create missing critical specs (harness abstraction, autonomy model, MCP integration)
6. ⏳ Consolidate overlapping specs
7. ⏳ Implement quick wins (guardrails, circuit-breaker)

---

**Related:** SPEC-TEMPLATE.md, TOOLS-WISHLIST.md

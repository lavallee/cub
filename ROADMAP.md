# Cub Roadmap

Comprehensive status of all features and specifications. Features marked complete have been moved to `specs/completed/`.

**Last Updated:** 2026-01-19

---

## Summary Stats

- **Completed:** 8 features
- **In Progress:** 1 feature  
- **Ready (Next):** 3 features
- **Planned:** 12 features
- **Research:** 7 features

---

## ✅ Completed

Features fully implemented and shipped. Specs moved to `specs/completed/`.

| Feature | Version | ID | Spec |
|---------|---------|-----|------|
| Guardrails System | 0.20 | [GS] | `completed/guardrails-system.md` |
| Live Dashboard (tmux) | 0.23 | [LD] | `completed/live-dashboard.md` |
| Vision-to-Tasks Pipeline | 0.14 | [VTP] | `completed/vision-to-tasks-pipeline.md` |
| Plan Review | 0.15 | [PR] | `completed/plan-review.md` |
| Interview Mode | 0.16 | [IM] | `completed/interview-mode.md` |
| PRD Import / Document Conversion | 0.17 | [PRD] | `completed/prd-import.md` |
| Onboarding & Project Organization | 0.18 | [OPO] | `completed/onboarding-and-organization.md` |
| Git Workflow Integration | 0.19 | [GWI] | `completed/git-workflow-integration.md` |

**Notes:**
- Guardrails: CLI + bash lib implemented, auto-learning pending
- Live Dashboard: `cub monitor` command working, tmux integration complete
- Interview: `cub interview` command implemented
- Import: `cub import` supports PRD and document formats

---

## 🚧 In Progress

Features currently being worked on.

| Feature | ID | Branch | Status | Spec |
|---------|-----|--------|--------|------|
| Language Migration (Go + Python) | [LM] | `feat/go-rewrite` | Active | `roadmap/language-migration.md` |

**Status:** Python CLI complete, bash delegation working, core modules migrated.

---

## 🎯 Ready (Next Priority)

Features ready to start, ordered by priority. All have clear specs and no blockers.

| Feature | ID | Complexity | Priority | Spec |
|---------|-----|------------|----------|------|
| Circuit Breaker / Stagnation Detection | [CB] | Medium | High | `roadmap/circuit-breaker.md` |
| Receipt-Based Gating | [RBG] | Low | High | `roadmap/receipt-based-gating.md` |
| Re-anchoring Mechanism | [RA] | Low | Medium | `roadmap/re-anchoring.md` |

**Quick wins:** Circuit-breaker and receipt-based gating are standalone, high-value features.

---

## 📋 Planned Features

Features with specs but not yet prioritized for immediate work.

### Quality & Reliability

| Feature | ID | Complexity | Spec |
|---------|-----|------------|------|
| Advanced Error Detection | [AED] | Medium | `roadmap/advanced-error-detection.md` |
| Dual-Condition Exit | [DCE] | Low | `roadmap/dual-condition-exit.md` |
| Fresh Context Mode | [FCM] | Medium | `roadmap/fresh-context-mode.md` |
| Implementation Review | [IR] | Medium | `roadmap/implementation-review.md` |
| Sandbox Mode | [SM] | High | `roadmap/sandbox-mode.md` |

**Blockers:**
- Advanced Error Detection: Needs error taxonomy definition
- Fresh Context Mode: Needs workflow integration
- Sandbox Mode: Requires Docker setup

### Tooling & Integration

| Feature | ID | Complexity | Spec |
|---------|-----|------------|------|
| Verification Integrations | [VI] | Medium | `roadmap/verification-integrations.md` |
| Multi-Model Review | [MMR] | Medium | `roadmap/multi-model-review.md` |
| Runs Analysis | [RunA] | Medium | `roadmap/runs-analysis.md` |

**Blockers:**
- Multi-Model Review: Depends on harness abstraction
- Runs Analysis: Needs metrics definition

### Project Management

| Feature | ID | Complexity | Spec |
|---------|-----|------------|------|
| Codebase Health Audit | [CHA] | Medium | `roadmap/codebase-health-audit.md` |

**Status:** Partial implementation exists (`cub audit` command), needs completion.

---

## 🔬 Research & Exploration

Features in research phase. Specs exist but need more design work before implementation.

### Core Infrastructure

| Feature | ID | Status | Spec |
|---------|-----|--------|------|
| Tools Registry | [TR] | Draft (6/10) | `research/tools-registry.md` |
| Workflow Management | [WM] | Draft (7/10) | `research/workflow-management.md` |
| AI-Assisted PM Shaping | [PMSH] | Draft (5/10) | `research/ai-assisted-pm-shaping-model.md` |

**Readiness:**
- Tools Registry: Needs format decisions, MCP integration design
- Workflow Management: Needs expression language choice, human handoff UX
- PM Shaping: Needs operationalization into specific features

### External Inspiration

| Feature | ID | Source | Spec |
|---------|-----|--------|------|
| Session Checkpointing | [SC] | Gas Town | `roadmap/session-checkpointing.md` |
| Team Knowledge Base | [TKB] | Compound | `roadmap/team-knowledge-base.md` |
| Agent Personas | [AP] | Gas Town | `roadmap/agent-personas.md` |
| Workflow Recipes | [WR] | Gas Town | `roadmap/workflow-recipes.md` |

See: `specs/research/external-tools-analysis.md` for analysis of Gas Town, Compound, and other tools.

---

## 🎨 Feature Capture

Active feature development pipeline.

| Feature | Status | Readiness | Spec |
|---------|--------|-----------|------|
| Capture System | Partial | 7/10 | `features/capture.md` |
| Capture Workflow | Draft | 4/10 | `features/capture-workflow.md` |
| Investigate Command | Complete | 10/10 | `features/investigate-command.md` |
| PM Workbench | Draft | 3/10 | `features/pm-workbench.md` |

**Status:**
- Capture: Core implemented, needs import/organize commands
- Investigate: Fully implemented, generates research/design/audit reports
- PM Workbench: Vision doc, needs breaking down into smaller features

---

## Key Blockers & Dependencies

### Architectural Decisions Needed

1. **Harness Abstraction** - Many specs assume ability to swap LLM providers
   - Blocks: Multi-Model Review, Tools Registry, Workflow Management
   - **Decision needed:** Define harness interface design

2. **Workflow Engine** - Multiple specs need orchestration
   - Blocks: Capture Workflow, Interview Mode enhancements, PM Shaping
   - **Decision needed:** Choose YAML vs Python, native vs Windmill/Temporal

3. **State Management** - How to persist agent state across sessions
   - Blocks: Re-anchoring, Fresh Context Mode, Workflow Management
   - **Decision needed:** File-based vs database, schema design

### Design Questions

4. **Error Taxonomy** - What failure patterns should we detect?
   - Blocks: Advanced Error Detection, Circuit Breaker tuning
   - **Tool needed:** Error pattern analyzer (scan run logs)

5. **Metrics/Observability** - What should we measure?
   - Blocks: Runs Analysis, Live Dashboard enhancements
   - **Tool needed:** Metrics discovery tool

6. **Human Handoff UX** - How to pause and ask for input?
   - Blocks: Workflow Management, Interview Mode, Plan Review enhancements
   - **Tool needed:** UX prototyper for CLI/notifications

### Integration Points

7. **MCP Protocol** - Need stable MCP integration
   - Blocks: Tools Registry, Verification Integrations
   - **Tool needed:** MCP discovery/test harness

8. **External Tools** - Integration with pytest, jest, git, gh, etc
   - Blocks: Verification Integrations, Tools Registry
   - **Tool needed:** Tool capability mapper

---

## Recommended Next Steps

### This Week

1. ✅ Add frontmatter to all specs
2. ✅ Move completed specs to `specs/completed/`
3. **Implement Circuit Breaker** - Clear spec, high value, standalone
4. **Implement Receipt-Based Gating** - Similar to guardrails, straightforward

### Next 2 Weeks

5. **Resolve Harness Abstraction** - Critical blocker
   - Design harness interface
   - Implement Claude harness
   - Add config for harness selection

6. **Build Minimal Workflow Engine** - Unblocks many features
   - Start with simple sequential workflows (YAML)
   - Add conditional branching
   - Implement tool execution layer

7. **Define Core Metrics** - Needed for observability
   - What to track per run
   - Success/failure criteria
   - Performance indicators

### Next Month

8. **Complete Capture Workflow** - Builds on capture feature
9. **Enhance Interview Mode** - Improves UX for ambiguous tasks
10. **Build Runs Analysis** - Uses metrics from step 7

---

## Tools Wishlist

To move specs from draft → ready, we need better research/design/decision tools.

See `specs/TOOLS-WISHLIST.md` for comprehensive list including:

**High Priority:**
- Complexity Estimator
- Trade-off Analyzer  
- Dependency Analyzer
- Readiness Score Calculator
- Technical Feasibility Checker

**Medium Priority:**
- Design Pattern Matcher
- Risk Scorer
- API Design Validator
- Test Coverage Planner

---

## Spec Health

### Consolidation Needed

These specs overlap and should be unified:
- `pm-workbench.md` + `ai-assisted-pm-shaping-model.md` + `vision-to-tasks-pipeline.md`

### Missing Critical Specs

Need to create:
- Harness abstraction spec (critical dependency)
- Autonomy model spec (referenced but doesn't exist)
- MCP integration spec (assumed by tools-registry)

---

## Notes

- Features can move between sections as priorities evolve
- Version numbers assigned at release time, not pre-planned
- Standalone features can be implemented in any order
- See `specs/SPEC-TEMPLATE.md` for frontmatter schema
- See `specs/SPEC-STATUS.md` for detailed per-spec analysis (deprecated - content merged here)

---

**Related Docs:**
- `specs/SPEC-TEMPLATE.md` - Frontmatter schema for specs
- `specs/TOOLS-WISHLIST.md` - Tools we wish we had
- `CHANGELOG.md` - Released features by version
- `specs/research/external-tools-analysis.md` - Analysis of adjacent tools

# Cub Roadmap

Comprehensive status of all features and specifications.

**Last Updated:** 2026-01-19

---

## Spec Organization

Specs are organized into three states:

1. **`specs/completed/`** - Features merged to main and shipped
2. **`specs/planned/`** - Ready to break into tasks and implement
3. **`specs/researching/`** - Early research, design exploration, open questions

Additional:
- **`sketches/`** - Investigations, notes, artifacts (not locked-down specs)
- **`specs/SPEC-TEMPLATE.md`** - Frontmatter schema for specs
- **`specs/TOOLS-WISHLIST.md`** - Research/design tools we need

---

## Summary Stats

- **Completed:** 9 features
- **Planned:** 14 features
- **Researching:** 9 specs

---

## ✅ Completed (`specs/completed/`)

Features fully implemented and shipped to main.

| Feature | Version | Spec |
|---------|---------|------|
| Vision-to-Tasks Pipeline | 0.14 | `completed/vision-to-tasks-pipeline.md` |
| Plan Review | 0.15 | `completed/plan-review.md` |
| Interview Mode | 0.16 | `completed/interview-mode.md` |
| PRD Import / Document Conversion | 0.17 | `completed/prd-import.md` |
| Onboarding & Project Organization | 0.18 | `completed/onboarding-and-organization.md` |
| Git Workflow Integration | 0.19 | `completed/git-workflow-integration.md` |
| Guardrails System | 0.20 | `completed/guardrails-system.md` |
| Live Dashboard (tmux) | 0.23 | `completed/live-dashboard.md` |
| Investigate Command | 0.22 | `completed/investigate-command.md` |

**Key accomplishments:**
- Full prep pipeline (triage→architect→plan→bootstrap)
- Interactive refinement modes (interview, review)
- Branch/PR workflow integration
- Live monitoring dashboard
- Institutional memory (guardrails)
- Research/design/audit command

---

## 📋 Planned (`specs/planned/`)

Features ready to break into tasks and implement. Design is clear, open questions answered.

### High Priority / Quick Wins

| Feature | Complexity | Spec |
|---------|------------|------|
| Circuit Breaker / Stagnation Detection | Medium | `planned/circuit-breaker.md` |
| Receipt-Based Gating | Low | `planned/receipt-based-gating.md` |
| Re-anchoring Mechanism | Low | `planned/re-anchoring.md` |
| Capture System | Medium | `planned/capture.md` |

**Why these are next:**
- Circuit breaker: Prevents wasted iterations, standalone
- Receipt-based gating: Like guardrails, straightforward
- Re-anchoring: Standalone, improves context management
- Capture: Core implemented, needs CLI completion

### Quality & Reliability

| Feature | Complexity | Spec |
|---------|------------|------|
| Advanced Error Detection | Medium | `planned/advanced-error-detection.md` |
| Dual-Condition Exit | Low | `planned/dual-condition-exit.md` |
| Fresh Context Mode | Medium | `planned/fresh-context-mode.md` |
| Implementation Review | Medium | `planned/implementation-review.md` |
| Sandbox Mode | High | `planned/sandbox-mode.md` |

### Tooling & Integration

| Feature | Complexity | Spec |
|---------|------------|------|
| Multi-Model Review | Medium | `planned/multi-model-review.md` |
| Runs Analysis | Medium | `planned/runs-analysis.md` |
| Verification Integrations | Medium | `planned/verification-integrations.md` |
| Codebase Health Audit | Medium | `planned/codebase-health-audit.md` |

### In Progress

| Feature | Status | Spec |
|---------|--------|------|
| Language Migration (Go + Python) | Active (feat/go-rewrite) | `planned/language-migration.md` |

---

## 🔬 Researching (`specs/researching/`)

Features in early research/design phase. Still answering key questions, exploring approaches.

### Core Infrastructure

| Spec | Focus | Status |
|------|-------|--------|
| `toolsmith.md` | **Meta-tool for tool discovery/adoption** | **Needs discovery source prioritization, evaluation criteria** |
| `tool-marketplace.md` | **ClawdHub-style collection of cub tools** | **Needs distribution model, packaging format, quality standards** |
| `tools-registry.md` | Unified tool discovery/execution | Needs format decisions, MCP integration |
| `workflow-management.md` | YAML-based orchestration | Needs expression language, human handoff UX |
| `ai-assisted-pm-shaping-model.md` | PM workflow modes | Needs operationalization |

**Blockers:**
- Toolsmith: Needs discovery source prioritization (which to search first), evaluation criteria definition
- Tool Marketplace: Needs distribution model (central vs git-based), packaging format, quality standards
- Tools registry: Needs MCP integration design, authentication approach
- Workflow management: Expression language choice, state persistence format
- PM shaping: Needs breaking down into specific features

**Note:** Toolsmith can help bootstrap other wishlist tools by discovering and adopting existing components (see spec for 5 concrete examples). Tool marketplace publishes these implementations for community use.

### Feature Development

| Spec | Focus | Status |
|------|-------|--------|
| `capture-workflow.md` | Capture → spec pipeline | Depends on workflow engine |
| `pm-workbench.md` | Integrated PM environment | Vision doc, needs scoping |

### Analysis & Strategy

| Spec | Purpose |
|------|---------|
| `external-tools-analysis.md` | Analysis of Gas Town, Compound, Loom |
| `knowledge-retention-system.md` | Cross-run knowledge compounding |

---

## Key Dependencies & Blockers

### Architectural Decisions Needed

1. **Harness Abstraction**
   - Blocks: Multi-Model Review, Tools Registry, Workflow Management
   - Need: Define harness interface for swappable LLM providers

2. **Workflow Engine**
   - Blocks: Capture Workflow, PM Shaping implementation
   - Need: Decide native YAML vs Windmill/Temporal

3. **MCP Integration**
   - Blocks: Tools Registry, Verification Integrations
   - Need: Stable MCP protocol integration

### Design Questions to Resolve

4. **Error Taxonomy** - What failure patterns should we detect?
   - Blocks: Advanced Error Detection, Circuit Breaker tuning

5. **Metrics/Observability** - What should we measure?
   - Blocks: Runs Analysis, Live Dashboard enhancements

6. **Human Handoff UX** - How to pause and ask for input?
   - Blocks: Workflow Management, Interview Mode enhancements

---

## Next Steps

### Immediate (This Week)

1. **Implement Circuit Breaker** - Clear spec, high value, standalone
2. **Implement Receipt-Based Gating** - Similar to guardrails

### Short Term (Next 2 Weeks)

3. **Resolve Harness Abstraction** - Critical blocker
   - Design harness interface
   - Implement Claude harness
   - Add config for harness selection

4. **Build Minimal Workflow Engine** - Unblocks multiple features
   - Simple sequential workflows (YAML)
   - Conditional branching
   - Tool execution layer

5. **Define Core Metrics** - Needed for observability
   - What to track per run
   - Success/failure criteria
   - Performance indicators

### Medium Term (Next Month)

6. **Complete Capture Feature** - Finish implementation
7. **Enhance Interview Mode** - Improve UX for ambiguous tasks
8. **Build Runs Analysis** - Use metrics from step 5

---

## Tools Wishlist

To move specs from researching → planned, we need better research/design/decision tools.

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

## External Inspiration

Features being considered based on analysis of adjacent tools:

| Feature | Source | Status |
|---------|--------|--------|
| Session Checkpointing | Gas Town | Research |
| Team Knowledge Base | Compound | Research |
| Agent Personas | Gas Town | Research |
| Workflow Recipes | Gas Town | Research |

See: `specs/researching/external-tools-analysis.md` for analysis of Gas Town, Compound, and other tools.

---

## Spec Health Notes

### Consolidation Candidates

These specs may overlap and could be unified:
- `pm-workbench.md` + `ai-assisted-pm-shaping-model.md` + parts of `vision-to-tasks-pipeline.md`

### Missing Critical Specs

Need to create:
- **Harness abstraction** (critical dependency for multiple features)
- **Autonomy model** (referenced but doesn't exist)
- **MCP integration** (assumed by tools-registry)

---

## Version History

Recent releases (see `CHANGELOG.md` for complete history):

- **v0.26.x** (current) - Python CLI migration, GitHub integration improvements
- **v0.23.0** - Live Dashboard
- **v0.20.0** - Guardrails System
- **v0.19.0** - Git Workflow Integration
- **v0.18.0** - Onboarding & Organization
- **v0.17.0** - PRD Import
- **v0.16.0** - Interview Mode
- **v0.15.0** - Plan Review
- **v0.14.0** - Vision-to-Tasks Pipeline

---

**Related Docs:**
- `specs/SPEC-TEMPLATE.md` - Frontmatter schema for specs
- `specs/TOOLS-WISHLIST.md` - Tools we wish we had
- `CHANGELOG.md` - Released features by version
- `sketches/` - Investigations, notes, and artifacts

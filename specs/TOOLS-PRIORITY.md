# Tools Priority Analysis

Analysis of which tools from TOOLS-WISHLIST.md are most needed across specs.

Based on cross-referencing all planned and researching specs with the tools wishlist.

**Last Updated:** 2026-01-19

---

## Tool Usage Frequency

Count of how many specs reference each tool:

| Tool | References | Priority | Category |
|------|------------|----------|----------|
| **Design Pattern Matcher** | 12 | **Critical** | Design & Architecture |
| **Trade-off Analyzer** | 11 | **Critical** | Decision Support |
| **API Design Validator** | 8 | **High** | Design & Architecture |
| **Competitive Analysis Tool** | 7 | **High** | Research & Discovery |
| **Technical Feasibility Checker** | 5 | **High** | Research & Discovery |
| **Dependency Analyzer** | 5 | **High** | Scoping & Prioritization |
| **Implementation Path Generator** | 4 | **Medium** | Meta / Process |
| **Complexity Estimator** | 3 | **Medium** | Scoping & Prioritization |
| **Test Coverage Planner** | 2 | **Medium** | Validation & Testing |
| **Spec Clarity Checker** | 2 | **Medium** | Documentation & Communication |
| **Risk Scorer** | 2 | **Medium** | Scoping & Prioritization |
| Others | 1 each | **Low** | Various |

---

## Top 5 Critical Tools (Build These First)

### 1. Design Pattern Matcher (12 references)

**Referenced by:**
- circuit-breaker, receipt-based-gating, re-anchoring
- advanced-error-detection, dual-condition-exit, fresh-context-mode
- implementation-review, runs-analysis, verification-integrations
- tools-registry, workflow-management, knowledge-retention-system

**What it does:**
- Find proven patterns for common problems
- Show pattern examples in similar tech stack
- Suggest modifications for our context
- Link to reference implementations

**Why critical:**
- Nearly every spec asks "is there a standard way to solve this?"
- Unblocks design decisions across the board
- Most specs need pattern research to move forward

**Implementation approach:**
- LLM-based with curated pattern library
- Search GitHub for similar implementations
- Extract and summarize patterns

---

### 2. Trade-off Analyzer (11 references)

**Referenced by:**
- re-anchoring, fresh-context-mode, implementation-review
- advanced-error-detection, multi-model-review, runs-analysis
- ai-assisted-pm-shaping-model, capture-workflow
- tools-registry, workflow-management, knowledge-retention-system

**What it does:**
- Compare multiple approaches objectively
- Score against criteria (complexity, performance, maintainability)
- Identify deal-breakers
- Recommend based on project context

**Why critical:**
- Most specs have multiple valid approaches
- Decisions need structured comparison
- Prevents analysis paralysis

**Implementation approach:**
- LLM-based with structured scoring rubric
- Define standard criteria (complexity, perf, maintenance, risk)
- Generate comparison matrices

---

### 3. API Design Validator (8 references)

**Referenced by:**
- receipt-based-gating, dual-condition-exit, capture
- multi-model-review, verification-integrations
- tools-registry, workflow-management, knowledge-retention-system

**What it does:**
- Check if API design is ergonomic and complete
- Identify missing CRUD operations
- Suggest naming conventions
- Find edge cases

**Why critical:**
- Many specs define new APIs or formats
- Poor API design leads to rework
- Need consistency across cub's interfaces

**Implementation approach:**
- LLM-based with API design principles
- Check against existing cub patterns
- Generate examples of API usage

---

### 4. Competitive Analysis Tool (7 references)

**Referenced by:**
- advanced-error-detection, codebase-health-audit, runs-analysis
- ai-assisted-pm-shaping-model, pm-workbench
- tools-registry, workflow-management, knowledge-retention-system

**What it does:**
- Search for similar open source projects
- Extract key features/approaches from README/docs
- Summarize differences and trade-offs
- Find prior art and design patterns

**Why critical:**
- Many specs ask "how do others solve this?"
- Prevents reinventing the wheel
- Identifies proven approaches

**Implementation approach:**
- GitHub search + README parsing
- LLM summarization of approaches
- Comparison matrix generation

---

### 5. Technical Feasibility Checker (5 references)

**Referenced by:**
- circuit-breaker, re-anchoring, sandbox-mode
- verification-integrations, tools-registry

**What it does:**
- Quick validation that approach is technically viable
- Check if library/API exists and is maintained
- Verify version compatibility
- Estimate integration complexity

**Why critical:**
- Prevents going down dead-end paths
- Validates assumptions early
- Identifies integration risks

**Implementation approach:**
- Check package registries (npm, PyPI, etc)
- Verify GitHub repo status (stars, recent commits)
- LLM-based complexity estimation

---

## Medium Priority Tools (Build These Second)

### Dependency Analyzer (5 references)
Understand what needs to be built first. Referenced by multi-model-review, fresh-context-mode, ai-assisted-pm-shaping-model, capture-workflow, pm-workbench.

### Implementation Path Generator (4 references)
Break specs into tasks. Referenced by capture, codebase-health-audit, ai-assisted-pm-shaping-model, pm-workbench.

### Complexity Estimator (3 references)
Realistic effort assessment. Referenced by sandbox-mode, language-migration, pm-workbench.

### Test Coverage Planner (2 references)
Identify what needs testing. Referenced by circuit-breaker, receipt-based-gating.

### Spec Clarity Checker (2 references)
Ensure specs are implementable. Referenced by dual-condition-exit, implementation-review.

### Risk Scorer (2 references)
Identify high-risk changes. Referenced by sandbox-mode, language-migration.

---

## Implementation Strategy

### Phase 1: Critical Tools (Weeks 1-3)

Build the top 3 tools that unblock the most specs:

1. **Design Pattern Matcher** (week 1)
   - Start simple: LLM + curated patterns
   - GitHub search for examples
   
2. **Trade-off Analyzer** (week 2)
   - Define scoring rubric
   - LLM-based comparison generation
   
3. **API Design Validator** (week 3)
   - Check against existing patterns
   - Generate usage examples

### Phase 2: High-Value Tools (Weeks 4-6)

4. **Competitive Analysis Tool** (week 4)
5. **Technical Feasibility Checker** (week 5)
6. **Dependency Analyzer** (week 6)

### Phase 3: Specialized Tools (Weeks 7+)

Build remaining medium-priority tools as needed.

---

## Tool Categories

**Research & Discovery** (3 tools, 17 total references)
- Competitive Analysis Tool (7)
- Technical Feasibility Checker (5)
- User Research Summarizer (1)
- Integration Point Mapper (1)
- Spec Search & Navigation (1)

**Design & Architecture** (2 tools, 20 total references)
- Design Pattern Matcher (12)
- API Design Validator (8)

**Decision Support** (1 tool, 11 references)
- Trade-off Analyzer (11)

**Scoping & Prioritization** (4 tools, 12 total references)
- Dependency Analyzer (5)
- Implementation Path Generator (4)
- Complexity Estimator (3)
- Risk Scorer (2)

**Validation & Testing** (1 tool, 2 references)
- Test Coverage Planner (2)

**Documentation & Communication** (1 tool, 2 references)
- Spec Clarity Checker (2)

---

## Impact Analysis

### Building Top 5 Tools Would:

**Unblock planned specs:**
- Circuit Breaker (references 3 of top 5)
- Receipt-Based Gating (references 3 of top 5)
- Re-anchoring (references 3 of top 5)
- Advanced Error Detection (references 3 of top 5)
- Sandbox Mode (references 3 of top 5)
- Multi-Model Review (references 3 of top 5)
- Runs Analysis (references 3 of top 5)

**Advance researching specs:**
- Tools Registry (references 4 of top 5)
- Workflow Management (references 4 of top 5)
- AI-Assisted PM Shaping (references 3 of top 5)
- Knowledge Retention System (references 4 of top 5)

**Total impact:** Would help answer key questions in 18 out of 21 specs (86%)

---

## Next Steps

1. **Validate tool designs** - Create spec for each of the top 5 tools
2. **Build MVP implementations** - Start with simple LLM-based versions
3. **Integrate with workflow** - Make tools invokable from CLI
4. **Iterate based on usage** - Track which tools are most valuable in practice

---

**Related:**
- `TOOLS-WISHLIST.md` - Full tool catalog with capabilities
- `ROADMAP.md` - Spec status and priorities
- `specs/researching/tools-registry.md` - Tool execution infrastructure
- `specs/researching/workflow-management.md` - Tool orchestration

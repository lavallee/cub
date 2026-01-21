# Tools Wishlist

Tools we wish we had to help move specs from "draft" to "ready" by answering open questions and making decisions.

This wishlist informs tool registry and workflow development priorities.

---

## Research & Discovery

### **Competitive Analysis Tool**
**Need:** Compare our approach to existing solutions  
**Use case:** When spec asks "how do others solve this?"  
**Capabilities:**
- Search for similar open source projects
- Extract key features/approaches from README/docs
- Summarize differences and trade-offs
- Find prior art and design patterns

**Example question answered:**  
"What workflow systems exist that are similar to what we're building?"

---

### **User Research Summarizer**
**Need:** Synthesize insights from conversations, issues, support tickets  
**Use case:** When spec needs validation of problem/approach  
**Capabilities:**
- Search GitHub issues for pain points
- Summarize Discord/Slack discussions
- Extract feature requests patterns
- Identify common workflows

**Example question answered:**  
"Do users actually need this feature? What are they asking for?"

---

### **Technical Feasibility Checker**
**Need:** Quick validation that approach is technically viable  
**Use case:** When spec proposes new architecture/integration  
**Capabilities:**
- Check if library/API exists and is maintained
- Verify version compatibility
- Find example implementations
- Estimate integration complexity

**Example question answered:**  
"Can we actually do this with available tools?"

---

### **Dependency Analyzer**
**Need:** Understand what needs to be built first  
**Use case:** When spec touches multiple systems  
**Capabilities:**
- Map dependencies between specs
- Identify circular dependencies
- Suggest implementation order
- Flag breaking changes

**Example question answered:**  
"What else needs to be ready before we can build this?"

---

## Design & Architecture

### **Design Pattern Matcher**
**Need:** Find proven patterns for common problems  
**Use case:** When spec is solving a known problem class  
**Capabilities:**
- Match problem to design patterns
- Show pattern examples in similar tech stack
- Suggest modifications for our context
- Link to reference implementations

**Example question answered:**  
"Is there a standard way to solve this?"

---

### **API Design Validator**
**Need:** Check if API design is ergonomic and complete  
**Use case:** When spec proposes new API/interface  
**Capabilities:**
- Check consistency with existing APIs
- Identify missing CRUD operations
- Suggest naming conventions
- Find edge cases

**Example question answered:**  
"Does this API make sense? What are we missing?"

---

### **Schema Evolution Checker**
**Need:** Validate schema changes won't break things  
**Use case:** When spec changes data models  
**Capabilities:**
- Analyze breaking vs non-breaking changes
- Suggest migration path
- Identify affected code
- Check backwards compatibility

**Example question answered:**  
"Can we make this change safely?"

---

## Scoping & Prioritization

### **Complexity Estimator**
**Need:** Realistic effort/complexity assessment  
**Use case:** When deciding if spec is too big  
**Capabilities:**
- Count files/functions that need changes
- Estimate based on similar past work
- Identify rabbit holes
- Suggest scope cuts

**Example question answered:**  
"Is this a 2-day or 2-week project?"

---

### **Impact Analyzer**
**Need:** Understand user/business value  
**Use case:** When prioritizing specs  
**Capabilities:**
- Estimate user impact (% affected)
- Analyze usage patterns
- Compare to alternatives
- Quantify problem severity

**Example question answered:**  
"How many users will this help?"

---

### **Risk Scorer**
**Need:** Identify high-risk changes  
**Use case:** When deciding autonomy level  
**Capabilities:**
- Flag breaking changes
- Identify security implications
- Check for irreversible actions
- Suggest mitigation strategies

**Example question answered:**  
"What could go wrong?"

---

## Validation & Testing

### **Test Coverage Planner**
**Need:** Identify what needs testing  
**Use case:** When spec needs test strategy  
**Capabilities:**
- Suggest test cases from spec
- Identify edge cases
- Recommend test types (unit/integration/e2e)
- Generate test skeleton

**Example question answered:**  
"How do we know this works?"

---

### **Smoke Test Generator**
**Need:** Quick validation without full test suite  
**Use case:** When prototyping or doing spikes  
**Capabilities:**
- Generate minimal test script
- Create sample data
- Suggest validation steps
- Provide success criteria

**Example question answered:**  
"What's the fastest way to verify this works?"

---

### **Backward Compatibility Checker**
**Need:** Ensure changes don't break existing usage  
**Use case:** When modifying public APIs  
**Capabilities:**
- Compare old vs new signatures
- Find all call sites
- Suggest deprecation path
- Generate migration guide

**Example question answered:**  
"Will this break existing code?"

---

## Decision Support

### **Trade-off Analyzer**
**Need:** Compare multiple approaches objectively  
**Use case:** When spec has multiple solution paths  
**Capabilities:**
- List pros/cons for each approach
- Score against criteria (complexity, performance, maintainability)
- Identify deal-breakers
- Recommend based on project context

**Example question answered:**  
"Which approach should we choose?"

---

### **Constraint Checker**
**Need:** Validate against project constraints  
**Use case:** When spec might violate policies/standards  
**Capabilities:**
- Check against coding standards
- Verify license compatibility
- Validate security requirements
- Check accessibility compliance

**Example question answered:**  
"Does this meet our requirements?"

---

### **Assumption Validator**
**Need:** Test assumptions before committing  
**Use case:** When spec makes untested assumptions  
**Capabilities:**
- Identify implicit assumptions
- Suggest quick validation tests
- Find contradicting evidence
- Propose experiments

**Example question answered:**  
"Are our assumptions correct?"

---

## Documentation & Communication

### **Spec Clarity Checker**
**Need:** Ensure spec is understandable and complete  
**Use case:** Before marking spec as "ready"  
**Capabilities:**
- Find ambiguous language
- Identify missing sections
- Check for contradictions
- Suggest clarifications

**Example question answered:**  
"Is this spec clear enough to implement?"

---

### **Changelog Generator**
**Need:** Document what changed and why  
**Use case:** When spec is updated  
**Capabilities:**
- Diff spec versions
- Summarize key changes
- Identify decision reversals
- Generate update notes

**Example question answered:**  
"What changed since last time?"

---

### **Stakeholder Impact Notifier**
**Need:** Alert relevant people about changes  
**Use case:** When spec affects multiple teams/areas  
**Capabilities:**
- Identify affected stakeholders
- Summarize impact per stakeholder
- Suggest review/approval flow
- Track sign-offs

**Example question answered:**  
"Who needs to know about this?"

---

## Meta / Process

### **Spec Health Monitor**
**Need:** Track spec freshness and completeness  
**Use case:** Regular spec maintenance  
**Capabilities:**
- Flag stale specs
- Check for broken links
- Identify orphaned specs
- Suggest consolidation

**Example question answered:**  
"Which specs need attention?"

---

### **Readiness Score Calculator**
**Need:** Objective readiness assessment  
**Use case:** Deciding what to implement next  
**Capabilities:**
- Score based on answered questions
- Weight by decision importance
- Compare specs
- Suggest next steps to improve score

**Example question answered:**  
"Which specs are ready to build?"

---

### **Implementation Path Generator**
**Need:** Break ready spec into tasks  
**Use case:** Moving from spec to execution  
**Capabilities:**
- Generate task breakdown
- Sequence dependencies
- Estimate per task
- Create tickets/issues

**Example question answered:**  
"How do we actually build this?"

---

## Cross-Cutting Tools

### **Spec Search & Navigation**
**Need:** Find related specs quickly  
**Use case:** Understanding context and connections  
**Capabilities:**
- Semantic search across specs
- Find related/similar specs
- Visualize spec dependencies
- Track spec lineage (what led to this)

**Example question answered:**  
"What else is related to this?"

---

### **Decision Log Extractor**
**Need:** Track key decisions made in specs  
**Use case:** Understanding rationale later  
**Capabilities:**
- Extract decision records from specs
- Link decisions to outcomes
- Find decision justifications
- Alert on contradictory decisions

**Example question answered:**  
"Why did we decide this?"

---

### **Integration Point Mapper**
**Need:** Understand system boundaries and connections  
**Use case:** When spec touches multiple systems  
**Capabilities:**
- Map integration points
- Identify API contracts
- Find shared dependencies
- Suggest decoupling opportunities

**Example question answered:**  
"Where does this connect to everything else?"

---

## Priority Indicators

Each tool has implicit priority based on pain points:

**High Priority** (would use daily):
- Competitive Analysis Tool
- Complexity Estimator
- Trade-off Analyzer
- Spec Search & Navigation

**Medium Priority** (would use weekly):
- Technical Feasibility Checker
- Risk Scorer
- Readiness Score Calculator
- Dependency Analyzer

**Low Priority** (nice to have):
- Stakeholder Impact Notifier
- Spec Health Monitor
- Changelog Generator

---

## Implementation Notes

These tools would be:
- Part of the **tools registry**
- Invokable in **workflows** (automated in triage/shaping)
- Accessible via **CLI** for manual use
- Composable (outputs of one feed into another)

Many can be implemented as:
- LLM prompts with structured output
- Searches + summarization
- Static analysis of codebase/specs
- Integration with existing tools (GitHub, etc)

Start simple: LLM-based tools that read specs and code, provide structured analysis.

---

**Related**: tools-registry.md, workflow-management.md

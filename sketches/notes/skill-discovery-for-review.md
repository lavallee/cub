# Skill Discovery for Improving cub review

**Date:** 2025-01-25
**Goal:** Find code analysis skills that could improve our review workflow

## Current cub review Capabilities

### Structural Checks (default)
- Verification status from ledger
- Spec drift detection (additions/omissions)
- Outcome success/failure/partial
- Commit history presence
- File existence verification
- Acceptance criteria (markdown checkbox parsing)
- Test file existence

### Deep Analysis (`--deep` flag)
- LLM-based comparison of implementation vs specification
- Parses `[CRITICAL]`, `[WARNING]`, `[INFO]` markers from output
- Reads spec file + implementation files
- Builds context from ledger entry metadata

### Current Limitations
1. Deep analysis prompt is generic - not specialized for different review types
2. No security-focused analysis
3. No performance analysis
4. No architecture/design review
5. No test quality assessment
6. Single-pass analysis (no multi-step reasoning)

---

## Discovery Process

### Phase 1: Gather ✓
Found 12 skills doing code analysis from multiple sources.

### Phase 2: Evaluate (below)
Document what each analyzes, inputs, outputs, unique techniques.

### Phase 3: Report (below)
Identify themes, contrasts, gaps, combinations.

### Phase 4: Decide (pending)

---

## Gathered Skills

| # | Skill | Source | Focus Area |
|---|-------|--------|------------|
| 1 | receiving-code-review | obra/superpowers | Handling review feedback |
| 2 | verification-before-completion | obra/superpowers | Evidence-based claims |
| 3 | systematic-debugging | obra/superpowers | Root cause analysis |
| 4 | test-driven-development | obra/superpowers | Test-first workflow |
| 5 | requesting-code-review | obra/superpowers | Getting reviews |
| 6 | skill-threat-modeling | fr33d3m0n | Security assessment |
| 7 | code-review-router | win4r | Review routing |
| 8 | differential-review | trailofbits | Security diff review |
| 9 | static-analysis | trailofbits | CodeQL/Semgrep |
| 10 | fix-review | trailofbits | Verify fixes |
| 11 | audit-context-building | trailofbits | Architecture understanding |
| 12 | code-review | getsentry | PR review practices |

---

## Evaluation Notes

### 1. receiving-code-review (obra/superpowers)
**Focus:** How to process review feedback before implementing
**Key Technique:** Verification-first: READ → UNDERSTAND → VERIFY → EVALUATE → RESPOND → IMPLEMENT
**Unique Insight:** "Technical correctness supersedes social comfort" - push back when justified
**Output:** Action-based acknowledgments, not performative gratitude
**Relevance to cub review:** Could inform how we present review findings - actionable, not just critical

### 2. verification-before-completion (obra/superpowers)
**Focus:** Ensuring claims are backed by evidence
**Key Technique:** 5-step gate: identify command → execute → review output → verify support → state claim
**Iron Law:** "NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE"
**Red Flags:** Tentative language ("should", "probably"), satisfaction pre-verification
**Relevance to cub review:** This IS what cub review should enforce - verification before marking complete

### 3. systematic-debugging (obra/superpowers)
**Focus:** Finding root causes, not symptoms
**Key Technique:** 4 phases - Investigation → Pattern Analysis → Hypothesis Testing → Implementation
**Critical Rule:** "ALWAYS find root cause before attempting fixes. Symptom fixes are failure."
**Safeguard:** If 3+ fixes fail, stop - it's architectural, not a bug
**Relevance to cub review:** When review finds issues, guide toward root cause not surface fixes

### 4. test-driven-development (obra/superpowers)
**Focus:** Test-first workflow enforcement
**Key Technique:** Red-Green-Refactor with verification at each step
**Iron Law:** Write failing tests before production code - no exceptions
**Validation:** "If you didn't watch the test fail, you don't know if it tests the right thing"
**Relevance to cub review:** Verify tests were written BEFORE code (check git history)

### 5. requesting-code-review (obra/superpowers)
**Focus:** Structured approach to getting reviews
**Key Technique:** Capture git refs → invoke reviewer → respond to feedback
**Integration:** Review after every task, or every 3 tasks in batches
**Relevance to cub review:** Could inform when/how to trigger reviews in cub workflow

### 6. skill-threat-modeling (fr33d3m0n)
**Focus:** Comprehensive security threat assessment
**Key Technique:** 8-phase sequential workflow with knowledge bases (CWE, CAPEC, ATT&CK)
**Phases:** Project Understanding → DFD → Trust Boundaries → Design Review → STRIDE → Risk Validation → Mitigation → Report
**Unique:** POC code required for Critical/High threats, attack path feasibility scoring
**Data Model:** Finding → Threat → ValidatedRisk → Mitigation with full traceability
**Relevance to cub review:** Too heavyweight for task review, but design review phase (Phase 4) has good checklist

### 7. code-review-router (win4r)
**Focus:** Routing reviews to appropriate tools
**Key Technique:** Complexity scoring + pattern matching → route to Gemini or Codex
**Hard Rules:** Security code → Codex, >20 files → Codex, pure frontend → Gemini
**Relevance to cub review:** Could inform model selection for deep analysis

### 8. differential-review (trailofbits)
**Focus:** Security-focused code change review
**Key Technique:** Git history analysis + security lens on diffs
**Relevance to cub review:** Could add git diff analysis to deep review

### 9. static-analysis (trailofbits)
**Focus:** Automated code scanning
**Key Technique:** CodeQL, Semgrep, SARIF parsing
**Relevance to cub review:** Could integrate static analysis results into review

### 10. fix-review (trailofbits)
**Focus:** Verify fixes don't introduce new issues
**Key Technique:** Compare fix against original finding, check for regressions
**Relevance to cub review:** Useful when reviewing tasks that fix previous issues

### 11. audit-context-building (trailofbits)
**Focus:** Deep architectural understanding
**Key Technique:** Ultra-granular code examination
**Relevance to cub review:** Could inform how we build context for deep analysis

### 12. code-review (getsentry)
**Focus:** Practical PR review checklist
**Key Technique:** Problem identification checklist + design review + test coverage
**Categories:** Runtime errors, performance (N+1, O(n²)), security, API changes
**Tone:** "Empathetic, actionable suggestions" - approve when only minor issues remain
**Relevance to cub review:** Good checklist for what to look for in implementation review

---

## Themes & Contrasts

### Common Themes

1. **Evidence Before Claims**
   - verification-before-completion: "No claims without fresh verification"
   - systematic-debugging: "Find root cause before fixes"
   - TDD: "Watch test fail first"
   - All emphasize PROOF over ASSERTION

2. **Structured Multi-Phase Workflows**
   - threat-modeling: 8 phases, strict sequence
   - systematic-debugging: 4 phases
   - verification: 5-step gate
   - receiving-code-review: 6-step process
   - Lesson: Complex analysis benefits from explicit phases

3. **Actionable Output**
   - receiving-code-review: Action-based acknowledgments
   - getsentry: "Actionable suggestions, not vague criticism"
   - fix-review: Clear fix verification
   - Lesson: Review output should be actionable, not just critical

4. **Severity Classification**
   - threat-modeling: Critical/High/Medium/Low with POC requirements
   - getsentry: "Approve when only minor issues remain"
   - cub review already has: CRITICAL/WARNING/INFO
   - Lesson: Different severities need different responses

5. **Context Building**
   - audit-context-building: Deep architectural understanding first
   - threat-modeling: Phase 1 is project understanding
   - Lesson: Good review requires understanding context first

### Contrasts

1. **Lightweight vs Heavyweight**
   - verification-before-completion: Simple 5-step gate
   - threat-modeling: 8-phase comprehensive process
   - Trade-off: Thoroughness vs speed

2. **Generic vs Domain-Specific**
   - getsentry: Python/Django/React specific patterns
   - systematic-debugging: Language-agnostic
   - Trade-off: Precision vs generality

3. **Human-in-Loop vs Autonomous**
   - receiving-code-review: Assumes human feedback
   - code-review-router: Fully automated routing
   - Trade-off: Quality vs automation

### Gaps in Current Skills

1. **Spec Compliance** - cub review's unique strength (ledger-based drift detection)
2. **Task Lineage** - tracking epic/plan context through review
3. **Cost/Token Awareness** - no skills consider LLM cost efficiency
4. **Incremental Review** - most assume full codebase, not task-scoped

---

## Synthesis: What Could Improve cub review?

### Immediate Improvements (Prompt Enhancement)

1. **Add verification checklist from superpowers**
   - Before claiming completion, verify: tests pass, files exist, criteria met

2. **Add Sentry's problem identification checklist**
   - Runtime errors, performance (N+1, O(n²)), security, API changes

3. **Structure deep analysis as phases**
   - Phase 1: Build context (what was the task, what changed)
   - Phase 2: Verify structural completeness
   - Phase 3: Assess implementation quality
   - Phase 4: Check for issues (security, performance, design)
   - Phase 5: Summarize with severity classification

4. **Add severity-appropriate recommendations**
   - CRITICAL: Blocks approval, specific fix required
   - WARNING: Should address, provide guidance
   - INFO: Nice to have, optional

### Medium-Term Improvements (Feature Enhancement)

1. **Git diff analysis** - Use differential-review approach
2. **Model routing** - Simple tasks → haiku, complex → sonnet/opus
3. **Test-first verification** - Check git history for TDD compliance
4. **Static analysis integration** - Run ruff/mypy, include in review

### Ideas to NOT Pursue

1. **Full threat modeling** - Too heavyweight for task review
2. **Multiple reviewer routing** - Adds complexity without clear benefit for single-project use
3. **POC code generation** - Beyond scope of implementation review

---

## Decision Interview

**Purpose:** These 5 questions help determine which features to include in cub review.

---

### Q1: When does review happen in your workflow?

| Answer | Implies |
|--------|---------|
| **A) After every task** | Needs to be fast (<30s). Lightweight structural checks. Haiku model. Skip comprehensive analysis. |
| **B) After batches of tasks** | Moderate depth. Can aggregate findings across tasks. Sonnet model. |
| **C) Before merge/release** | Can be thorough. Full deep analysis justified. Sonnet/Opus. Multi-phase. |
| **D) On-demand when suspicious** | Maximum depth. User already suspects issues. Comprehensive audit mode. |

**Feature mapping:**
- A → Structural checks only, no LLM deep analysis
- B → Single-pass deep analysis with checklist
- C/D → Multi-phase deep analysis with verification

---

### Q2: What's your primary concern about completed work?

| Answer | Implies |
|--------|---------|
| **A) Incomplete - didn't do what was asked** | Focus: Spec compliance, acceptance criteria, drift detection |
| **B) Broken - introduces bugs/errors** | Focus: Runtime errors, edge cases, error handling |
| **C) Insecure - security vulnerabilities** | Focus: Security checklist, injection, auth, secrets |
| **D) Slow - performance problems** | Focus: N+1 queries, O(n²), unnecessary allocations |
| **E) Untested - inadequate test coverage** | Focus: Test existence, TDD compliance, coverage gaps |

**Feature mapping:**
- A → Enhance drift detection, acceptance criteria parsing (cub review's strength)
- B → Add Sentry's problem identification checklist
- C → Add security-focused differential review
- D → Add performance pattern detection
- E → Add git history analysis for test-first verification

*Can select multiple - but prioritize top 2*

---

### Q3: How much do you trust the agent's self-reported completion?

| Answer | Implies |
|--------|---------|
| **A) High - just sanity check** | Quick verification. Trust ledger claims. Flag only obvious issues. |
| **B) Medium - verify key claims** | Structured verification. Check files exist, tests pass, criteria met. |
| **C) Low - comprehensive audit** | Assume nothing. Re-verify everything. Deep code analysis. |

**Feature mapping:**
- A → Current structural checks sufficient
- B → Add verification-before-completion 5-step gate
- C → Multi-phase analysis: context → verify → assess → issues → summarize

---

### Q4: What context is reliably available at review time?

| Answer | Implies |
|--------|---------|
| **A) Full spec + task description + implementation** | Can do spec-to-code compliance |
| **B) Task description + implementation only** | Focus on stated requirements vs code |
| **C) Just the code changes (git diff)** | Differential review only |
| **D) Code + test files** | Can assess test quality and coverage |

**Feature mapping:**
- A → Enable spec compliance analysis (cub review's unique strength)
- B → Simpler requirement-vs-implementation check
- C → Git diff focused review (trailofbits differential-review approach)
- D → Add test quality assessment

*Select all that apply*

---

### Q5: What's the acceptable cost/time overhead per review?

| Answer | Implies |
|--------|---------|
| **A) Minimal (<5s, <1K tokens)** | Structural checks only. No LLM. |
| **B) Low (<30s, <10K tokens)** | Haiku for quick assessment. Single pass. |
| **C) Moderate (<2min, <50K tokens)** | Sonnet for thorough single-pass analysis. |
| **D) Thorough (no limit)** | Opus for comprehensive multi-phase analysis. |

**Feature mapping:**
- A → `cub review task` (no --deep)
- B → `--deep --model haiku` with focused prompt
- C → `--deep` default (sonnet) with full checklist
- D → `--deep --model opus` with multi-phase workflow

---

## Feature Matrix

Based on interview answers, here's what to include:

| Feature | Include When |
|---------|--------------|
| **Structural checks** (files, criteria, tests) | Always |
| **Spec compliance analysis** | Q2=A, Q4=A |
| **Problem identification checklist** | Q2=B, Q3≥B |
| **Security-focused review** | Q2=C |
| **Performance pattern detection** | Q2=D |
| **Test quality/TDD verification** | Q2=E, Q4=D |
| **Multi-phase analysis** | Q1=C/D, Q3=C |
| **Git diff analysis** | Q4=C |
| **Verification gate (5-step)** | Q3=B/C |
| **Model routing** | Q5 determines model |

---

## Sample Profiles

### "Trust but Verify" (Common case)
- Q1: B (after batches)
- Q2: A+B (incomplete, broken)
- Q3: B (medium trust)
- Q4: A (full context)
- Q5: C (moderate cost)

**→ Features:** Structural + spec compliance + problem checklist + verification gate. Sonnet model. Single-pass.

### "Security-Conscious"
- Q1: C (before merge)
- Q2: C (security focus)
- Q3: C (low trust)
- Q4: A+C (spec + diff)
- Q5: D (thorough)

**→ Features:** All structural + security review + diff analysis + multi-phase. Opus model.

### "Fast Feedback Loop"
- Q1: A (every task)
- Q2: A (incomplete)
- Q3: A (high trust)
- Q4: B (task + code)
- Q5: A (minimal)

**→ Features:** Structural checks only. No deep analysis. Haiku if any LLM.

---

## Interview Results (2025-01-25)

### Answers

**Q1 - Timing:** Two-tier system desired
- Quick validation during ralph loop (acceptance criteria focused)
- Configurable deep review in `cub review` step (composable workflows)

**Q2 - Concerns:** Incomplete + Broken
- Agents "forget to follow through on instructions"
- "Decide to leave placeholders"
- "Functional but not necessarily to requirements"

**Q3 - Trust:** Medium
- Self-reported completion can't be fully trusted
- Need verification of key claims

**Q4 - Context:** Rich (all available)
- Specs and plan files ✓
- Task definition ✓
- Git diff ✓
- Harness run log ✓ (bonus context!)

**Q5 - Cost:** Adaptive/progressive
- Start with low/moderate scan
- If issues found → re-run deeper
- Configure based on diff size

### Mapped Feature Set

Based on these answers, here's what to build:

#### Tier 1: Ralph Loop Integration (Quick)
**Purpose:** Fast acceptance criteria validation during task execution
**Trigger:** End of each task in ralph loop
**Features:**
- [ ] Parse acceptance criteria from task description
- [ ] Check each criterion against implementation
- [ ] Flag incomplete/placeholder patterns
- [ ] Time budget: <30s, Haiku model

**Skills informing this:**
- verification-before-completion (5-step gate)
- Sentry's "every PR should have appropriate test coverage"

#### Tier 2: Configurable Deep Review
**Purpose:** Thorough analysis with composable workflow phases
**Trigger:** `cub review task --deep` or before merge
**Features:**
- [ ] **Phase 1: Context Building** - Load spec, task, diff, run log
- [ ] **Phase 2: Structural Verification** - Files exist, tests exist, criteria parsed
- [ ] **Phase 3: Spec Compliance** - Compare implementation to requirements
- [ ] **Phase 4: Problem Identification** - Sentry checklist (runtime errors, edge cases)
- [ ] **Phase 5: Summary** - Grade + actionable recommendations

**Skills informing this:**
- audit-context-building (Phase 1)
- verification-before-completion (Phase 2)
- cub review's existing drift detection (Phase 3)
- Sentry code-review checklist (Phase 4)
- receiving-code-review's action-based output (Phase 5)

#### Adaptive Depth
**Logic:**
```
if diff_size < SMALL_THRESHOLD:
    model = "haiku"
    phases = [1, 2, 5]  # Quick structural
elif diff_size < MEDIUM_THRESHOLD:
    model = "sonnet"
    phases = [1, 2, 3, 5]  # Add spec compliance
else:
    model = "sonnet"  # or opus
    phases = [1, 2, 3, 4, 5]  # Full analysis

if issues_found and depth < max_depth:
    re_run_deeper()
```

#### Unique Cub Advantage: Harness Run Log
No discovered skills use execution logs as review context. This is cub's unique asset:
- What commands did the agent run?
- What errors occurred during execution?
- Did the agent struggle/retry?
- What was the agent's stated approach?

**→ Add Phase 0: Execution Analysis** - Review harness log for red flags before looking at code

### Implementation Priority

1. **First:** Enhance `--deep` prompt with phased structure + Sentry checklist
2. **Second:** Add acceptance criteria parsing to structural checks
3. **Third:** Add harness log analysis (unique differentiator)
4. **Fourth:** Ralph loop integration
5. **Fifth:** Adaptive depth based on diff size

### Not Building (Per Interview)

- Security-focused review (not primary concern)
- Performance pattern detection (not primary concern)
- Multi-model routing (simpler adaptive approach instead)
- Full threat modeling (overkill)

---

## Process Notes

### What Worked
- Web search found multiple skill repositories quickly
- GitHub raw URLs work for fetching SKILL.md content
- Different sources (obra, trailofbits, getsentry, fr33d3m0n) had complementary focuses

### What Didn't Work
- Some GitHub API calls returned 404 (URL encoding issues with spaces)
- skillsmp.com requires API key (401)
- Trail of Bits skills use `plugins/` not `skills/` in path

### Time Spent
- ~30 min gathering 12 skills
- ~15 min evaluating and synthesizing
- Total: ~45 min for research phase

### For Future Skill Discovery
1. Start with awesome-claude-skills lists as indexes
2. Focus on 10-15 skills max - diminishing returns after
3. Categorize by focus area early
4. Look for "iron laws" and "red flags" - these are the distilled wisdom

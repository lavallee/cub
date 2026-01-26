# Cub 0.30 Public Alpha Release Plan

**Status:** Draft
**Target:** v0.30.0
**Milestone:** Public Alpha (people who know what they're doing can try it out)
**Created:** 2026-01-26

---

## Guiding Principle

The threshold for 0.30 is: **someone reasonably conversant with CLI coding tools can get Cub up and running and quickly understand how to graft it into their existing workflow and get value.**

This means prioritizing:
1. Core loop reliability over new features
2. Clear documentation over comprehensive documentation
3. Working defaults over configurability
4. Honest "alpha" positioning over polish

---

## The Product Thesis (What We're Saying Cub Is)

### One-Sentence Promise
> Cub helps **solo builders** who already use AI coding harnesses make **solid, confidence-building progress** by turning fuzzy intent into **PR-ready changes** without getting trapped in **LLM thrash**.

### The Core Insight
We're in an era of **code generation abundance**. The bottleneck has shifted from "how do we generate code?" to:
- Is it **worth making**?
- Is it the **right thing**?
- Does it **work properly**?
- Does it **fit** what users want?

Cub is not primarily a faster code generator—it's the **workflow + artifact layer** that reduces entropy at the beginning and end of AI-assisted development so the builder can keep moving forward.

### The "Never Again" Problem
**LLM thrash:** repeated cycles where the model redoes/undoes work, leaves components broken, and makes progress feel illusory.

Thrash modes Cub is designed against:
- Requirement/spec drift and "interpretation creep"
- Partial implementations and placeholders that accumulate
- Regressions from local fixes breaking adjacent areas
- Tests being "made to pass" rather than validating behavior
- Context loss across sessions
- Overengineering / reinventing wheels

### Messaging Hooks (Working)
- "Stop babysitting agents. Start shipping."
- "From fuzzy intent to PR-ready—with receipts."
- "Make one confident change at a time."
- "Less thrash, more progress."
- "Work ahead of your AI coding agents, then let them run."

---

## The 15 Attributes: Alpha vs Future

The rationale document defines 15 attributes that Cub should embody. Here's how they map to alpha delivery vs future roadmap:

### Delivering in Alpha (0.30)

| # | Attribute | Alpha Delivery | Evidence |
|---|-----------|----------------|----------|
| **1** | **Reliable and Predictable** | ✅ Core | Deterministic control layer, iteration limits, budget caps, clean state enforcement |
| **2** | **Economical** | ✅ Core | Per-task model selection, budget management, token tracking |
| **3** | **Configurable and Extendable** | ✅ Partial | Global + project config, hooks system (8 lifecycle points) |
| **4** | **Observable** | ✅ Core | Structured JSONL logging, artifact bundles per task, dashboard |
| **6** | **Composable** | ✅ Core | Works alongside direct harness use, doesn't demand exclusive control |
| **8** | **Organized** | ✅ Core | Consistent artifact locations, predictable project structure |
| **9** | **Comprehensive and Holistic** | ✅ Partial | prep → run → PR pipeline exists; can use parts independently |
| **10** | **Vertically Integrated** | ✅ Core | Batteries-included prompts/templates, repo-centric model |
| **11** | **Intuitive** | ✅ Focus area | CLI consistency, helpful --help, logical command names |
| **15** | **Easy Things Easy, Hard Things Possible** | ⚠️ Gap | Need `cub quick` mode to make simple tasks simple |

### Foundations Laid, Not Fully Realized (Alpha)

| # | Attribute | Alpha State | What's Missing |
|---|-----------|-------------|----------------|
| **5** | **Collaborative** | 🔶 Partial | Human handoff UX exists but rough; needs polish |
| **13** | **Self-Healing** | 🔶 Partial | Retry logic exists; stagnation detection (circuit breaker) not shipped |
| **14** | **Alignable** | 🔶 Partial | Guardrails exist; constitution files concept not formalized |

### Deferred to Post-Alpha

| # | Attribute | Why Defer |
|---|-----------|-----------|
| **7** | **Proactive** | Daemon/expediter mode is post-alpha scope |
| **12** | **Self-Learning** | Automatic prompt mutation needs safety work first |

---

## Value Propositions: Alpha vs V1

### V1 Win (The Alpha Promise)
> In a short working session, Cub should reliably help the user produce **one solid piece of progress** that feels safe to move forward with—ideally to a **PR-ready** state.

### Confidence Signals We Must Deliver (Alpha)

| Signal | Alpha Status | Work Needed |
|--------|--------------|-------------|
| Clear written **intent** (what/why) attached to the change | ✅ | Via prep pipeline + task artifacts |
| A **bounded plan** (what will change + what won't) | ⚠️ Partial | Envelope enforcement exists; needs docs clarity |
| A reviewable **diff** with human-readable summary | ✅ | `summary.md` + `changes.patch` in artifacts |
| **Automated checks** (tests/lint/build) + report | ✅ | Verification runs; results in artifacts |
| **Regression surface** called out | ⚠️ Partial | Files touched logged; "areas affected" summary not explicit |
| **Traceability**: intent → tasks → commits → outputs | ✅ | Task IDs in commits; artifact bundles link back |

### Anti-Thrash Guardrails (Core Differentiator)

| Guardrail | Alpha Status | Notes |
|-----------|--------------|-------|
| **Bounded change envelope** | ⚠️ Implicit | Via task scope; explicit envelope declaration not enforced |
| **Soft-disjoint task envelopes** | 🔴 Not yet | V1 scope item; warn on overlap |
| **INTEGRATION task pattern** | 🔴 Not yet | V1 scope item; suggested when cross-envelope touch detected |
| **Redo/undo pattern detection** | 🔴 Not yet | Would be part of circuit breaker |
| **Budget limits** | ✅ | Wall-time and token budgets implemented |

**Decision point:** How much anti-thrash do we need for alpha? Recommendation: Budget limits + iteration limits are the alpha floor. Explicit envelope enforcement can be V1.

---

## Current State Assessment

### What's Working Well
- Core `cub run` loop with Claude/Codex/Gemini/OpenCode harnesses
- `cub plan` pipeline (orient → architect → itemize → stage)
- Task backends (beads, JSON)
- Git workflow integration (auto-branching, commits, clean state)
- Hooks system (8 lifecycle points)
- Budget management with limits/warnings
- Structured JSONL logging
- Dashboard (kanban aggregation)
- 53% test coverage with CI on 4 Python versions × 2 OS

### Known Gaps (from your notes + pain points)
- Beads backend complexity for small/medium projects
- Untested experimental features (sandbox)
- Docs may be out of sync with code
- No "quick task" path that skips full prep pipeline
- Stagnation detection not implemented (planned: circuit breaker)

---

## The Line: Alpha vs Defer

### MUST HAVE for 0.30 (Alpha Gate)

#### 1. Installation & Onboarding
| Item | Status | Work Needed |
|------|--------|-------------|
| `install.sh` resilient to missing deps | Partial | Test more scenarios, improve fallback messaging |
| `cub init` works cleanly | Done | Validate templates are current |
| `cub doctor` diagnoses common issues | Done | Add more checks for harness availability |
| `cub docs` command to launch docs in browser | Missing | New command (~30 min) |
| Clear error messages when harness unavailable | Partial | Audit harness detection errors |

#### 2. Core Loop Reliability
| Item | Status | Work Needed |
|------|--------|-------------|
| `cub run` completes without crashes | Done | Regression testing |
| `cub run --once` for single-task mode | Done | - |
| Clean exit on Ctrl+C | Verify | Test signal handling |
| Budget limits actually stop execution | Done | - |
| Iteration limits prevent runaway | Done | - |

#### 3. Task Management
| Item | Status | Work Needed |
|------|--------|-------------|
| JSON backend as default (flip from beads) | Decision | Change default, update docs |
| `cub task create/list/show/close` work | Done | - |
| `cub status` shows meaningful state | Done | - |
| Dependencies respected in task selection | Done | - |

#### 4. Documentation
| Item | Status | Work Needed |
|------|--------|-------------|
| README reflects current commands | Partial | Audit against `cub --help` |
| Quick Start actually works | Verify | End-to-end walkthrough test |
| UPGRADING.md for users of prior versions | Done | - |
| CONTRIBUTING.md accurate | Verify | Check against current architecture |
| Mark experimental features clearly | Missing | Add warnings to sandbox, toolsmith |
| Security/permissions warning prominent | Partial | Add to README intro section |

#### 5. Alpha-Appropriate Polish
| Item | Status | Work Needed |
|------|--------|-------------|
| `Development Status :: 3 - Alpha` classifier | Missing | Add to pyproject.toml |
| Pre-release versioning (0.30.0a1, etc.) | Not yet | Adopt for alpha testing |
| Helpful `--help` text on all commands | Partial | Audit Typer help strings |
| Consistent error message format | Partial | Audit error handling |

#### 6. Critical Bug Fixes
| Item | Status | Work Needed |
|------|--------|-------------|
| Beads backend reliability issues | Known | Document workarounds, or fix |
| Any blocking bugs in GitHub issues | TBD | Triage current issues |

### SHOULD HAVE (Strong preference, but not blocking)

#### Quality & Reliability
| Item | Spec | Notes |
|------|------|-------|
| Circuit Breaker / Stagnation Detection | `planned/circuit-breaker.md` | High value for preventing wasted iterations |
| Receipt-Based Gating | `planned/receipt-based-gating.md` | Like guardrails, straightforward |
| Re-anchoring Mechanism | `planned/re-anchoring.md` | Improves context management |

#### Developer Experience
| Item | Notes |
|------|-------|
| `cub quick <description>` for single tasks | Skip prep pipeline for simple work |
| Better "what's the agent thinking?" visibility | Pain point #3 from analysis |
| `cub analyze` for existing codebases | Your public-alpha-notes.md |

#### Testing & Release
| Item | Notes |
|------|-------|
| TestPyPI upload before final release | Verify packaging works |
| Release signing (GPG) | Best practice, but can defer |
| Codecov badge in README | Nice to have |

### CAN DEFER (Post-Alpha)

| Feature | Spec | Why Defer |
|---------|------|-----------|
| Multi-Model Review | `planned/multi-model-review.md` | Depends on harness abstraction work |
| Sandbox Mode | `planned/sandbox-mode.md` | Untested, high complexity |
| Workflow Management | `researching/workflow-management.md` | Still in research |
| PM Workbench | `researching/pm-workbench.md` | Vision doc, needs scoping |
| Tool Marketplace | `researching/tool-marketplace.md` | Post-alpha community feature |
| Knowledge Retention System | `researching/knowledge-retention-system.md` | Research phase |
| Language Migration (Go) | `planned/language-migration.md` | Parallel track, not blocking |
| Runs Analysis | `planned/runs-analysis.md` | Nice-to-have observability |
| Verification Integrations | `planned/verification-integrations.md` | Per-repo customization |
| Fresh Context Mode | `planned/fresh-context-mode.md` | Optimization, not core |
| Dual-Condition Exit | `planned/dual-condition-exit.md` | Can use existing iteration limits |

---

## Action Items by Category

### Category A: Documentation & Positioning (Est: 1-2 days)

1. **Audit README.md against `cub --help`**
   - Ensure all documented commands exist
   - Remove references to deprecated/renamed commands
   - Add alpha disclaimer at top

2. **Add prominent security/permissions warning**
   - "This tool runs AI agents with `--dangerously-skip-permissions`"
   - "Recommended for isolated environments / solo developers"

3. **Mark experimental features**
   - Add `[EXPERIMENTAL]` to sandbox commands help text
   - Add `[EXPERIMENTAL]` to toolsmith commands help text
   - Consider hiding from default `--help` (use `--all` to show)

4. **Create `cub docs` command**
   - Opens docs site in browser
   - Falls back to local README if offline

5. **Add alpha classifier to pyproject.toml**
   ```toml
   classifiers = [
       "Development Status :: 3 - Alpha",
       "Environment :: Console",
       "Intended Audience :: Developers",
       "License :: OSI Approved :: MIT License",
       "Programming Language :: Python :: 3.10",
       ...
   ]
   ```

### Category B: Installation & Onboarding (Est: 1-2 days)

1. **Test install.sh in more scenarios**
   - Fresh Ubuntu (no Python, no pipx)
   - macOS with Homebrew Python
   - System with only Python 3.9 (should fail gracefully)
   - Already has uv installed
   - Already has pipx installed

2. **Improve error messages**
   - When no harness is detected
   - When beads CLI is missing but beads backend selected
   - When git is not initialized

3. **Add `cub doctor` checks**
   - Verify at least one harness available
   - Check Python version compatibility
   - Verify templates are current

### Category C: Core Reliability (Est: 2-3 days)

1. **Decide on default task backend**
   - Recommendation: JSON for simplicity in alpha
   - Document beads as "advanced" option
   - Update `cub init` default

2. **Audit signal handling**
   - Test Ctrl+C during `cub run`
   - Test Ctrl+C during `cub plan`
   - Ensure clean exit without data corruption

3. **Audit error handling consistency**
   - Use Rich console for error output
   - Consistent exit codes
   - Helpful suggestions in error messages

4. **End-to-end smoke test**
   - Create test project
   - Run full `cub plan` → `cub run` cycle
   - Verify artifacts are created correctly

### Category D: Should-Have Features (Est: 3-5 days if included)

1. **Circuit Breaker** (if included)
   - Implement stagnation detection
   - Configurable thresholds
   - Clear messaging when circuit trips

2. **Quick Task Mode** (if included)
   - `cub quick "fix the typo in README"`
   - Creates task, runs once, cleans up
   - Skips full prep pipeline

3. **Receipt-Based Gating** (if included)
   - Similar pattern to guardrails
   - Require evidence before task completion

### Category E: Release Process (Est: 1 day)

1. **Pre-release testing**
   - Build package locally
   - Test install from wheel
   - Upload to TestPyPI
   - Install from TestPyPI and verify

2. **Tag and release**
   - Use alpha versioning: `0.30.0a1`
   - Create GitHub release with notes
   - Publish to PyPI

3. **Post-release**
   - Announce (if desired)
   - Monitor for install issues
   - Quick patch releases as needed (0.30.0a2, etc.)

---

## Recommended Prioritization

### Phase 1: Foundation (0.28 → 0.29)
Focus: Make what exists reliable and documented

1. Documentation audit & fixes
2. Installation testing & hardening
3. Default to JSON backend
4. Add alpha classifiers
5. Mark experimental features
6. `cub docs` command

### Phase 2: Reliability (0.29 → 0.30a1)
Focus: Core loop confidence

1. Signal handling audit
2. Error handling consistency
3. End-to-end smoke tests
4. Circuit breaker (if time permits)

### Phase 3: Release (0.30a1)
Focus: Ship it

1. TestPyPI validation
2. Final documentation pass
3. Tag and publish
4. Monitor and patch

---

## Decisions (Resolved)

| Question | Decision | Rationale |
|----------|----------|-----------|
| **Default task backend** | ✅ JSON (flip from beads) | Simpler for alpha users, fewer dependencies. Beads becomes "advanced" opt-in. |
| **Circuit Breaker in alpha?** | ✅ Yes, explore/spike | High value for preventing wasted iterations. Explore clean run looping too. |
| **TestPyPI first?** | ✅ Yes | Validate packaging before PyPI. TestPyPI for 0.30.0a1. |
| **Beads reliability issues** | ✅ Default to JSON | Don't block alpha on beads fixes. Document beads as opt-in. |
| **Public announcement?** | ✅ Quiet (friends & family) | Quality threshold: users can get far enough to give useful feedback. Broader announce at beta. |
| **Claude Tasks integration** | 🔶 Spike for alpha | Explore what symbiotic integration looks like. May punt implementation to post-alpha. |

---

## Spikes & Explorations

### Spike 1: Claude Tasks Integration

**Goal:** Understand how Cub can work symbiotically with Claude's new Tasks feature.

**Questions to answer:**
- What does the Claude Tasks API/interface look like?
- Can Cub tasks map to/from Claude Tasks?
- Can we detect when someone is working in Claude directly and capture that context?
- What's the handoff model: Cub → Claude Task → Cub picks up results?
- How does this affect artifact collection and traceability?

**Possible integration points:**
1. **Export to Claude Tasks**: `cub export --to-claude-task` creates a Claude Task from a cub task
2. **Import from Claude Tasks**: Capture completed Claude Task work back into cub artifacts
3. **Hybrid mode**: Cub orchestrates, but individual tasks can be "handed off" to Claude Tasks for interactive work
4. **Session awareness**: Detect active Claude Code sessions and coordinate (don't fight for the same files)

**Spike deliverable:** Decision doc on whether/how to integrate for alpha vs post-alpha.

### Spike 2: Circuit Breaker & Clean Run Looping

**Goal:** Implement stagnation detection and clean multi-run looping.

**Circuit breaker triggers:**
- Same files modified N times in succession without test improvement
- Token burn rate exceeds threshold without progress
- Same error pattern repeated N times
- No task state changes for N iterations

**Clean run looping:**
- After a run completes (success or budget exhaustion), what's the UX for "continue"?
- Should there be a `cub continue` or `cub run --resume`?
- How do we persist state across runs for circuit breaker detection?

**Spike deliverable:** Working implementation or clear defer decision with spec for post-alpha.

### Spike 3: Symbiotic Workflow (Cub + Direct Harness Use)

**Goal:** Define and test the model where someone uses Cub for structure but also works directly in Claude Code/Codex.

**Current state:**
- Cub can run alongside direct harness use (composable attribute)
- But no explicit coordination or artifact capture from direct sessions

**Questions:**
- How does someone doing direct Claude Code work in a cub-enabled project get their work "counted"?
- Can we detect and log direct harness sessions?
- Should `cub capture` have a mode for "I just did some work manually, record it"?
- What about Claude Code's `--resume` and session continuity?

**Possible approaches:**
1. **Git-based detection**: Watch for commits not made by cub, prompt to associate with task
2. **CLAUDE.md integration**: Cub writes context to CLAUDE.md that direct sessions pick up
3. **Post-hoc reconciliation**: `cub reconcile` command that reviews recent commits and associates with tasks
4. **Hook into harness**: Use Claude Code hooks (if available) to notify cub of sessions

**Spike deliverable:** Recommended approach for alpha (even if minimal) + roadmap for deeper integration.

---

## Success Criteria for 0.30

An alpha release is successful if:

1. **Install works** on fresh Ubuntu and macOS machines
2. **Quick Start** in README produces working output
3. **`cub run`** completes a multi-task epic without crashing
4. **Documentation** accurately describes what the tool does
5. **Error messages** help users diagnose problems
6. **No known data loss bugs** (task state, git state)

---

## Appendix: Standards Reference

Based on research into open source release best practices:

### From [libresource/open-source-checklist](https://github.com/libresource/open-source-checklist)
- [x] Good project name
- [x] Mission statement (README intro)
- [x] Features list
- [x] Development status (need to add alpha classifier)
- [x] Download page (GitHub releases)
- [x] Version control (GitHub)
- [x] Bug tracker (GitHub Issues)
- [ ] Communication channels (consider Discussions)
- [x] Contributing guide
- [x] User documentation
- [x] Developer documentation
- [x] License (MIT)
- [ ] Code of Conduct (consider adding)
- [ ] Security policy (consider adding)
- [x] Issue templates (check if exist)
- [x] Tests
- [ ] Test coverage badge

### From [Python Packaging Guide](https://packaging.python.org/en/latest/discussions/versioning/)
- [ ] Alpha version format (0.30.0a1)
- [ ] Pre-release classifier
- [ ] TestPyPI validation before PyPI

### From [CLI Guidelines](https://clig.dev/)
- [x] Helpful `--help` output
- [x] Consistent command structure
- [ ] Audit error messages for helpfulness
- [ ] Consider shell completions (post-alpha)

---

## Marketing & Communications Plan

### Philosophy: Build in Public, Ship Artifacts

The alpha release is an opportunity to:
1. **Refine the value prop language** through real-world testing
2. **Generate reusable content** (blog posts, threads, demos)
3. **Build credibility** before wider announcement
4. **Attract early adopters** who can provide feedback

### Target Audience for Alpha

**Primary:** Solo builders who:
- Already use AI coding harnesses (Claude Code, Codex, Cursor, Aider)
- Are comfortable in a terminal but not necessarily CLI power users
- Feel overwhelmed keeping agents "fed" with coherent work
- Have experienced LLM thrash and want to avoid it

**Secondary:** Technical content creators who cover AI dev tools

### Content Artifacts to Create

#### Tier 1: Must Have for Alpha (ship with release)

| Artifact | Purpose | Status |
|----------|---------|--------|
| **README with clear value prop** | First impression, conversion | Needs update |
| **Quick Start that actually works** | Time-to-first-value | Verify end-to-end |
| **`cub --help` that tells the story** | In-product marketing | Audit needed |
| **GitHub release notes** | Changelog + positioning | Template ready |

#### Tier 2: Alpha Launch Content (first 2 weeks)

| Artifact | Purpose | Notes |
|----------|---------|-------|
| **Blog post: "Why I built Cub"** | Origin story, philosophy | Draw from rationale doc |
| **Blog post: "The LLM Thrash Problem"** | Problem framing, establish expertise | Use hair-on-fire examples |
| **Twitter/X thread: Launch announcement** | Reach, shareability | Concise, visual |
| **Demo video: 5-min "first run"** | Reduce friction, show don't tell | Screen recording + voiceover |
| **Demo video: "prep to PR" workflow** | Show full value prop | Can be longer (10-15 min) |

#### Tier 3: Ongoing Content (post-alpha)

| Artifact | Purpose | Notes |
|----------|---------|-------|
| **"Building Cub with Cub"** series | Dogfooding credibility | Use actual cub runs |
| **Comparison posts** | SEO, positioning | vs raw Claude Code, vs Cursor, etc. |
| **User stories / testimonials** | Social proof | Collect from early adopters |
| **Technical deep dives** | Attract power users | Harness abstraction, hooks system |

### Key Messages to Test

| Message | Hypothesis | How to Test |
|---------|------------|-------------|
| "Stop babysitting agents" | Resonates with frustration | Social engagement |
| "PR-ready with receipts" | Appeals to review anxiety | Landing page conversion |
| "Work ahead, then step back" | Captures the prep→run flow | Demo completion rate |
| "Less thrash, more progress" | Simple, memorable | Word-of-mouth tracking |

### Channels

| Channel | Alpha Strategy | Notes |
|---------|----------------|-------|
| **GitHub** | Primary home; README, releases, discussions | Enable Discussions for community |
| **Personal blog** | Long-form content | Cross-post to dev.to, Hashnode |
| **Twitter/X** | Threads, updates, engagement | Build in public style |
| **Reddit** | r/LocalLLaMA, r/ClaudeAI, r/ChatGPTCoding | Share genuinely, don't spam |
| **Hacker News** | One "Show HN" post when ready | Time for maximum engagement |
| **YouTube** | Demo videos | Unlisted for alpha, public for beta |

### Content Production Plan

#### Pre-Alpha (this week)
- [ ] Write "Why I built Cub" draft (can refine later)
- [ ] Outline "LLM Thrash Problem" post
- [ ] Update README value prop section
- [ ] Create release notes template

#### Alpha Launch (0.30.0a1)
- [ ] Publish GitHub release with notes
- [ ] Twitter thread (soft launch)
- [ ] Reddit post in 1-2 relevant subs
- [ ] Record quick demo video (5 min)

#### Post-Alpha (0.30.0a2+)
- [ ] Publish blog posts
- [ ] Full demo video
- [ ] Collect feedback, iterate on messaging
- [ ] Prepare for beta announcement

### Metrics to Track

| Metric | Tool | Why It Matters |
|--------|------|----------------|
| GitHub stars | GitHub | Vanity but signals interest |
| PyPI downloads | PyPI stats / pepy.tech | Actual usage |
| GitHub issues opened | GitHub | Engagement, feedback quality |
| Time to first successful run | User feedback | Onboarding friction |
| Blog post engagement | Analytics | Message resonance |
| Social mentions | Search / alerts | Word of mouth |

### Voice and Tone Guidelines

**Do:**
- Be honest about alpha status and limitations
- Share the "why" and philosophy, not just features
- Acknowledge the rapidly evolving landscape
- Credit inspirations (beads, Ralph Wiggum loop, etc.)
- Use concrete examples and real outputs

**Don't:**
- Overpromise or hype
- Position as "better than X" (position as "different approach")
- Hide limitations or experimental status
- Use jargon without explanation
- Claim to solve problems we haven't validated

### The "Steam to Electric" Narrative

From the rationale doc, there's a powerful framing:

> "Even though there are other factors... the scale of change when it comes to making software is as great as steam to electric. It makes sense to start from first principles and start from scratch."

This positions Cub not as an incremental improvement but as a rethinking of the workflow for an era of code generation abundance. Use this framing sparingly (it's bold) but it's compelling for the right audience.

---

## Artifacts Inventory

### Existing Docs to Leverage

| Doc | Location | Use For |
|-----|----------|---------|
| Rationale & 15 Attributes | `sketches/notes/rationale-and-feature-transcription.txt` | Blog content, philosophy |
| Product Thesis | `sketches/notes/product-thesis.md` | Value prop language |
| V1 Scope | `sketches/notes/v1-scope.md` | Feature prioritization |
| Pain Points Map | `sketches/pain-points-map.md` | Problem framing content |
| Hair-on-Fire Instances | `sketches/notes/hair-on-fire-instances.md` | Concrete examples for content |
| Feature Narrative | `sketches/notes/feature_narrative.md` | Feature explanations |

### Content to Create

| Content | Source Material | Priority |
|---------|-----------------|----------|
| README value prop rewrite | product-thesis.md | Alpha gate |
| "Why Cub" blog post | rationale doc | Tier 2 |
| "LLM Thrash" explainer | hair-on-fire + pain-points | Tier 2 |
| Demo script | README quick start | Tier 2 |
| Twitter launch thread | product-thesis messaging hooks | Alpha launch |

---

## Human Testing Plan

The goal is to validate that each component works reliably before alpha. This goes beyond automated tests to include real-world usage scenarios.

### Testing Philosophy

1. **Test on real projects** — Not just toy apps. Use existing GitHub repos.
2. **Test the full flow** — Not just individual commands in isolation.
3. **Test failure modes** — What happens when things go wrong?
4. **Test as a new user** — Fresh install, minimal context.
5. **Document issues found** — Every failure is a bug or a docs gap.

### Test Matrix: Commands & Components

#### Installation & Setup

| Test Case | Steps | Expected | Status |
|-----------|-------|----------|--------|
| Fresh Ubuntu install | `curl -LsSf https://install.cub.tools \| bash` on fresh Ubuntu VM | Installs successfully, `cub --version` works | ⬜ |
| Fresh macOS install | Same on fresh macOS | Installs successfully | ⬜ |
| Python 3.9 rejection | Run installer on system with only Python 3.9 | Clear error message about Python version | ⬜ |
| Upgrade existing | Run installer when cub already installed | Upgrades cleanly, preserves config | ⬜ |
| `cub init` in empty dir | `mkdir test && cd test && cub init` | Creates prd.json, PROMPT.md, AGENT.md | ⬜ |
| `cub init` in existing git repo | Clone a repo, run `cub init` | Initializes without breaking repo | ⬜ |
| `cub init --global` | Run on fresh system | Creates ~/.config/cub/, ~/.local/share/cub/ | ⬜ |
| `cub doctor` | Run after init | Reports system status, detects harness | ⬜ |

#### Task Management (JSON Backend)

| Test Case | Steps | Expected | Status |
|-----------|-------|----------|--------|
| Create task | `cub task create "Fix the bug" --type bug --priority 2` | Task created with ID | ⬜ |
| List tasks | `cub task list` | Shows created task | ⬜ |
| Show task | `cub task show <id>` | Displays task details | ⬜ |
| Update task | `cub task update <id> --priority 1` | Priority updated | ⬜ |
| Close task | `cub task close <id>` | Status changes to closed | ⬜ |
| Task dependencies | Create task B depending on A, verify A must close first | Dependency respected | ⬜ |
| `cub status` | After creating tasks | Shows task counts, ready tasks | ⬜ |
| `cub status --json` | Same | Valid JSON output | ⬜ |

#### Plan Pipeline

| Test Case | Steps | Expected | Status |
|-----------|-------|----------|--------|
| `cub plan` full flow | Run on project with a feature idea | Completes orient → architect → itemize → stage | ⬜ |
| `cub plan orient` | Run with a spec or idea | Produces orientation.md | ⬜ |
| `cub plan architect` | After orient | Produces architecture.md | ⬜ |
| `cub plan itemize` | After architect | Produces itemized-plan.md with tasks | ⬜ |
| `cub stage` | After plan complete | Tasks imported to backend | ⬜ |
| Plan with existing spec | Point plan at a markdown spec file | Uses spec as input | ⬜ |

#### Run Loop (Core)

| Test Case | Steps | Expected | Status |
|-----------|-------|----------|--------|
| `cub run --once` | With one ready task | Picks task, runs harness, completes or fails | ⬜ |
| `cub run` full loop | With 3-5 tasks in an epic | Runs until all complete or budget exhausted | ⬜ |
| `cub run --epic <id>` | With multiple epics | Only runs tasks in specified epic | ⬜ |
| `cub run --stream` | Any run | Shows streaming output from harness | ⬜ |
| `cub run --debug` | Any run | Shows full prompts, command lines | ⬜ |
| Budget exhaustion | Set low budget, run | Stops cleanly when budget exceeded | ⬜ |
| Iteration limit | Set low max_iterations | Stops cleanly at limit | ⬜ |
| Ctrl+C during run | Press Ctrl+C mid-task | Clean exit, no data corruption | ⬜ |
| Task failure | Task that will fail (bad code) | Marks failed, continues or stops per config | ⬜ |
| Retry on failure | Configure retry mode | Retries with failure context | ⬜ |

#### Harness Integration

| Test Case | Steps | Expected | Status |
|-----------|-------|----------|--------|
| Claude harness | `cub run --harness claude` | Uses Claude Code | ⬜ |
| Codex harness | `cub run --harness codex` | Uses Codex CLI | ⬜ |
| Auto-detection | Don't specify harness | Detects available harness | ⬜ |
| Per-task model | Label task with `model:haiku` | Uses specified model | ⬜ |
| Harness not available | Specify unavailable harness | Clear error message | ⬜ |

#### Git Integration

| Test Case | Steps | Expected | Status |
|-----------|-------|----------|--------|
| Auto-branch creation | Run with auto-branch hook | Creates branch like `cub/session/timestamp` | ⬜ |
| Commit per task | Complete a task | Commit with task ID in message | ⬜ |
| Clean state check | Run with uncommitted changes | Warns or blocks per config | ⬜ |
| `cub branch <epic>` | Create branch for epic | Branch created and bound | ⬜ |
| `cub branches` | After creating branches | Lists branch-epic bindings | ⬜ |
| `cub pr <epic>` | After completing epic | Creates PR with template | ⬜ |

#### Artifacts & Observability

| Test Case | Steps | Expected | Status |
|-----------|-------|----------|--------|
| Artifact bundle created | Complete a task | `.cub/runs/{session}/tasks/{id}/` contains task.json, summary.md, changes.patch | ⬜ |
| `cub artifacts` | After run | Lists artifacts | ⬜ |
| `cub artifacts <id>` | With task ID | Shows specific task artifacts | ⬜ |
| JSONL logs created | After run | `~/.local/share/cub/logs/{project}/{session}.jsonl` exists | ⬜ |
| Log contains expected events | Inspect log | task_start, task_end events with correct data | ⬜ |

#### Hooks System

| Test Case | Steps | Expected | Status |
|-----------|-------|----------|--------|
| pre-loop hook | Create hook, run | Hook executes before loop | ⬜ |
| post-task hook | Create hook, complete task | Hook executes after task | ⬜ |
| on-error hook | Create hook, fail a task | Hook executes on failure | ⬜ |
| Hook receives env vars | Check hook output | CUB_TASK_ID, CUB_EXIT_CODE present | ⬜ |
| Hook failure handling | Hook that exits non-zero | Logged, doesn't stop run (default) | ⬜ |

#### Dashboard

| Test Case | Steps | Expected | Status |
|-----------|-------|----------|--------|
| `cub dashboard sync` | After some runs | Builds dashboard DB | ⬜ |
| Dashboard serves | `uvicorn cub.core.dashboard.api.app:app` | Opens in browser | ⬜ |
| Kanban shows tasks | Load dashboard | Tasks appear in correct columns | ⬜ |

### Real-World Project Tests

Beyond command-level testing, we need to validate cub works on real projects.

#### Test Project 1: Cub Itself (Dogfooding)

| Scenario | Steps | Expected |
|----------|-------|----------|
| Add a small feature | Use cub plan → run to add `cub docs` command | Feature implemented, tests pass |
| Fix a bug | Use cub to fix a known issue | Bug fixed, no regressions |
| Multi-task epic | Plan and execute a 5-task epic | All tasks complete, PR ready |

#### Test Project 2: External Python Project

Pick a well-known open source Python project (e.g., `httpx`, `rich`, or a smaller utility).

| Scenario | Steps | Expected |
|----------|-------|----------|
| Initialize cub | Clone repo, `cub init` | Initializes without issues |
| Add a feature | Plan a small feature, run | Feature implemented or clear failure |
| Run tests | Verify cub runs project's test suite | Tests pass (or cub reports failures correctly) |

#### Test Project 3: External Non-Python Project

Pick a JavaScript/TypeScript or Go project.

| Scenario | Steps | Expected |
|----------|-------|----------|
| Initialize cub | Clone repo, `cub init` | Works with non-Python project |
| Simple task | Create and run a simple task | Harness handles language correctly |

#### Test Project 4: Fresh "Greenfield" Project

Start from nothing and use cub to build something small.

| Scenario | Steps | Expected |
|----------|-------|----------|
| Project from idea | "Build a CLI that converts markdown to HTML" | Cub preps, plans, implements |
| Full lifecycle | Idea → tasks → code → tests → PR | End-to-end works |

### Edge Cases & Failure Modes

| Test Case | Steps | Expected |
|-----------|-------|----------|
| No internet | Disconnect, try to run | Clear error, no crash |
| API key missing | Unset ANTHROPIC_API_KEY, run | Clear error about auth |
| Disk full | Fill disk, try to run | Graceful failure, no corruption |
| Very large repo | Run on large codebase (e.g., VSCode) | Doesn't hang or OOM |
| Unicode in task titles | Create task with emoji/unicode | Handles correctly |
| Long-running task | Task that takes 10+ minutes | Doesn't timeout unexpectedly |
| Concurrent runs | Two terminals, both `cub run` | Either locks or coordinates cleanly |

### Testing Checklist

Before declaring alpha-ready:

- [ ] All "Installation & Setup" tests pass
- [ ] All "Task Management" tests pass
- [ ] All "Run Loop" tests pass
- [ ] At least one harness integration test passes
- [ ] Git integration tests pass
- [ ] Artifact creation tests pass
- [ ] At least one real-world project test completes successfully
- [ ] No critical edge case failures
- [ ] All failures have clear error messages

### Issue Tracking

During testing, create GitHub issues for:
- Any crash or data loss
- Any confusing error message
- Any doc that doesn't match reality
- Any "this should be easier" friction point

Tag issues with `alpha-blocker` if they must be fixed before release.

---

## Next Steps

1. ~~Review this plan~~ ✅
2. ~~Make decisions on open questions~~ ✅ (Resolved above)
3. **Execute spikes** — Claude Tasks, Circuit Breaker, Symbiotic Workflow
4. **Run human testing plan** — Start with Installation & Setup
5. **Break remaining work into tasks** — Use cub to track cub alpha work
6. **Set target date** for 0.30.0a1
7. **Draft "Why I built Cub" post** — Can refine during alpha
8. **Update README value prop** — Use product thesis language

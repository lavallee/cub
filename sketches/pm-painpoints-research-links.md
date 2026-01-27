# PM pain points in the AI era — research links + extracted themes

Captured: 2026-01-26

Goal: gather public examples (blog posts, forums, practitioner writeups) that surface **PM-specific** pain points when building LLM/agent products, and translate them into Cub-relevant opportunities.

---

## Sources (public)

### 1) “How to Write Product Requirement Docs (PRDs) in the AI Era” (Aakash newsletter, 2025-08-16)
- URL: https://www.news.aakashg.com/p/ai-prd
- Key quoted pain point:
  - "PMs started using LLMs to create overly long PRDs that said nothing" (the classic *spec bloat / low signal* problem).
- Also frames what prototypes *don’t* specify (i.e., what PM work remains):
  - hypothesis of the change
  - fit within overall strategy
  - rollout plan (A/B vs full)
  - passing metrics for graduation
  - non-goals / side effects

### 2) “A Proven AI PRD Template” (Product Compass / Miqdad Jaffer, 2025-03-26)
- URL: https://www.productcompass.pm/p/ai-prd-template
- Key framing:
  - AI PRD as core alignment tool across strategy → planning → dev → GTM.
  - "continuous PRM mode" (continuous product review mindset): every interaction is a chance to test assumptions around value/usability/viability/feasibility.
- Practical AI/PM traps called out:
  - shipping AI without justified business case
  - missing AI-specific considerations / guardrails
  - relying on gut feel vs hard data

### 3) Prompt/prompt-regression ecosystem (PromptLayer blog roundup, 2025-01-16)
- URL: https://blog.promptlayer.com/5-best-tools-for-prompt-versioning/
- Surfaces a PM-adjacent pain point category:
  - prompt versioning + evaluation + regression prevention using historical datasets
  - observability: cost, latency, logs
  - collaboration with non-technical stakeholders

### 4) Hacker News threads (proxy for forum evidence)
- “PMs: How Are You Monitoring Your LLM Chatbot?” (Ask HN)
  - URL: https://news.ycombinator.com/item?id=44065387
  - Key pain points raised by the prompt itself:
    - monitoring quality/behavior/output
    - which KPIs matter (hallucination rate, latency, CSAT, retention)
    - feedback loops + regression when updating prompts/models

> Note: Reddit has multiple relevant PM threads, but is blocked via web_fetch (403) from this environment.

---

## Extracted PM pain point clusters (AI product lifecycle)

### A) Spec quality degradation ("long PRDs that say nothing")
- Symptom: LLMs make it easy to produce *volume* that looks official but doesn’t help decision-making.
- Missing pieces: hypothesis, strategy fit, rollout plan, success metrics, non-goals.
- Cub opportunity:
  - spec linting / "spec signal" scoring
  - templates that force missing sections
  - explicit "non-goals" + "side effects" capture

### B) Continuous alignment vs doc theater
- Symptom: Specs are still needed as alignment artifacts, but must stay live and update with new learnings.
- Cub opportunity:
  - treat spec as a living artifact with workflow stages
  - append-only “assumptions tested” ledger attached to spec (like experiments log)

### C) Acceptance criteria for stochastic systems
- Symptom: for LLM/agent products, the output is variable, so PMs need stronger notions of desired/undesired outcomes and measurable gates.
- Cub opportunity:
  - receipt-based gating (planned) extended to product-level criteria
  - verification integrations applied to AI product evaluation suites

### D) Monitoring + regression (prompts/models)
- Symptom: prompt changes can cause silent regressions; PMs need observability and replay-based evaluation.
- Cub opportunity:
  - runs analysis (planned) expanded into “prompt run analysis”
  - dataset-based regression tests (historical interactions)

### E) Feedback triage overload (bugs + qualitative feedback)
- Symptom: too many bug reports / tickets; hard to cluster and prioritize.
- Cub opportunity:
  - capture/import pipelines that dedupe/cluster
  - “bug hydration” and severity/impact tagging

---

## Cub mapping (existing/planned) — quick notes

- Existing:
  - `cub capture` / `cub captures` / dashboard lifecycle columns
  - `cub spec` (AI-guided interview)
  - `cub plan ...` pipeline
  - `cub review --deep`
  - `cub run` with logs/ledger

- Planned:
  - receipt-based gating
  - verification integrations
  - runs analysis
  - re-anchoring / fresh context / circuit breaker
  - capture system completion

---

## Next research targets (to fill gaps)

1) PM writeups on *LLM evaluation frameworks* (qual+quant): golden sets, rubrics, human review loops.
2) Product org posts about moving from PRDs → prototypes, and the backlash (what broke).
3) "Prompt regression" case studies in production (incidents caused by prompt/model changes).
4) "Agent product requirements" discussions (what changes in PRDs/user stories when output is stochastic).

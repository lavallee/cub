# Eval + regression (PM deep dive): what practitioners are doing, and what Cub could become

Captured: 2026-01-26

This expands the PM section of the lifecycle map, focusing on **evaluation, monitoring, and regression prevention** for LLM/agent products.

It also captures a parallel framing about **PRD evolution**: PRDs historically served stakeholder alignment + CYA in big orgs; for a small team working with agents, we may only need *a thin alignment layer* for 1–2 humans + deterministic gates.

---

## 1) Evidence: what people are saying about eval + regression

### A) “Prompt regression testing” is emerging as a core discipline
**Traceloop** frames it as: prompts are versioned assets; regression tests compare prompt-v2 vs prompt-v1 on a standard dataset; gate deployments in CI/CD.
- Source: https://www.traceloop.com/blog/automated-prompt-regression-testing-with-llm-as-a-judge-and-ci-cd
- Extracted points:
  - Treat prompts like code: **versioned, tested, deployed**.
  - Need a **curated test dataset** (“golden set”), ideally derived from **production traces**.
  - “LLM-as-a-Judge” is widely used: define a **rubric**, have a judge model score outputs.
  - CI/CD gate should check not just quality, but also **latency** and **cost**.

### B) Silent model/API changes cause real regressions
**Statsig** emphasizes that even if *your* code doesn’t change, upstream LLM behavior can.
- Source: https://www.statsig.com/perspectives/slug-prompt-regression-testing
- Extracted points:
  - Silent API updates shift tone/safety/refusals mid-release.
  - “Single response checks do not cut it” → you need **slice-level distributions**.
  - Golden datasets go stale; use **fresh random samples from production**.
  - Tie prompt versions + model versions + experiment IDs + feature flags to make rollouts reversible.

### C) Hybrid approach: random sampling + a lean golden set
- Source: https://dev.to/practicaldeveloper/random-prompt-sampling-vs-golden-dataset-which-works-better-for-llm-regression-tests-1ln7
- Extracted points:
  - Random sampling finds long-tail failures; golden sets provide deterministic CI gates.
  - Drift sources: **prompt drift** + **model drift**.

---

## 2) What “eval + regression” actually means (a practical taxonomy)

### What you can regress
1) **Quality / helpfulness** (subjective but rubric-scoreable)
2) **Correctness / faithfulness** (especially for RAG)
3) **Safety / policy compliance**
4) **Tone / style consistency**
5) **Tool-use correctness** (agent uses the right tools in the right order)
6) **Latency**
7) **Cost**

### What you need to version
- Prompt(s): system prompts, templates, tool instructions
- Model + parameters
- Toolchain configuration (retriever settings, tool availability)
- Datasets: golden set + sampled production traces

### What you need to measure
- Scores and their **distribution by slice** (intent/segment/category)
- Diffs vs baseline (trend lines, not just pass/fail)

---

## 3) Cub mapping: where this fits in Cub’s worldview

Cub already has most of the *scaffolding* for an eval/regression system:
- **Artifacts + sessions** (trace-like bundles)
- **Structured logs / ledger** (a place to attach “what happened”)
- **Dashboard** (to show status and funnel work)
- **Receipt-based gating (planned)** (exactly the right primitive)
- **Verification integrations (planned)**

### Proposed “Cub Evals” concept (future)
Think of evals as *product requirements receipts*:

- A “receipt” is a machine-checkable artifact that proves a claim.
- For LLM features, a receipt might be:
  - a golden-set run summary (scores)
  - a slice-level regression report
  - a latency/cost budget report
  - a refusal/toxicity rate delta report

---

## 4) Candidate Cub additions (commands + artifacts)

### A) `cub eval` (new command family)
**Goal:** make eval/regression a first-class workflow stage, not an external dashboard.

Potential subcommands:
- `cub eval dataset add --from-ledger <run_id|task_id>` (curate a test case from artifacts)
- `cub eval dataset sample --from-prod --rate 0.01 --since 7d` (ingest recent interactions)
- `cub eval run --dataset golden --baseline v1 --candidate v2` (batch run)
- `cub eval report --by slice:intent --by segment:tier` (slice metrics)
- `cub eval gate --thresholds <yaml>` (fail/pass with tolerance bands)

Artifacts:
- `.cub/evals/datasets/*.jsonl`
- `.cub/evals/runs/<id>/*.json`
- dashboard card(s) for “EVALS / REGRESSION” (or folded into NEEDS_REVIEW)

### B) “Prompt map” / “Prompt changelog” (PM-visible)
A lightweight replacement for heavy PRDs:
- prompt families + intent + owners
- linked eval datasets
- linked rollout flags
- “what changed” explanation

### C) Regression-aware rollout workflow
- integrate with feature flags (or simple staged rollout config)
- require:
  - offline eval gate
  - online monitoring window
  - automatic rollback plan

---

## 5) PRD evolution: a small-team framing

Your take resonates: PRDs are often a byproduct of:
- many stakeholders needing alignment,
- org overhead and handoffs,
- CYA (plant a flag so decisions are defensible).

For a “1–2 humans + agents” product team, the PRD can shrink into:

1) **A thin spec** (why/what, success metrics, non-goals, constraints)
2) **A living assumptions log** (what we believe, what we tested)
3) **Deterministic gates/receipts** (offline evals, verification, budgets)

In other words:
- *Docs become smaller*, because the system’s truth is in artifacts + receipts.
- *Alignment becomes continuous*, because you can iterate cheaply.

Cub’s opportunity is to make that small-team model feel “enterprise-safe” without the bureaucracy.

---

## 6) Next research slice (to keep digging)

To deepen this, we should pull examples on:
- “LLM-as-a-judge” pitfalls + how people calibrate judges
- property-based tests for agents (asserting invariants vs string matches)
- real incident writeups: prompt/model updates causing regressions
- tooling ecosystems: Langfuse/LangSmith/Helicone case studies and their eval primitives

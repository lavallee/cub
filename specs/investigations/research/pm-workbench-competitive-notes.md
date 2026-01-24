---
created: 2026-01-24
source: toolsmith.run (mcp-official:brave-search)
purpose: Competitive analysis / prior art to help scope PM Workbench
---

# PM Workbench — Competitive / Prior Art Notes

This note captures adjacent frameworks that map closely to PM Workbench’s goals: *an “unknowns ledger” plus a recommended “next move” that reduces uncertainty cheaply.*

## 1) Opportunity Solution Trees (OST) — Teresa Torres ecosystem

OST is a visual framework for connecting:
- desired outcomes → opportunities → solutions → experiments

It maps well to PM Workbench because it:
- forces explicit articulation of **unknowns/opportunities**
- encourages **small experiments** as the next move
- emphasizes alignment and continuous discovery loops

Sources (Brave search):
- https://www.producttalk.org/opportunity-solution-trees/
- https://amplitude.com/blog/opportunity-solution-tree
- https://www.productplan.com/glossary/opportunity-solution-tree/
- https://productschool.com/blog/product-fundamentals/opportunity-solution-tree
- https://www.product-frameworks.com/Opportunity-Solution-Tree.html

## 2) Shape Up (Basecamp) — shaping + appetite + boundaries

Shape Up’s *shaping* phase is essentially “reduce unknowns and constrain the solution space” before committing.

High-signal concepts to borrow directly:
- **Appetite**: time/effort budget as a hard boundary
- **Set boundaries / where to stop**: explicitly enumerating what is *out of scope*
- **Eliminate rabbit holes**: proactively remove open questions

This maps to PM Workbench:
- Unknowns Ledger ⇢ the list of rabbit holes + open questions
- Next Move ⇢ shaping work that collapses uncertainty (clarify, decide, spike)
- Promote ⇢ shaped pitch/task brief

Sources (Brave search):
- https://basecamp.com/shapeup/0.3-chapter-01
- https://basecamp.com/shapeup/1.1-chapter-02
- https://basecamp.com/shapeup/1.2-chapter-03
- https://www.conordewey.com/blog/notes-on-shape-up/
- https://alphalist.com/blog/how-do-you-shape-up-your-product-team-s-appetite

## 3) Continuous Discovery Habits (CDH) — continuous customer touchpoints

CDH frames the practice as sustainable routines (weekly touchpoints, small learning loops) rather than big “discovery phases.”

Potential mapping:
- Unknown type `evidence` ⇢ CDH assumption-testing cadence
- Next Move `question/research` ⇢ structured customer touchpoint prompts

Sources (Brave search):
- https://www.producttalk.org/getting-started-with-discovery/
- https://evansamek.substack.com/p/summary-continuous-discovery-habits

## Suggested “Next Move” for the spec (to reduce the biggest unknown cheaply)

**Next Move:** Add a short section to `specs/researching/pm-workbench.md` called **“Borrowed primitives”** with:
- Appetite (from Shape Up)
- Outcomes→Opportunities→Solutions→Experiments chain (OST)
- Weekly touchpoint habit for evidence unknowns (CDH)

This will make the PM Workbench spec less “from scratch” and more like an intentional synthesis.

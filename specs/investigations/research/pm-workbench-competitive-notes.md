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

## Research run (2026-01-24T14:32:17.135706+00:00)
Tool: `mcp-official:brave-search`

### Query: product discovery framework next step uncertainty reduction
- Status: OK
- Artifact: `/home/lavallee/clawdbot/cub/.cub/toolsmith/runs/20260124-143213-mcp-official_brave-search.json`

- Product Discovery: ​A Practical In-depth Guide for Product Teams
  - https://herbig.co/product-discovery/
  - This is why frameworks like simple Effort-Impact-Scoring fall short—because you don’t know what kind of solution you should rate. I prefer a different grading: Product Discovery Priorities should be defined along the lines of Impact and Uncertainty · By evaluating the uncertainty, you get a much clearer picture about which ideas you need to further explore during Product Discovery. The area on the upper right includes your next targets to evaluate.
- Guide: Product Discovery Process & Techniques | Productboard
  - https://www.productboard.com/blog/step-by-step-framework-for-better-product-discovery/
  - Productboard uses the Double Diamond approach for conducting product discovery, structured as follows: ... Let’s break down each piece step-by-step.
- 9 Most Effective Product Discovery Frameworks with Examples - 9 Most Effective Product Discovery Frameworks with Examples
  - https://codewave.com/insights/product-discovery-framework-examples-techniques/
  - Discovery frameworks address these challenges by establishing clear validation processes: Risk reduction: <strong>Teams test assumptions early, preventing costly development of unwanted features or products that miss market needs</strong>.
- Product Discovery Process: Framework, Templates & Guide
  - https://lanpdt.com/product-discovery-process/
  - This guide breaks down the complete product discovery process, along with templates, frameworks, questions, and common pitfalls to avoid. Product Discovery reduces uncertainty and de-risks development.
- 7 Product Discovery Frameworks Every Product Manager Should Know | Sondar.Ai
  - https://www.sondar.ai/resources/7-product-discovery-frameworks-every-product-manager-should-know
  - Instead of lengthy planning phases, Lean Startup encourages <strong>launching a Minimum Viable Product (MVP) to gather early feedback and make data-driven decisions about the next steps</strong>. The goal is to reduce uncertainty and achieve a successful product-market fit as efficiently as possible.

### Query: Shape Up appetite shaping boundaries
- Status: OK
- Artifact: `/home/lavallee/clawdbot/cub/.cub/toolsmith/runs/20260124-143214-mcp-official_brave-search.json`

- Set Boundaries | Shape Up
  - https://basecamp.com/shapeup/1.2-chapter-03
  - We apply this principle at each stage of the process, from shaping potential projects to building and shipping them. First, <strong>the appetite constrains what kind of a solution we design during the shaping process</strong>.
- Principles of Shaping | Shape Up
  - https://basecamp.com/shapeup/1.1-chapter-02
  - Lastly, shaped work indicates what not to do. It tells the team where to stop. There’s a specific appetite—the amount of time the team is allowed to spend on the project. Completing the project within that fixed amount of time requires limiting the scope and leaving specific things out. Taken together, the roughness leaves room for the team to resolve all the details, while the solution and boundaries act like guard rails.
- What’s the Shape Up Methodology and How to Use It?
  - https://userpilot.com/blog/shape-up/
  - If not, there is less appetite and the likelihood of the feature being developed is smaller. In practice, <strong>setting the boundaries means also prioritizing the problems they are facing</strong>.
- Notes on Shape Up
  - https://www.conordewey.com/blog/notes-on-shape-up/
  - You&#x27;ll either need a generalist that can do both or a collaboration between PM + Design for this phase. Part of shaping is setting boundaries. <strong>Narrow down the problem and define the appetite</strong>...
- Avoid appetite deviations - Shape Up Forum
  - https://discourse.learnshapeup.com/t/avoid-appetite-deviations/756
  - When shaping a 2, 4, or 6-week cycle batch, what are the best ways to determine what looks like 2, 4, or 6 weeks so we do not write a pitch that is destined to result in deviations from the stated appetite? Would, for example, considering Brooks’ rule of thumb for estimating help: 1/3 for planning (e.g., the product pitch and sometimes the left side activities of the Hill Chart.), 1/6 for coding (assumed to be easier to estimate), 1/4 for component test and early system test, and 1/4 for system...

### Query: Opportunity Solution Tree product discovery
- Status: OK
- Artifact: `/home/lavallee/clawdbot/cub/.cub/toolsmith/runs/20260124-143215-mcp-official_brave-search.json`

- Opportunity Solution Trees: Visualize Your Discovery to Stay Aligned and Drive Outcomes
  - https://www.producttalk.org/opportunity-solution-trees/
  - Opportunity solution trees <strong>help us discover products that are both desirable now and viable over time</strong>.
- Opportunity Solution Trees for Enhanced Product Discovery
  - https://productschool.com/blog/product-fundamentals/opportunity-solution-tree
  - One of the most effective tools ... Solution Tree. <strong>This visual framework helps teams map out possible routes to achieving their goals by connecting desired outcomes to opportunities, solutions, and experiments</strong>....
- Opportunity Solution Tree: A Visual Tool for Product Discovery
  - https://amplitude.com/blog/opportunity-solution-tree
  - Product discovery <strong>combines qualitative insight and quantitative analytics to determine high-value customer needs to be solved</strong>. Opportunity solution trees help product teams focus on key areas of customer need:
- Opportunity Solution Tree | Definition and Overview
  - https://www.productplan.com/glossary/opportunity-solution-tree/
  - An Opportunity Solution Tree (OST) is <strong>a visual aid that helps enable the product discovery process through the non-linear organization of ideation flows, experimentation, and identification of gaps</strong>.
- Opportunity Solution Tree
  - https://www.product-frameworks.com/Opportunity-Solution-Tree.html
  - The Opportunity Solution Tree is <strong>a visual representation of how you plan to achieve your desired outcome</strong>. The goal is to overcome many of the common pitfalls that occur during the product discovery phase by explicitly mapping out our opportunities ...

### Query: continuous discovery habits weekly touchpoints
- Status: OK
- Artifact: `/home/lavallee/clawdbot/cub/.cub/toolsmith/runs/20260124-143216-mcp-official_brave-search.json`

- Everyone Can Do Continuous Discovery—Even You! Here’s How
  - https://www.producttalk.org/getting-started-with-discovery/
  - In my book, Continuous Discovery Habits, I define continuous discovery as at <strong>a minimum weekly touchpoints with customers by the team that&#x27;s building the product where they conduct small research activities in pursuit of a desired product outcome</strong>.
- An Overview On Teresa's Torres Continuous Discovery Framework
  - https://userpilot.com/blog/continuous-discovery-framework-teresa-torres/
  - Continuous discovery is the process of conducting small research activities through weekly touchpoints with customers, by the team who’s building the product.
- Continuous Discovery Habits, by Teresa Torres
  - https://evansamek.substack.com/p/summary-continuous-discovery-habits
  - Each element is critical: &quot;a) <strong>at a minimum, weekly touchpoints with customers</strong>; b) by the team building the product; c) where they conduct small research activities; d) in pursuit of a desired outcome.”
- Key Takeaways from Continuous Discovery Habits | Zeda.io
  - https://zeda.io/blog/continuous-discovery-habits
  - In the book Continuous Discovery Habits, Torres introduces us to a working definition of continuous discovery. It goes like this: ‍ · “<strong>At a minimum, weekly touchpoints with customers</strong> · By the team building the product · Where they conduct ...
- Book Summary: Continuous Discovery Habits (Teresa Torres)
  - https://scottburleson.substack.com/p/book-summary-continuous-discovery
  - Make customer interviews, testing, ... insights. One of the foundational habits Torres recommends is <strong>setting up regular, weekly touchpoints with customers</strong>....

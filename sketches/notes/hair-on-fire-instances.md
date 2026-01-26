# Hair-on-fire incidents & pain points (examples)

These are concrete, high-severity failure modes people report in the wild that map directly to Cub’s thesis ("lock in gains" / prevent thrash).

## 1) Agent-driven deletion / irreversible local damage
- **Warp AI: “Deleted my entire project from local disk when I rejected changes”**
  - Report: rejecting AI changes led to many scripts/docs being deleted or zeroed out.
  - Quote: “Following that rejection, every python script it read, as well as many .md and reference files, were deleted; some files… were written to 0 bytes.”
  - https://github.com/warpdotdev/Warp/issues/7976

## 2) Whole-file rewriting → huge diffs / slow / hard to review
- **Copilot Workspace (known issue): whole file rewriting**
  - Quote: “Copilot Workspace currently uses ‘whole file rewriting’…” (partial-file rewriting is future work)
  - https://raw.githubusercontent.com/githubnext/copilot-workspace-user-manual/main/known-issues.md

## 3) Bad context selection → irrelevant code changes
- **Copilot Workspace (known issue): suboptimal content selection**
  - Quote: “The content selection … can sometimes be suboptimal, leading to the generation of code that is not relevant to the task.”
  - https://raw.githubusercontent.com/githubnext/copilot-workspace-user-manual/main/known-issues.md

## 4) Missing stop/abort control → runaway costs/time
- **Copilot Workspace (known issue): no stop button in some flows**
  - Quote: “There is no ‘Stop’ button when generating pull request descriptions.”
  - https://raw.githubusercontent.com/githubnext/copilot-workspace-user-manual/main/known-issues.md

## 5) Review bots produce too much noise → people ignore them
- **WooCommerce on PR review tools**
  - Quote: “they tend to generate a lot of false positives. This noise leads to contributors often ignoring them…”
  - https://github.com/woocommerce/woocommerce/issues/58887

## 6) IDE agent workflow regressions increase review friction
- **Cursor community: reduced ergonomics for accepting changes**
  - Example snippet (from indexed search; direct Reddit fetch blocked here): “In Agent Mode, the ‘Accept All Changes’ button was replaced with ‘Review’… the slowdown adds up fast.”
  - https://www.reddit.com/r/cursor/comments/1p395v1/cursor_keeps_removing_essential_features_and_its/

## Why these matter for Cub
These map cleanly to Cub’s differentiation:
- Bounded envelopes + disjoint tasks + integration task = prevent cross-cutting damage and thrash.
- Diff-first / changeset governance = resist whole-file rewrite chaos.
- Context discipline = fewer irrelevant edits.
- Budgeting + stop/abort semantics = prevent runaway loops.
- PR confidence report = reduce review burden without bot-noise.

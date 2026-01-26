# Death-by-a-thousand-paper-cuts (instances & patterns)

These are smaller, high-frequency frictions that make AI-assisted coding feel like babysitting—even when nothing catastrophic happens.

## 1) Review ergonomics regress / extra clicks to accept changes
- Cursor community complaint (indexed snippet): “In Agent Mode, the ‘Accept All Changes’ button was replaced with ‘Review’… the slowdown adds up fast.”
  - https://www.reddit.com/r/cursor/comments/1p395v1/cursor_keeps_removing_essential_features_and_its/
  - (Direct Reddit fetch blocked in this environment.)

## 2) UI instability in the agent toolchain interrupts flow
- Cursor issue: “Window is not responding” triggered by deleting a chat.
  - https://github.com/cursor/cursor/issues/3388

## 3) Lack of change-size visibility before approving
- Feature request: show diff magnitude (“lines added/deleted”) so users can judge disruption up front.
  - Example surfaced in Cursor-adjacent agent tooling:
  - https://github.com/xenodium/agent-shell/issues/163

## 4) Whole-file rewrites cause noisy diffs even when change is small
- Copilot Workspace explicitly uses “whole file rewriting,” making review heavier and slower.
  - https://raw.githubusercontent.com/githubnext/copilot-workspace-user-manual/main/known-issues.md

## 5) Content selection misses → you spend time steering, not building
- Copilot Workspace: content selection can be “suboptimal,” producing irrelevant edits.
  - https://raw.githubusercontent.com/githubnext/copilot-workspace-user-manual/main/known-issues.md

## 6) Ambiguity detection too eager → extra back-and-forth
- Copilot Workspace admits ambiguity detection may trigger even when tasks are clear (creates interaction tax).
  - https://raw.githubusercontent.com/githubnext/copilot-workspace-user-manual/main/known-issues.md

## 7) Missing stop/abort controls in parts of workflows
- Copilot Workspace: no stop button for some generation flows (e.g., PR descriptions).
  - https://raw.githubusercontent.com/githubnext/copilot-workspace-user-manual/main/known-issues.md

## 8) Review bots: low signal-to-noise adds friction to every PR
- WooCommerce: false positives → contributors ignore reviews; teams want defensive checks without spam.
  - https://github.com/woocommerce/woocommerce/issues/58887

---

## Why this matters for Cub’s value prop
Cub can position itself as a **progress governor** that reduces paper cuts by default:
- Bounded envelopes + soft-disjoint tasks = fewer sprawling diffs.
- Change-size preview + staged commits = approval becomes fast and confident.
- “Stop/timeout/budget” semantics = no runaway sessions.
- Confidence report tuned for signal (risk, verification, intent) = less review fatigue.

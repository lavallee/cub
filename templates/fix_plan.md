# Fix Plan

<!--
WHAT IS THIS FILE?
This document tracks known issues, bugs, and planned fixes discovered during development.
It helps organize technical debt and prevents issues from being forgotten between sessions.

WHAT TO ADD:
- Bugs found but not yet fixed
- Technical debt that should be addressed
- Performance improvements that could be made
- Test coverage gaps
- Deprecation notices for code

WHAT NOT TO ADD:
- Feature requests (use task backlog instead: prd.json or .beads/issues.jsonl)
- Architecture discussions (use specs/ directory instead)
- Completed fixes (delete entries once merged)

TIPS FOR EFFECTIVE ENTRIES:
1. Be specific about the problem and impact
2. Include reproduction steps if it's a bug
3. Link to related files and line numbers
4. Add priority to help future sessions prioritize fixes
5. Note if a fix is blocked by other work

FORMAT:
Use the Severity/Priority system below. Move fixed items to "Completed" section at bottom.
-->

## Open Issues

### High Priority (blocks other work or causes data loss)

- **[ISSUE ID]**: [Brief description]
  - **Impact**: [What breaks or how bad is it?]
  - **Reproduction**: [How to trigger it]
  - **Location**: [File path and line number]
  - **Workaround**: [If available]
  - **Fix Approach**: [How to solve it]

### Medium Priority (degrades user experience or performance)

- **[ISSUE ID]**: [Brief description]
  - **Impact**: [What breaks or how bad is it?]
  - **Reproduction**: [How to trigger it]
  - **Location**: [File path and line number]
  - **Workaround**: [If available]
  - **Fix Approach**: [How to solve it]

### Low Priority (nice to have, test coverage, documentation)

- **[ISSUE ID]**: [Brief description]
  - **Impact**: [What breaks or how bad is it?]
  - **Reproduction**: [How to trigger it]
  - **Location**: [File path and line number]
  - **Workaround**: [If available]
  - **Fix Approach**: [How to solve it]

---

## Technical Debt

List refactoring opportunities and code quality improvements:

- **[Area]**: [What could be improved and why]
  - **Related files**: [Files affected]
  - **Effort**: [Small/Medium/Large]
  - **Benefit**: [Why improve this?]

---

## Test Coverage Gaps

Known areas with insufficient tests:

- **[Feature/Module]**: [What's not tested]
  - **Impact**: [Risk of this gap]
  - **Test plan**: [How to add coverage]

---

## Completed Fixes

Move resolved issues here with the date completed:

- ✅ **[ISSUE ID]** (YYYY-MM-DD): [Brief description of fix]
  - **Fix**: [How it was solved]
  - **Commit**: [Git commit hash if available]

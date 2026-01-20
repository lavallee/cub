# Fix Plan & Technical Debt Tracker

<!--
╔══════════════════════════════════════════════════════════════════╗
║  WHAT IS THIS FILE?                                              ║
╚══════════════════════════════════════════════════════════════════╝

This is your project's bug tracker and technical debt backlog.
It captures issues discovered during development so they don't get forgotten.

This file helps:
- Track issues that need fixing (bugs, performance problems, etc.)
- Organize work by priority so critical issues get fixed first
- Document institutional knowledge (why something is temporary/hacky)
- Prevent regressions by noting what broke before

This file is committed to git and read by every session.

╔══════════════════════════════════════════════════════════════════╗
║  WHAT TO ADD                                                     ║
╚══════════════════════════════════════════════════════════════════╝

✅ ADD THESE:
- Bugs: reproducible problems that need fixing
  Example: "Login button broken on mobile Safari"
- Performance: slow code that needs optimization
  Example: "HomePage takes 5+ seconds to load with 1000 items"
- Technical debt: hacky or temporary code
  Example: "Search uses O(n) algorithm instead of indexed query"
- Test gaps: untested code or scenarios
  Example: "No tests for error handling in auth flow"
- Deprecations: code being phased out
  Example: "Old API endpoints in src/api/v1/ - migrate to v2"
- Security: potential vulnerabilities
  Example: "User input not sanitized in comments field"

❌ DON'T ADD:
- Feature requests (use task backlog instead)
- Completed fixes (delete when merged/fixed - archive in git history)
- Vague complaints ("Code is messy" - be specific!)
- Architecture discussions (use specs/ directory)
- Things visible in code (if code is obvious, don't document it here)

EXAMPLES (Good Issues):
- **Database N+1 Query in POST /users endpoint**: Every user fetch runs extra query for their profile picture. Impact: API slow with >100 users. Fix: Use eager loading with .populate('profile'). See: src/api/users.ts:42
- **Test flakiness on CI**: Auth tests fail randomly on GitHub Actions. Symptom: "timeout waiting for login". Workaround: add --retries=3 to pytest. Root cause: CI network slower than local.
- **Memory leak in real-time sync**: App consumes 500MB after 1 hour, crashes after 4 hours. See: src/lib/sync.ts - WebSocket listener never unsubscribed. Fix: Add cleanup in useEffect return.

EXAMPLES (Bad Issues):
- "Code is bad" ← Not specific, not actionable
- "Performance needs work" ← What specifically is slow?
- "Should use better patterns" ← What patterns? Where?

╔══════════════════════════════════════════════════════════════════╗
║  HOW TO WRITE GOOD ISSUES                                        ║
╚══════════════════════════════════════════════════════════════════╝

STRUCTURE:
- **Title**: One-line summary (what's broken)
- Impact: Why this matters (who's affected, what breaks)
- Reproduction: Steps to trigger (or conditions when it happens)
- Location: File path and line number(s)
- Workaround: If there's a temporary fix, document it
- Root Cause: If you know why it's broken
- Fix Approach: How to solve it (or leave blank if unknown)
- Blocked By: If this depends on other work
- Added: Date discovered (YYYY-MM-DD)

TIPS:
- Be SPECIFIC: "Login fails on Firefox" beats "Login broken"
- Include impact: "Affects 5% of users on mobile" matters
- Add reproduction steps: "Submit form with >100 chars in email field"
- Link to code: "src/api/middleware.ts:127 missing error handler"
- Include dates: If time-bound, note when it started: "Broken since 2024-01-15"
- Suggest fixes: "Could use lodash debounce to prevent this"
- Note blockers: "Can't fix until we upgrade TypeScript"

PRIORITY SYSTEM:
- 🔴 HIGH: Breaks functionality, data loss, security, affects many users
- 🟡 MEDIUM: Degrades user experience, affects some users, performance issues
- 🟢 LOW: Nice-to-have improvements, rare edge cases, code quality
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

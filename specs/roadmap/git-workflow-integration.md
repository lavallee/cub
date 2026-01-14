# Git Workflow Integration

**Source:** Original (cub)
**Dependencies:** None
**Complexity:** Low-Medium
**Priority:** High (quick win, daily workflow improvement)

## Overview

Tightly integrate git workflow with beads task lifecycle to enforce good hygiene:
- Branch-per-epic pattern
- Checkpoint tasks for natural commit groupings
- Automatic PR creation when epics close
- Clean git state enforcement throughout

## Problem Statement

### Current Pain Points

**1. Disconnected Workflows**
```bash
# User has to manually coordinate these
bd create --type epic "User Authentication"
git checkout -b feature/auth        # Manual
# ... work on tasks ...
bd close beads-abc                  # Closes epic
# Now manually create PR?
gh pr create                        # Easy to forget
```

**2. No Branch-Epic Association**
- Which branch belongs to which epic?
- Multiple epics on same branch = messy PRs
- No enforcement of "one epic = one PR" pattern

**3. Checkpoint Tasks Are Ad-Hoc**
- No standard pattern for "pause points"
- Hard to know when work is PR-ready
- No natural grouping for code review

**4. Stale Branches**
- Epics close but branches linger
- PRs merged but local branches not cleaned
- No visibility into branch-epic mapping

---

## Proposed Solution

### 1. Epic-Branch Binding

When creating or starting an epic, optionally bind it to a git branch:

```bash
# Create epic with auto-branch
bd create --type epic --branch "User Authentication"
# Creates: beads-abc (epic)
# Creates: git branch epic/beads-abc/user-authentication

# Or bind existing epic to branch
bd branch beads-abc
# Creates branch from current HEAD, binds to epic

# View binding
bd show beads-abc
# Epic: beads-abc "User Authentication"
# Branch: epic/beads-abc/user-authentication
# Base: main
# Tasks: 5 (3 closed, 2 open)
```

**Storage:**
```yaml
# .beads/branches.yaml
beads-abc:
  branch: epic/beads-abc/user-authentication
  base: main
  created_at: 2026-01-13T14:30:00Z
```

### 2. Checkpoint Tasks

Introduce a `checkpoint` task type for natural pause points:

```bash
# Create checkpoint within epic
bd create --type checkpoint --parent beads-abc "Auth flow complete - ready for review"

# Checkpoints block downstream tasks until explicitly closed
# They signal "stop here and review before continuing"
```

**Checkpoint Semantics:**
- Checkpoints are tasks with `type: checkpoint`
- They don't auto-close (require explicit `bd close`)
- Downstream tasks depend on the checkpoint
- Closing a checkpoint can trigger actions (PR, notification)

**Example Epic Structure:**
```
beads-abc: "User Authentication" (epic)
├── beads-def: "Set up auth database schema" (task)
├── beads-ghi: "Implement login endpoint" (task)
├── beads-jkl: "Implement logout endpoint" (task)
├── beads-mno: "CHECKPOINT: Core auth complete" (checkpoint)
│   └── [closing this could trigger PR]
├── beads-pqr: "Add password reset" (task)
├── beads-stu: "Add email verification" (task)
└── beads-vwx: "CHECKPOINT: Full auth complete" (checkpoint)
    └── [closing this closes the epic]
```

### 3. Auto-PR on Epic/Checkpoint Close

When closing an epic or checkpoint, offer to create a PR:

```bash
$ bd close beads-abc

Closing epic: beads-abc "User Authentication"

Branch: epic/beads-abc/user-authentication
Base:   main
Commits: 12 ahead

Tasks completed:
  ✓ beads-def: Set up auth database schema
  ✓ beads-ghi: Implement login endpoint
  ✓ beads-jkl: Implement logout endpoint

? Create Pull Request? [Y/n/e(dit)]

Creating PR...
  Title: feat(auth): User Authentication
  Body: [auto-generated from tasks]

✓ PR created: https://github.com/user/repo/pull/123
✓ Epic beads-abc closed
```

**PR Body Generation:**
```markdown
## Summary

Implements user authentication epic (beads-abc).

### Tasks Completed
- [x] Set up auth database schema (beads-def)
- [x] Implement login endpoint (beads-ghi)
- [x] Implement logout endpoint (beads-jkl)

### Testing
- [ ] Manual testing of login flow
- [ ] Review database migrations

---
Epic: beads-abc
Branch: epic/beads-abc/user-authentication
```

### 4. Git Hygiene Commands

New commands for maintaining clean git state:

```bash
# Show branch-epic mapping
bd branches
# epic/beads-abc/user-auth    beads-abc  "User Authentication"  (in_progress)
# epic/beads-xyz/api-refactor beads-xyz  "API Refactoring"      (closed, PR #123)

# Clean up merged branches
bd branches --cleanup
# Found 3 branches with merged PRs:
#   epic/beads-xyz/api-refactor (PR #123 merged)
#   epic/beads-123/bug-fix (PR #124 merged)
#   epic/beads-456/docs (PR #125 merged)
# Delete these branches? [Y/n]

# Sync branch state
bd branches --sync
# Fetching remote state...
# ✓ Branch epic/beads-abc is up to date
# ⚠ Branch epic/beads-xyz was deleted on remote (PR merged)
#   → Deleting local branch
```

### 5. Cub Integration

Cub hooks into this workflow automatically:

```bash
# Starting a run on an epic
cub run --epic beads-abc

# Pre-loop hook checks:
# - Is there a branch bound to this epic?
# - If not, offer to create one
# - Switch to the epic's branch

# Post-loop hook (when all epic tasks done):
# - Prompt for PR creation
# - Or auto-create if configured
```

**Configuration:**
```json
{
  "git": {
    "branch_per_epic": true,
    "branch_prefix": "epic/",
    "auto_pr_on_epic_close": "prompt",  // "prompt" | "auto" | "never"
    "cleanup_merged_branches": true
  }
}
```

---

## CLI Interface

### New Beads Commands

```bash
# Branch management
bd branch <epic-id>              # Create/bind branch for epic
bd branch <epic-id> --from main  # Specify base branch
bd branches                      # List all epic-branch bindings
bd branches --cleanup            # Clean up merged branches
bd branches --sync               # Sync with remote state

# Checkpoint tasks
bd create --type checkpoint --parent <epic-id> "Description"
bd checkpoints                   # List all checkpoints
bd checkpoints --pending         # Show checkpoints blocking work

# PR integration
bd pr <epic-id>                  # Create PR for epic
bd pr <epic-id> --draft          # Create draft PR
bd pr --check                    # Check PR status for all epics
```

### Enhanced Existing Commands

```bash
# bd close now offers PR creation for epics/checkpoints
bd close <epic-id>
# → Prompts for PR if branch exists

# bd show includes branch info
bd show <epic-id>
# → Shows branch, base, PR status

# bd ready respects checkpoint blocking
bd ready
# → Won't show tasks blocked by open checkpoints
```

### Cub Commands

```bash
# Epic-aware run
cub run --epic beads-abc         # Switches to epic branch automatically

# PR creation
cub pr                           # Create PR for current epic
cub pr --epic beads-abc          # Create PR for specific epic
```

---

## Workflow Examples

### Example 1: Full Epic Lifecycle

```bash
# 1. Create epic with branch
bd create --type epic --branch "Add user profiles"
# ✓ Created epic beads-abc
# ✓ Created branch epic/beads-abc/add-user-profiles

# 2. Add tasks
bd create --parent beads-abc "Create profile model"
bd create --parent beads-abc "Add profile API endpoints"
bd create --parent beads-abc --type checkpoint "Profile backend complete"
bd create --parent beads-abc "Create profile UI components"
bd create --parent beads-abc "Add profile settings page"

# 3. Run cub on epic
cub run --epic beads-abc
# Automatically on epic/beads-abc/add-user-profiles branch

# 4. Work progresses, checkpoint reached
bd close beads-checkpoint-1
# → "Create PR for checkpoint? [Y/n]"
# → Creates draft PR for review

# 5. Continue work, epic completes
bd close beads-abc
# → "Create/update PR? [Y/n]"
# → Updates PR, marks ready for review

# 6. After PR merges
bd branches --cleanup
# → Deletes local branch
```

### Example 2: Multiple Epics in Parallel

```bash
# Team member A works on auth
bd create --type epic --branch "Authentication"
cub run --epic beads-auth

# Team member B works on API
bd create --type epic --branch "API v2"
cub run --epic beads-api

# Each has isolated branch, clean PRs
bd branches
# epic/beads-auth/authentication  beads-auth  (in_progress)
# epic/beads-api/api-v2           beads-api   (in_progress)
```

### Example 3: Checkpoint-Driven Development

```bash
# Create epic with checkpoints as milestones
bd create --type epic "Payment Integration"
bd create --parent beads-pay "Research payment providers"
bd create --parent beads-pay --type checkpoint "Provider selected"
bd create --parent beads-pay "Implement Stripe integration"
bd create --parent beads-pay "Add payment UI"
bd create --parent beads-pay --type checkpoint "MVP payment flow"
bd create --parent beads-pay "Add subscription support"
bd create --parent beads-pay "Add invoicing"
bd create --parent beads-pay --type checkpoint "Full payment system"

# Checkpoints naturally pause work for review
cub run --epic beads-pay
# Stops at first checkpoint, prompts for PR

# After review, continue
bd close beads-checkpoint-1  # "Provider selected"
cub run --epic beads-pay
# Continues to next checkpoint
```

---

## Implementation Notes

### Branch Naming Convention

```
epic/{epic-id}/{slugified-title}

Examples:
  epic/beads-abc/user-authentication
  epic/beads-xyz/api-v2-refactoring
  epic/beads-123/fix-login-bug
```

**Slug Generation:**
```bash
slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | \
    sed 's/[^a-z0-9]/-/g' | \
    sed 's/--*/-/g' | \
    sed 's/^-//' | \
    sed 's/-$//' | \
    head -c 50
}
```

### Branch Metadata Storage

Option A: YAML file in `.beads/`
```yaml
# .beads/branches.yaml
branches:
  beads-abc:
    branch: epic/beads-abc/user-authentication
    base: main
    created_at: 2026-01-13T14:30:00Z
    pr_number: null
  beads-xyz:
    branch: epic/beads-xyz/api-v2
    base: main
    created_at: 2026-01-12T10:00:00Z
    pr_number: 123
```

Option B: Labels on beads issues
```bash
bd label add beads-abc "branch:epic/beads-abc/user-auth"
bd label add beads-abc "base:main"
bd label add beads-abc "pr:123"
```

**Recommendation:** YAML file (Option A) - cleaner, easier to query.

### PR Body Template

```markdown
## {{epic.title}}

{{epic.description}}

### Completed Tasks
{{#each tasks}}
- [x] {{this.title}} ({{this.id}})
{{/each}}

### Checkpoints
{{#each checkpoints}}
- [{{#if this.closed}}x{{else}} {{/if}}] {{this.title}}
{{/each}}

---
Epic: {{epic.id}}
Branch: {{branch.name}}
Base: {{branch.base}}
```

### Hook Integration

**Pre-loop hook:** `10-epic-branch.sh`
```bash
#!/bin/bash
# Ensure we're on the right branch for the epic

EPIC_ID="${CUB_EPIC:-}"
if [[ -z "$EPIC_ID" ]]; then
  exit 0  # No epic specified, skip
fi

# Get branch for epic
BRANCH=$(bd branch --get "$EPIC_ID" 2>/dev/null)
if [[ -z "$BRANCH" ]]; then
  echo "[epic-branch] No branch bound to $EPIC_ID"
  echo "[epic-branch] Create one with: bd branch $EPIC_ID"
  exit 0
fi

# Switch to branch if not already there
CURRENT=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT" != "$BRANCH" ]]; then
  echo "[epic-branch] Switching to $BRANCH"
  git checkout "$BRANCH"
fi
```

**Post-loop hook:** `90-epic-pr.sh`
```bash
#!/bin/bash
# Offer PR creation when epic completes

EPIC_ID="${CUB_EPIC:-}"
if [[ -z "$EPIC_ID" ]]; then
  exit 0
fi

# Check if epic is closed
STATUS=$(bd show "$EPIC_ID" --format json | jq -r '.status')
if [[ "$STATUS" != "closed" ]]; then
  exit 0
fi

# Check if PR already exists
PR=$(bd show "$EPIC_ID" --format json | jq -r '.pr_number // empty')
if [[ -n "$PR" ]]; then
  echo "[epic-pr] PR #$PR already exists for $EPIC_ID"
  exit 0
fi

# Prompt for PR creation
echo ""
echo "[epic-pr] Epic $EPIC_ID is complete!"
read -p "[epic-pr] Create Pull Request? [Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z "$REPLY" ]]; then
  bd pr "$EPIC_ID"
fi
```

---

## Configuration

```json
{
  "git": {
    "branch_per_epic": true,
    "branch_prefix": "epic/",
    "include_epic_id": true,
    "auto_switch_branch": true,
    "auto_pr_on_epic_close": "prompt",
    "auto_pr_on_checkpoint": "prompt",
    "pr_template": ".github/PULL_REQUEST_TEMPLATE/epic.md",
    "cleanup_merged_branches": true,
    "protect_base_branches": ["main", "master", "develop"]
  },
  "checkpoints": {
    "enabled": true,
    "block_downstream": true,
    "require_review": false
  }
}
```

---

## Acceptance Criteria

### Phase 1: Branch-Epic Binding
- [ ] `bd branch <epic-id>` creates and binds branch
- [ ] `bd branches` lists all bindings
- [ ] `bd show` displays branch info for epics
- [ ] Branch metadata stored in `.beads/branches.yaml`
- [ ] Cub auto-switches to epic branch

### Phase 2: Checkpoints
- [ ] `--type checkpoint` creates checkpoint tasks
- [ ] Checkpoints block downstream tasks
- [ ] `bd checkpoints` lists checkpoints
- [ ] Checkpoint close prompts for action

### Phase 3: PR Integration
- [ ] `bd close` on epic prompts for PR
- [ ] `bd pr <epic-id>` creates PR
- [ ] PR body auto-generated from tasks
- [ ] PR number stored in branch metadata

### Phase 4: Cleanup
- [ ] `bd branches --cleanup` removes merged branches
- [ ] `bd branches --sync` syncs with remote
- [ ] Warning when deleting unmerged branches

---

## Future Enhancements

- **GitHub Actions integration:** Auto-close beads epic when PR merges
- **PR templates per epic type:** Different templates for features vs bugs
- **Review assignments:** Auto-assign reviewers based on epic labels
- **Branch protection:** Prevent direct commits to epic branches
- **Stacked PRs:** Support for dependent PRs within an epic
- **Release notes:** Auto-generate from closed epics

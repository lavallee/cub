# Captures

Captures are a quick way to record ideas, notes, and observations without interrupting your workflow. They're stored as Markdown files with frontmatter metadata, making them easy to search and organize.

## What Are Captures?

Captures are lightweight notes designed for:

- **Ideas that come up during work** - Quick jot without losing context
- **Observations about the codebase** - Things to fix later
- **Feature requests** - Ideas for future development
- **Bug reports** - Issues noticed in passing
- **Meeting notes** - Quick capture from discussions

Each capture is a Markdown file with YAML frontmatter:

```markdown
---
id: cap-a7x3m2
created: 2026-01-17T10:30:00Z
title: Add caching to user lookup
tags:
  - feature
  - performance
source: cli
---

The user lookup function is called on every request.
Adding a simple cache would improve performance significantly.

Could use Redis or even in-memory with TTL.
```

## Using Captures

### Quick Capture

```bash
# Capture a simple idea
cub capture "Add dark mode to settings page"
```

### With Tags

```bash
# Add tags for organization
cub capture "Refactor auth flow" --tag feature --tag auth
```

### From Stdin

```bash
# Pipe content
echo "Meeting notes: Discussed API versioning" | cub capture

# Multi-line content
cat << EOF | cub capture
Sprint retrospective notes:
- Good: Faster deployments
- Improve: Test coverage
- Action: Add CI checks
EOF
```

### With Priority

```bash
# Set priority (1-5, lower is higher)
cub capture "Critical bug in payment flow" --priority 1
```

### With Custom Name

```bash
# Specify filename (without .md)
cub capture "Q1 planning" --name "q1-2026-planning"
```

## Storage Model

Cub uses a two-tier storage model for captures:

### Global Captures (Default)

Stored at `~/.local/share/cub/captures/{project}/`:

- **Safe from branch deletion** - Persists across git operations
- **Organized by project** - Easy cross-project browsing
- **Not version controlled** - Personal notes

```bash
# Default: saves to global store
cub capture "My idea"
```

### Project Captures

Stored at `{project}/captures/`:

- **Version controlled** - Part of the project
- **Shared with team** - Visible to collaborators
- **Permanent record** - Tracked in git

```bash
# Save to project directory
cub capture "Team decision" --project
```

## File Naming

Captures use descriptive filenames:

```
{project-id}-cap-{YYYYMMDD}-{slug}.md
```

Example: `cub-cap-20260117-add-dark-mode-ui.md`

### Slug Generation

By default, Cub generates a slug from the content:

1. Analyzes the capture content
2. Generates a descriptive slug
3. Adds timestamp for uniqueness

Disable slug generation:

```bash
# Use ID only as filename
cub capture "Quick note" --no-slug
```

## Auto-Tagging

Cub can automatically suggest tags based on content:

```bash
# Auto-tags enabled by default
cub capture "Fix the broken API endpoint"
# Auto-tagged: [bugfix, api]
```

Disable auto-tagging:

```bash
cub capture "Quick note" --no-auto-tags
```

Tags are suggested based on keywords:

| Keywords | Suggested Tags |
|----------|---------------|
| bug, fix, broken | bugfix |
| feature, add, new | feature |
| test, spec | testing |
| refactor, clean | refactor |
| doc, readme | docs |

## Interactive Mode

Launch an interactive capture session with Claude:

```bash
cub capture -i "New feature idea"
```

Interactive mode:

1. Opens a conversation with Claude
2. Helps refine and expand your idea
3. Generates structured capture
4. Saves with rich metadata

## Listing Captures

View your captures:

```bash
# List all captures for current project
cub captures

# Filter by tag
cub captures --tag feature

# Filter by status
cub captures --status active
```

Output:

```
Captures (myproject)
+----------+------------+------------------------------+------------+
| ID       | Date       | Title                        | Tags       |
+----------+------------+------------------------------+------------+
| cap-a7x3 | 2026-01-17 | Add caching to user lookup   | feature    |
| cap-b2m4 | 2026-01-16 | Fix auth redirect bug        | bugfix     |
| cap-c9p1 | 2026-01-15 | Q1 planning notes            | planning   |
+----------+------------+------------------------------+------------+
```

## Organizing Captures

### Archive Old Captures

Move completed or outdated captures to archive:

```bash
# Archive a capture
cub captures archive cap-a7x3m2
```

Archived captures move to `captures/archived/`.

### Promote to Task

Convert a capture into a formal task:

```bash
# Create task from capture
cub captures promote cap-a7x3m2
```

This creates a new task in your task backend with the capture content.

## Workflow Examples

### During Code Review

```bash
# Spot something while reviewing
cub capture "Consider adding rate limiting to this endpoint" --tag review

# Continue with review, address later
```

### After a Meeting

```bash
# Quick meeting summary
cat << EOF | cub capture --tag meeting
Sprint planning 2026-01-17:
- Priority: Complete auth refactor
- Blocked: Waiting on API docs
- Next: Start caching layer
EOF
```

### Ideas While Coding

```bash
# Idea comes up while working
cub capture "This function could be memoized" --priority 3

# Stay focused on current task
```

### Bug Discovery

```bash
# Notice a bug while working on something else
cub capture "Race condition in user session handling" --tag bugfix --priority 2
```

## File Format

Captures use Markdown with YAML frontmatter:

```yaml
---
id: cap-a7x3m2
created: 2026-01-17T10:30:00Z
title: Add caching to user lookup
tags:
  - feature
  - performance
source: cli
priority: 3
status: active
needs_human_review: false
---
```

### Frontmatter Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique capture ID |
| `created` | datetime | Creation timestamp |
| `title` | string | Short title/summary |
| `tags` | list | Organization tags |
| `source` | string | How captured (cli, pipe, interactive) |
| `priority` | int | Priority 1-5 (optional) |
| `status` | string | active, archived (optional) |
| `needs_human_review` | bool | Flag for review (optional) |

## Searching Captures

### By Content

```bash
# Search capture content
grep -r "caching" ~/.local/share/cub/captures/myproject/
```

### By Tag

```bash
# Find captures with tag
cub captures --tag performance
```

### By Date

```bash
# Find recent captures
find ~/.local/share/cub/captures/myproject/ -mtime -7 -name "*.md"
```

## Best Practices

### Capture Quickly

Don't overthink captures. The goal is speed:

```bash
# Good: Quick and captured
cub capture "Look into connection pooling"

# Avoid: Spending time formatting
```

### Use Tags Consistently

Establish tag conventions:

| Tag | Use For |
|-----|---------|
| `feature` | New functionality ideas |
| `bugfix` | Bugs to fix |
| `refactor` | Code improvements |
| `docs` | Documentation needs |
| `urgent` | Time-sensitive items |

### Review Regularly

Schedule time to:

1. Review accumulated captures
2. Promote actionable items to tasks
3. Archive completed or stale captures

### Keep Captures Small

One idea per capture:

```bash
# Good: Focused
cub capture "Add retry logic to API client"

# Avoid: Multiple ideas
cub capture "Add retry logic and improve error messages and add logging"
```

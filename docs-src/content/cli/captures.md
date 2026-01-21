---
title: cub captures
description: List, view, and manage captured ideas, notes, and observations.
---

# cub captures

List, view, and manage captured ideas, notes, and observations.

## Synopsis

```bash
cub captures [OPTIONS]
cub captures show CAPTURE_ID
cub captures edit CAPTURE_ID
cub captures import CAPTURE_ID [--keep]
cub captures archive CAPTURE_ID
```

## Description

The `cub captures` command provides tools to list, view, and manage your captures. It shows captures from both storage locations:

- **Global**: `~/.local/share/cub/captures/{project}/` - Default for new captures
- **Project**: `./captures/` - Version-controlled captures

## Subcommands

| Subcommand | Description |
|------------|-------------|
| (default) | List captures from both stores |
| `show` | Display a capture in full |
| `edit` | Edit a capture in your $EDITOR |
| `import` | Import a global capture into the project |
| `archive` | Archive a capture (hide from listings) |

## List Options

| Option | Short | Description |
|--------|-------|-------------|
| `--all` | `-a` | Show all captures (default: last 20) |
| `--tag TAG` | `-t` | Filter by tag |
| `--since DATE` | | Filter by date (ISO date or relative: 7d, 1w, 2m) |
| `--search TERM` | `-s` | Full-text search in title and content |
| `--global` | `-g` | Show only global captures |
| `--project` | `-P` | Show only project captures |
| `--json` | | Output as JSON |
| `--help` | `-h` | Show help message and exit |

## Listing Captures

### Default listing

```bash
cub captures
```

Output:
```
Global (myproject) - ~/.local/share/cub/captures/myproject/
+------------+------------+---------------------------+-------------+-----+
| ID         | Date       | Title                     | Tags        | Pri |
+------------+------------+---------------------------+-------------+-----+
| cap-042    | Today      | Add dark mode to UI       | feature, ui | 2   |
| cap-041    | Yesterday  | Fix login timeout bug     | bug, auth   | 1   |
| cap-040    | 3d ago     | Refactor user service     | refactor    | -   |
+------------+------------+---------------------------+-------------+-----+
Showing 20 of 42. Use --all to see all.

Project (./captures/) - ./captures/
+------------+------------+---------------------------+-------------+-----+
| ID         | Date       | Title                     | Tags        | Pri |
+------------+------------+---------------------------+-------------+-----+
| cap-015    | 2w ago     | API versioning strategy   | design, api | -   |
+------------+------------+---------------------------+-------------+-----+
```

### Filter by tag

```bash
cub captures --tag feature
```

Shows only captures tagged with "feature".

### Filter by date

```bash
# Last 7 days
cub captures --since 7d

# Last 2 weeks
cub captures --since 2w

# Since specific date
cub captures --since 2026-01-01
```

Supported relative formats:

| Format | Meaning |
|--------|---------|
| `7d` | Last 7 days |
| `1w` | Last 1 week |
| `2m` | Last 2 months (approx 60 days) |

### Search content

```bash
cub captures --search "authentication"
```

Searches both title and content of captures.

### Show only global captures

```bash
cub captures --global
```

### Show only project captures

```bash
cub captures --project
```

### Show all captures

```bash
cub captures --all
```

Removes the default limit of 20 items.

### JSON output

```bash
cub captures --json
```

Output:
```json
{
  "global": [
    {
      "id": "cap-042",
      "created": "2026-01-17T10:30:00Z",
      "title": "Add dark mode to UI",
      "tags": ["feature", "ui"],
      "source": "cli",
      "status": "active",
      "priority": 2
    }
  ],
  "project": []
}
```

## show

Display a capture in full detail.

### Synopsis

```bash
cub captures show CAPTURE_ID
```

### Description

Shows the complete capture including all metadata and content. Automatically searches both global and project stores.

### Examples

```bash
cub captures show cap-042
```

Output:
```
Capture cap-042 (global)
Location: ~/.local/share/cub/captures/myproject/cap-042.md
Created: 2026-01-17 10:30:00
Title: Add dark mode to UI
Tags: feature, ui
Priority: 2
Status: active
Source: cli

Content:
The app should support a dark color scheme that users can toggle
in settings. This improves usability in low-light conditions.
```

## edit

Edit a capture in your text editor.

### Synopsis

```bash
cub captures edit CAPTURE_ID
```

### Description

Opens the capture file in your default text editor (`$EDITOR`). Searches both global and project stores automatically.

### Examples

```bash
cub captures edit cap-042
```

Opens the capture in vim (or your configured editor).

### Editor Configuration

Set your preferred editor:

```bash
export EDITOR=code  # VS Code
export EDITOR=vim   # Vim
export EDITOR=nano  # Nano
```

## import

Import a global capture into the project.

### Synopsis

```bash
cub captures import CAPTURE_ID [--keep]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--keep` | `-k` | Keep the original global capture after import |

### Description

Moves a capture from global storage (`~/.local/share/cub/captures/{project}/`) into the project's `./captures/` directory for version control.

By default, the global copy is removed after import. Use `--keep` to preserve both copies.

### Examples

Import and remove from global:

```bash
cub captures import cap-042
```

Output:
```
[check] Imported cap-042
Project: ./captures/myproject-cap-20260117-add-dark-mode-ui.md
Removed from global store
```

Import but keep global copy:

```bash
cub captures import cap-042 --keep
```

## archive

Archive a capture to hide it from listings.

### Synopsis

```bash
cub captures archive CAPTURE_ID
```

### Description

Marks a capture as archived. Archived captures are hidden from default listings but not deleted. The file remains on disk with `status: archived` in its frontmatter.

### Examples

```bash
cub captures archive cap-042
```

Output:
```
[check] Archived cap-042 (global)
```

To see archived captures, you would need to view the file directly or modify filters.

## Combining Filters

You can combine multiple filters:

```bash
# Features from last week
cub captures --tag feature --since 1w

# Search bugs in project only
cub captures --project --tag bug --search "login"

# All global captures as JSON
cub captures --global --all --json
```

## Capture Status

Captures can have different statuses:

| Status | Description |
|--------|-------------|
| `active` | Default, shown in listings |
| `archived` | Hidden from listings |
| `processed` | Converted to a task |

## Date Formatting

The date column shows relative dates for readability:

| Display | Meaning |
|---------|---------|
| Today | Within the last 24 hours |
| Yesterday | 1-2 days ago |
| 3d ago | 3 days ago |
| 2w ago | 2 weeks ago |
| 2026-01-01 | Older than 30 days (absolute date) |

## Examples

### Daily review workflow

```bash
# See recent captures
cub captures --since 1d

# Review a specific capture
cub captures show cap-042

# Import important ones to project
cub captures import cap-042
```

### Search and filter

```bash
# Find all authentication-related captures
cub captures --search "auth"

# Find high-priority bugs
cub captures --tag bug | grep -E "Pri.*1"
```

### Export for processing

```bash
# Get all captures as JSON
cub captures --all --json > captures_backup.json
```

## Related Commands

- [`cub capture`](capture.md) - Create a new capture
- [`cub triage`](triage.md) - Process captures into actions
- [`cub organize-captures`](organize-captures.md) - Normalize capture files

## See Also

- [Roadmap](../contributing/roadmap.md) - Planned features and backlog
- [Task Management](../guide/tasks/index.md) - Working with tasks

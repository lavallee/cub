---
title: cub organize-captures
description: Organize and normalize capture files by adding missing frontmatter and fixing filenames.
---

# cub organize-captures

Organize and normalize capture files by adding missing frontmatter and fixing filenames.

## Synopsis

```bash
cub organize-captures [OPTIONS]
```

## Description

The `cub organize-captures` command scans your captures directory and normalizes files that were added manually or have incomplete metadata. This is useful when:

- You've manually created markdown files in the captures directory
- Captures are missing required frontmatter fields
- Filenames don't follow the standard naming convention
- You want to ensure all captures have valid IDs

The command performs these normalizations:

1. **Adds missing frontmatter** to plain markdown files
2. **Generates IDs** for captures without valid `cap-NNN` identifiers
3. **Renames files** to follow the `YYYY-MM-DD-slug.md` convention
4. **Ensures required fields** (id, created, title, source) are present

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--dry-run` | | Show what would be changed without making changes |
| `--yes` | `-y` | Skip confirmation prompt |
| `--global` | `-g` | Organize global captures directory instead of project |
| `--help` | `-h` | Show help message and exit |

## What Gets Fixed

### Missing Frontmatter

Files without YAML frontmatter get it added:

**Before:**
```markdown
This is a raw note about improving error handling.
```

**After:**
```markdown
---
id: cap-043
created: 2026-01-17T10:30:00Z
title: This is a raw note about improving error handling
tags: []
source: manual
status: active
---

This is a raw note about improving error handling.
```

### Invalid or Missing ID

Files with missing or malformed IDs get valid ones:

**Before:**
```markdown
---
title: Some capture
created: 2026-01-17
---
Content here.
```

**After:**
```markdown
---
id: cap-043
title: Some capture
created: 2026-01-17
source: manual
---
Content here.
```

### Non-Standard Filenames

Files with non-standard names can be renamed:

| Before | After |
|--------|-------|
| `my-note.md` | `2026-01-17-my-note.md` |
| `idea.md` | `2026-01-17-idea.md` |
| `random_file.md` | `2026-01-17-random-file.md` |

Standard formats that are kept:

- `cap-NNN.md` (ID-based)
- `YYYY-MM-DD-slug.md` (date-based)
- `project-cap-YYYYMMDD-slug.md` (full format)

## Process Flow

1. **Scan** - Find all `.md` files in the captures directory
2. **Analyze** - Check each file for issues
3. **Report** - Display proposed changes in a table
4. **Confirm** - Ask for confirmation (unless `--yes`)
5. **Apply** - Make the changes
6. **Summarize** - Report success/failure counts

## Examples

### Preview changes (dry run)

```bash
cub organize-captures --dry-run
```

Output:
```
Scanning 15 markdown files in project captures...

Proposed Changes
+------------------+----------------------+--------------------------------+
| File             | Issue                | Action                         |
+------------------+----------------------+--------------------------------+
| raw-note.md      | Missing frontmatter  | Add frontmatter with ID, title |
| old-idea.md      | Invalid or missing ID| Generate valid cap-NNN ID      |
| my-thoughts.md   | Non-standard filename| Rename to 2026-01-15-my-...    |
+------------------+----------------------+--------------------------------+

3 files need normalization.

Dry run mode - no changes made.
```

### Organize project captures

```bash
cub organize-captures
```

Output:
```
Scanning 15 markdown files in project captures...

Proposed Changes
+------------------+----------------------+--------------------------------+
| File             | Issue                | Action                         |
+------------------+----------------------+--------------------------------+
| raw-note.md      | Missing frontmatter  | Add frontmatter with ID, title |
+------------------+----------------------+--------------------------------+

1 files need normalization.

Apply these changes? [y/N]: y

Applying changes...
[check] Successfully organized 1 files.
```

### Organize global captures

```bash
cub organize-captures --global
```

Organizes files in `~/.local/share/cub/captures/{project}/` instead of `./captures/`.

### Skip confirmation

```bash
cub organize-captures --yes
```

Applies changes without asking for confirmation.

### Combined options

```bash
cub organize-captures --global --dry-run
```

Preview changes to global captures without applying.

## Title Generation

When adding frontmatter to files without it, the title is extracted from:

1. **First line** of the content (if it's short enough)
2. **First 80 characters** (truncated with `...` if longer)

## Source Field

New captures get `source: manual` to indicate they were added manually rather than through `cub capture`.

## Error Handling

Files that can't be parsed generate errors:

```
Proposed Changes
+------------------+----------------------+--------------------------------+
| File             | Issue                | Action                         |
+------------------+----------------------+--------------------------------+
| corrupt.md       | Parse error: ...     | Manual review needed           |
+------------------+----------------------+--------------------------------+
```

Files with "Manual review needed" are skipped during the apply phase.

## Safe Operations

The command is designed to be safe:

- **Dry run first**: Always preview with `--dry-run` if unsure
- **Confirmation required**: Won't apply without explicit confirmation
- **Non-destructive**: Original content is preserved
- **Atomic updates**: Files are fully written before old versions are removed

## When to Use

### After Manual File Creation

If you create capture files by hand:

```bash
echo "My idea" > captures/my-idea.md
cub organize-captures
```

### After Importing Files

If you copy markdown files from elsewhere:

```bash
cp ~/notes/*.md captures/
cub organize-captures
```

### Periodic Cleanup

Run periodically to ensure consistency:

```bash
cub organize-captures --dry-run  # Check first
cub organize-captures            # Fix if needed
```

## Related Commands

- [`cub capture`](capture.md) - Create properly formatted captures
- [`cub captures`](captures.md) - List and manage captures
- [`cub investigate`](investigate.md) - Process captures into actions

## See Also

- [Roadmap](../contributing/roadmap.md) - Planned features and backlog
- [Task Management](../guide/tasks/index.md) - Working with tasks

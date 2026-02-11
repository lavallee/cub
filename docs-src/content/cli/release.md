---
title: cub release
description: Mark work as released and update version history, CHANGELOG, and git tags.
---

# cub release

Mark a plan or epic as released, update the CHANGELOG, and optionally create a git tag.

---

## Synopsis

```bash
cub release <EPIC_ID> <VERSION> [OPTIONS]
```

---

## Description

The `release` command formalizes completed work into a versioned release. It performs several coordinated actions:

- **Updates plan status** to "released" in the ledger
- **Updates CHANGELOG.md** with release information gathered from completed tasks
- **Creates a git tag** for the version (unless `--no-tag` is specified)
- **Moves spec files** from their current location to `specs/released/`

This command is typically run after all tasks in an epic are complete, tests pass, and the work has been reviewed. It creates a clean boundary between development and release.

---

## Arguments

| Argument | Description |
|----------|-------------|
| `EPIC_ID` | The epic or plan ID being released (e.g., `cub-048a`) |
| `VERSION` | Version string for the release (e.g., `v1.0`, `v0.30-alpha`) |

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--dry-run` | | Preview all changes without applying them |
| `--no-tag` | | Skip creating a git tag for the release |
| `--help` | `-h` | Show help message and exit |

---

## Examples

### Standard Release

```bash
cub release cub-048a v1.0
```

Updates the ledger, appends to CHANGELOG.md, creates a `v1.0` git tag, and moves specs to `specs/released/`.

### Preview Changes

```bash
cub release cub-048a v1.0 --dry-run
```

Output:

```
Dry run — no changes will be made.

Would update:
  - Ledger: mark cub-048a as released (v1.0)
  - CHANGELOG.md: append release section with 8 task summaries
  - Git tag: create v1.0
  - Specs: move specs/staged/auth-flow.md → specs/released/auth-flow.md
```

### Release Without Git Tag

```bash
cub release cub-048a v1.0 --no-tag
```

Performs all release actions except creating the git tag. Useful when tagging is handled by a separate CI/CD pipeline.

---

## What Gets Updated

### CHANGELOG.md

A new release section is appended with:

- Version number and date
- Summary of completed tasks from the epic
- Links to relevant specs and plans

### Ledger

The plan or epic entry in the ledger is updated with:

- Status set to `released`
- Release version recorded
- Release timestamp

### Spec Files

Specs associated with the released epic move through the lifecycle:

```
specs/staged/my-feature.md  →  specs/released/my-feature.md
```

### Git Tag

A lightweight git tag is created at the current HEAD:

```
v1.0  →  points to current commit
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Release completed successfully |
| `1` | Error (epic not found, CHANGELOG write failed, git tag failed) |

---

## Related Commands

- [`cub retro`](retro.md) - Generate retrospective report before or after release
- [`cub ledger show`](ledger.md) - View completed work in the ledger
- [`cub stage`](stage.md) - Import tasks from plans (upstream of release)

---

## See Also

- [Release Workflow Guide](../guide/releases/index.md) - End-to-end release process
- [Spec Lifecycle](../guide/specs/lifecycle.md) - How specs move through stages
- [CHANGELOG Management](../guide/releases/changelog.md) - CHANGELOG conventions

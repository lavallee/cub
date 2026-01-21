---
title: cub plan
description: Run the planning pipeline to transform specs into executable tasks.
---

# cub plan

Run the planning pipeline to transform specs into structured, agent-executable tasks through a three-stage process.

---

## Synopsis

```bash
cub plan <subcommand> [OPTIONS]
```

---

## Description

The `cub plan` command provides a three-stage pipeline to convert feature specs into executable tasks:

1. **Orient** - Research and understand the problem space
2. **Architect** - Design the technical approach
3. **Itemize** - Break into agent-sized tasks

Use `cub plan run` to execute all stages, or run individual stages for more control.

---

## Subcommands

### cub plan run

Run the full planning pipeline.

```bash
cub plan run [SPEC] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `SPEC` | Spec path or name (auto-discovers VISION.md if not provided) |

**Options:**

| Option | Description |
|--------|-------------|
| `--depth TEXT` | Orient depth: `light`, `standard`, `deep` (default: standard) |
| `--mindset TEXT` | Technical mindset: `prototype`, `mvp`, `production`, `enterprise` (default: mvp) |
| `--scale TEXT` | Expected scale: `personal`, `team`, `product`, `internet-scale` (default: team) |
| `--slug TEXT` | Explicit plan slug (default: derived from spec) |
| `--continue`, `-c` | Resume from existing plan slug |
| `--no-move-spec` | Don't move spec to planned/ on completion |
| `--non-interactive`, `--auto` | Run without user interaction (CI/automation) |
| `--project-root PATH` | Project root directory |
| `-v`, `--verbose` | Show detailed output |

**Examples:**

```bash
# Full pipeline from spec
cub plan run specs/researching/auth.md

# Auto-discover vision document
cub plan run

# With options
cub plan run auth.md --depth deep --mindset production

# Resume incomplete plan
cub plan run --continue my-feature

# CI/automation mode
cub plan run auth.md --non-interactive
```

---

### cub plan orient

Research and understand the problem space.

```bash
cub plan orient [SPEC] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `SPEC` | Spec ID or path to orient from |

**Options:**

| Option | Description |
|--------|-------------|
| `--depth TEXT` | Orient depth: `light`, `standard`, `deep` |
| `--slug TEXT` | Explicit plan slug |
| `--project-root PATH` | Project root directory |
| `-v`, `--verbose` | Show detailed output |

**Output:** `plans/{slug}/orientation.md`

**Examples:**

```bash
cub plan orient specs/researching/auth.md
cub plan orient auth.md --depth deep
cub plan orient auth.md --slug user-auth
```

---

### cub plan architect

Design the solution architecture.

```bash
cub plan architect [PLAN_SLUG] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PLAN_SLUG` | Plan slug to continue (default: most recent) |

**Options:**

| Option | Description |
|--------|-------------|
| `--spec TEXT` | Find plan by spec name |
| `--mindset TEXT` | Technical mindset: `prototype`, `mvp`, `production`, `enterprise` |
| `--scale TEXT` | Expected scale: `personal`, `team`, `product`, `internet-scale` |
| `--project-root PATH` | Project root directory |
| `-v`, `--verbose` | Show detailed output |

**Output:** `plans/{slug}/architecture.md`

**Examples:**

```bash
cub plan architect
cub plan architect my-feature
cub plan architect --mindset production --scale product
```

---

### cub plan itemize

Break architecture into actionable tasks.

```bash
cub plan itemize [PLAN_SLUG] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PLAN_SLUG` | Plan slug to itemize (default: most recent) |

**Options:**

| Option | Description |
|--------|-------------|
| `--spec TEXT` | Find plan by spec name |
| `--project-root PATH` | Project root directory |
| `-v`, `--verbose` | Show detailed output |

**Output:** `plans/{slug}/itemized-plan.md`

**Examples:**

```bash
cub plan itemize
cub plan itemize my-feature
cub plan itemize --spec auth-feature
```

---

### cub plan list

List all existing plans.

```bash
cub plan list [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--project-root PATH` | Project root directory |
| `-v`, `--verbose` | Show stage-by-stage status |

**Examples:**

```bash
cub plan list
cub plan list --verbose
```

---

## Plan Directory Structure

Plans are stored in `plans/{slug}/`:

```
plans/my-feature/
├── plan.json          # Plan metadata
├── orientation.md     # Orient stage output
├── architecture.md    # Architect stage output
└── itemized-plan.md   # Itemize stage output
```

---

## Vision Document Discovery

If no spec is provided, `cub plan run` looks for documents in this order:

1. **VISION.md** in project root
2. **docs/PRD.md** - Product requirements document
3. **docs/VISION.md** - Alternative location

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error occurred |

---

## Related Commands

- [`cub spec`](spec.md) - Create specs interactively
- [`cub stage`](stage.md) - Import tasks after planning
- [`cub run`](run.md) - Execute tasks

---

## See Also

- [Plan Flow Guide](../guide/prep-pipeline/index.md) - Detailed pipeline documentation
- [Orient Stage](../guide/prep-pipeline/orient.md) - Problem research
- [Architect Stage](../guide/prep-pipeline/architect.md) - Technical design
- [Itemize Stage](../guide/prep-pipeline/itemize.md) - Task decomposition

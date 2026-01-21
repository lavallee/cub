---
title: cub spec
description: Create feature specifications through an interactive interview.
---

# cub spec

Create feature specifications through an AI-guided interactive interview process.

---

## Synopsis

```bash
cub spec [TOPIC] [OPTIONS]
```

---

## Description

The `spec` command launches an interactive interview session that helps you articulate a feature idea and produces a structured spec file in `specs/researching/`.

The interview covers:

- Problem space exploration
- Goals and non-goals
- Dependencies and constraints
- Open questions and readiness assessment

---

## Arguments

| Argument | Description |
|----------|-------------|
| `TOPIC` | Feature name or brief description to start the interview (optional) |

---

## Options

| Option | Description |
|--------|-------------|
| `-l`, `--list` | List specs in researching stage |
| `-h`, `--help` | Show help message |

---

## Examples

### Start Interview with Topic

```bash
cub spec "user authentication"
```

### Start Interview (No Topic)

```bash
cub spec
```

### List Researching Specs

```bash
cub spec --list
```

---

## Output

Specs are created in `specs/researching/`:

```
specs/researching/user-authentication.md
```

Each spec includes YAML frontmatter with metadata:

```yaml
---
title: User Authentication
created: 2026-01-20
readiness:
  score: 7
  blockers:
    - Need to decide on OAuth providers
---
```

---

## Spec Lifecycle

Specs move through stages as work progresses:

```
specs/
├── researching/   # Active exploration (cub spec creates here)
├── planned/       # Plan exists (after cub plan run)
├── staged/        # Tasks in backend (after cub stage)
├── implementing/  # Active work (during cub run)
└── released/      # Shipped
```

---

## List Output

```bash
$ cub spec --list

Specs in researching (3):

  user-auth [7/10]
    User Authentication System

  dark-mode [5/10]
    Dark Mode Theme Support

  api-v2 [3/10]
    API Version 2 Design

View a spec: cat specs/researching/<name>.md
Plan a spec: cub plan run specs/researching/<name>.md
```

The number in brackets is the readiness score (0-10).

---

## Requirements

- **Claude Code** must be installed for the interactive interview
- The `/cub:spec` skill must be available

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (e.g., Claude not found) |

---

## Related Commands

- [`cub plan`](plan.md) - Plan a spec
- [`cub stage`](stage.md) - Stage planned tasks
- [`cub capture`](capture.md) - Quick idea capture

---

## See Also

- [Plan Flow Guide](../guide/prep-pipeline/index.md) - Complete workflow overview

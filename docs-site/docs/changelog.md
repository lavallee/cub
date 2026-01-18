# Changelog

All notable changes to Cub are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

[:octicons-tag-24: View All Releases](https://github.com/lavallee/cub/releases){ .md-button }
[:octicons-file-code-24: Full Changelog](https://github.com/lavallee/cub/blob/main/CHANGELOG.md){ .md-button .md-button--primary }

---

## Versioning Scheme

!!! info "Semantic Versioning"

    Cub follows [Semantic Versioning](https://semver.org/):

    - **MAJOR**: Breaking changes (currently 0.x during active development)
    - **MINOR**: New features, backward compatible
    - **PATCH**: Bug fixes, backward compatible

    Until v1.0, minor versions may include breaking changes. Check the upgrade notes for each release.

---

## Recent Releases

### v0.26.x - Captures & Releases

!!! success "Current Release"

    **v0.26.3** (2026-01-18)

#### Highlights

- **Consolidated PR management** - `cub pr` and `cub merge` commands in Python
- **GitHub issue integration** - Work through GitHub issues in `cub run`
- **Streaming output fixes** - Real-time display now flushes properly
- **CLI help reorganization** - Commands grouped by function

#### Key Changes

| Version | Date | Highlights |
|---------|------|------------|
| 0.26.3 | 2026-01-18 | PR/merge commands, CLI help reorg |
| 0.26.2 | 2026-01-17 | Non-interactive prep mode |
| 0.26.1 | 2026-01-16 | Captures system, investigate command |
| 0.26.0 | 2026-01-16 | Auto-generate changelog, AI capture titles |

---

### v0.25.x - Sandbox Mode

!!! abstract "Isolation & Safety"

    Docker-based sandboxing for running cub with full isolation and review capabilities.

#### Highlights

- **SandboxProvider Protocol** - Pluggable provider interface
- **DockerProvider** - Full filesystem and network isolation
- **`--sandbox` flag** - Run tasks in Docker isolation
- **`cub sandbox` subcommands** - Manage sandbox lifecycle

#### Key Features

```bash
# Run in sandbox
cub run --sandbox

# Review changes before applying
cub sandbox diff
cub sandbox apply
```

---

### v0.24.x - Git Worktrees

!!! abstract "Parallel Development"

    Support for running cub in isolated worktrees and processing multiple tasks concurrently.

#### Highlights

- **WorktreeManager** - Core worktree management
- **`--worktree` flag** - Run in isolated worktree
- **`--parallel N` flag** - Concurrent task execution
- **`cub worktree` subcommands** - CLI for worktree management

#### Key Features

```bash
# Run in worktree
cub run --worktree

# Parallel execution
cub run --parallel 4
```

---

### v0.23.x - Live Dashboard & Hybrid CLI

!!! abstract "Real-Time Monitoring"

    Rich-based terminal UI and tmux integration for split-pane workflows.

#### Highlights

- **Rich Dashboard** - Task progress visualization
- **Tmux Integration** - `--monitor` flag for split pane
- **Hybrid CLI** - Python + Bash delegation
- **`cub audit`** - Codebase health checking

#### Key Features

```bash
# Live monitoring
cub run --monitor

# Or standalone dashboard
cub monitor
```

---

### v0.21.x - Python Core Migration

!!! abstract "Foundation Release"

    Complete Python implementation of cub's core functionality.

#### Highlights

- **Python 3.10+** - Modern Python foundation
- **Pydantic v2** - Type-safe models
- **10-50x faster** - No jq subprocess overhead
- **Full compatibility** - Same workflow, faster execution

See [Upgrading Guide](getting-started/upgrading.md) for migration details.

---

### v0.20.x - Guardrails System

!!! abstract "Institutional Memory"

    Capture, preserve, and apply project-specific lessons learned.

#### Highlights

- **`.cub/guardrails.md`** - Store lessons learned
- **Auto-learn from failures** - Extract lessons automatically
- **`cub guardrails`** - Show, add, learn, curate commands
- **Task prompt integration** - Guardrails included in prompts

---

### v0.19.x - Git Workflow Integration

!!! abstract "Branch & PR Management"

    Branch-epic bindings, checkpoints, and PR management.

#### Highlights

- **`cub branch`** - Create and bind branches to epics
- **`cub checkpoints`** - Review gates that block tasks
- **`cub pr`** - Auto-generate PRs from epic work

---

### v0.16.x - v0.18.x - Planning & Interview

!!! abstract "Vision to Tasks"

    Transform product visions into executable tasks.

#### Highlights

- **Interview Mode** (v0.16) - Deep questioning to refine task specs
- **PRD Import** (v0.17) - Import from Markdown, JSON, GitHub, PDF
- **Project Init** (v0.18) - Interactive setup with templates
- **Prep Pipeline** (v0.18.1) - Triage -> Architect -> Plan -> Bootstrap

---

## Full Version History

| Version | Date | Highlight |
|---------|------|-----------|
| 0.26.3 | 2026-01-18 | PR/merge commands |
| 0.26.0 | 2026-01-16 | Auto-changelog, captures |
| 0.25.0 | 2026-01-16 | Sandbox mode |
| 0.24.0 | 2026-01-16 | Git worktrees |
| 0.23.0 | 2026-01-15 | Live dashboard |
| 0.21.0 | 2026-01-15 | Python migration |
| 0.20.0 | 2026-01-14 | Guardrails system |
| 0.19.0 | 2026-01-14 | Git workflow |
| 0.18.0 | 2026-01-14 | Project organization |
| 0.17.0 | 2026-01-14 | PRD import |
| 0.16.0 | 2026-01-14 | Interview mode |
| 0.15.0 | 2026-01-14 | Plan review |
| 0.14.0 | 2026-01-13 | Vision-to-tasks pipeline |
| 0.13.0 | 2026-01-13 | Rename Curb -> Cub |
| 0.12.0 | 2026-01-13 | Modular architecture |
| 0.11.0 | 2026-01-11 | Guardrails, failure handling |
| 0.10.0 | 2026-01-10 | Git workflow |
| 0.9.0 | 2026-01-10 | Subcommand CLI |
| 0.8.0 | 2026-01-10 | Sessions & artifacts |
| 0.7.0 | 2026-01-10 | Documentation |
| 0.6.0 | 2026-01-10 | Budget tracking |
| 0.5.0 | 2026-01-10 | Config & logging |
| 0.4.0 | 2026-01-09 | Codex support |
| 0.3.0 | 2026-01-09 | GitHub Actions |
| 0.2.0 | 2026-01-09 | Beads backend |
| 0.1.0 | 2026-01-09 | Initial release |

---

## Upgrade Notes

### v0.20.x to v0.21.x (Bash to Python)

!!! warning "Major Migration"

    See the complete [Upgrading Guide](getting-started/upgrading.md) for detailed steps.

Key changes:

- Python 3.10+ required
- Virtual environment required
- jq no longer needed
- 10-50x performance improvement

### v0.12.x to v0.13.x (Curb to Cub)

- Update all `curb` references to `cub`
- Rename config: `.curb.json` -> `.cub.json`
- Update env vars: `CURB_*` -> `CUB_*`
- Move config dir: `~/.config/curb/` -> `~/.config/cub/`

### v0.8.x to v0.9.x (Flags to Subcommands)

| Old | New |
|-----|-----|
| `curb --init` | `curb init` |
| `curb --status` | `curb status` |
| `curb` | `curb run` |

Legacy flags show deprecation warnings but still work.

---

## Test Coverage

| Version | Tests |
|---------|-------|
| 0.23+ | 100+ pytest |
| 0.13.0 | 790 BATS |
| 0.11.0 | 732 BATS |
| 0.5.0 | 189 BATS |
| 0.1.0 | ~20 BATS |

---

## Links

- [:octicons-mark-github-16: GitHub Releases](https://github.com/lavallee/cub/releases)
- [:octicons-file-code-16: Full CHANGELOG.md](https://github.com/lavallee/cub/blob/main/CHANGELOG.md)
- [:octicons-issue-opened-16: Report an Issue](https://github.com/lavallee/cub/issues/new)

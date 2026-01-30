# Project Map: cub_sat

**Project Directory:** `/Users/lavallee/Experiments/cub_sat`

## Tech Stacks

- python

## Build Commands

- **cub**: `cub.cli:cli_main` (from pyproject.toml)
- **cub-hooks**: `cub.core.harness.hooks:cli_main` (from pyproject.toml)

## Key Files

- `README.md` (readme) - Project documentation
- `LICENSE` (license) - Project license
- `pyproject.toml` (config) - Python project configuration

## Modules

- **cub**: `src/cub` (258 files) (entry: __init__.py)

## Directory Structure

└── cub_sat/
    ├── .beads/
    │   ├── .gitignore
    │   ├── README.md
    │   ├── beads.db
    │   ├── beads.db-shm
    │   ├── beads.db-wal
    │   ├── config.yaml
    │   ├── interactions.jsonl
    │   └── metadata.json
    ├── .claude/
    │   ├── commands/
    │   │   ├── cub.md
    │   │   ├── cub:architect.md
    │   │   ├── cub:audit.md
    │   │   ├── cub:capture.md
    │   │   ├── cub:doctor.md
    │   │   ├── cub:itemize.md
    │   │   ├── cub:ledger.md
    │   │   ├── cub:orient.md
    │   │   ├── cub:plan.md
    │   │   ├── cub:run.md
    │   │   ├── cub:spec-to-issues.md
    │   │   ├── cub:spec.md
    │   │   ├── cub:status.md
    │   │   ├── cub:suggest.md
    │   │   ├── cub:tasks.md
    │   │   └── cub:triage.md
    │   ├── settings.json
    │   └── settings.local.json
    ├── .cub/
    │   ├── cache/
    │   │   └── code_intel/
    │   │       ├── 68/
    │   │       ├── a1/
    │   │       ├── cache.db
    │   │       ├── cache.db-shm
    │   │       └── cache.db-wal
    │   ├── docs/
    │   │   ├── claude-code-hooks.md
    │   │   └── run-exit-paths.md
    │   ├── hooks/
    │   │   ├── README.md
    │   │   ├── post-tool-use.sh
    │   │   ├── session-end.sh
    │   │   ├── session-start.sh
    │   │   └── stop.sh
    │   ├── ledger/
    │   │   ├── by-epic/
    │   │   │   ├── cub-a1f/
    │   │   │   ├── cub-a2s/
    │   │   │   ├── cub-a3r/
    │   │   │   ├── cub-a4e/
    │   │   │   ├── cub-b1a/
    │   │   │   ├── cub-b1b/
    │   │   │   ├── cub-b1c/
    │   │   │   ├── cub-b1d/
    │   │   │   ├── cub-b1e/
    │   │   │   ├── cub-b1f/
    │   │   │   ├── cub-c5i/
    │   │   │   ├── cub-d8b/
    │   │   │   ├── cub-j1a/
    │   │   │   ├── cub-j1b/
    │   │   │   ├── cub-j1c/
    │   │   │   ├── cub-j1d/
    │   │   │   ├── cub-j1e/
    │   │   │   ├── cub-j1f/
    │   │   │   ├── cub-m3k/
    │   │   │   ├── cub-p1t/
    │   │   │   ├── cub-p2c/
    │   │   │   ├── cub-p3s/
    │   │   │   ├── cub-p9q/
    │   │   │   ├── cub-q2j/
    │   │   │   ├── cub-r1a/
    │   │   │   ├── cub-r1b/
    │   │   │   ├── cub-r1c/
    │   │   │   ├── cub-r1d/
    │   │   │   ├── cub-r2v/
    │   │   │   ├── cub-r4h/
    │   │   │   ├── cub-r5c/
    │   │   │   ├── cub-r6s/
    │   │   │   ├── cub-r9d/
    │   │   │   ├── cub-t5w/
    │   │   │   ├── cub-v8n/
    │   │   │   ├── cub-w3f/
    │   │   │   ├── cub-x3s/
    │   │   │   └── cub-x7f/
    │   │   ├── by-task/
    │   │   │   ├── cub-001/
    │   │   │   ├── cub-a1f.1/
    │   │   │   ├── cub-a1f.2/
    │   │   │   ├── cub-a2s.1/
    │   │   │   ├── cub-a3r.1/
    │   │   │   ├── cub-a3r.2/
    │   │   │   ├── cub-a3r.3/
    │   │   │   ├── cub-a4e.1/
    │   │   │   ├── cub-a4e.2/
    │   │   │   ├── cub-a4e.3/
    │   │   │   ├── cub-b1a.1/
    │   │   │   ├── cub-b1a.2/
    │   │   │   ├── cub-b1a.3/
    │   │   │   ├── cub-b1a.4/
    │   │   │   ├── cub-b1a.5/
    │   │   │   ├── cub-b1b.1/
    │   │   │   ├── cub-b1b.2/
    │   │   │   ├── cub-b1b.3/
    │   │   │   ├── cub-b1b.4/
    │   │   │   ├── cub-b1b.5/
    │   │   │   ├── cub-b1c.1/
    │   │   │   ├── cub-b1c.2/
    │   │   │   ├── cub-b1c.3/
    │   │   │   ├── cub-b1c.4/
    │   │   │   ├── cub-b1d.1/
    │   │   │   ├── cub-b1d.2/
    │   │   │   ├── cub-b1d.3/
    │   │   │   ├── cub-b1e.1/
    │   │   │   ├── cub-b1e.2/
    │   │   │   ├── cub-b1e.3/
    │   │   │   ├── cub-b1f.1/
    │   │   │   ├── cub-b1f.2/
    │   │   │   ├── cub-b1f.3/
    │   │   │   ├── cub-c5i.1/
    │   │   │   ├── cub-c5i.2/
    │   │   │   ├── cub-c5i.3/
    │   │   │   ├── cub-c5i.4/
    │   │   │   ├── cub-c5i.5/
    │   │   │   ├── cub-d8b.1/
    │   │   │   ├── cub-d8b.2/
    │   │   │   ├── cub-d8b.3/
    │   │   │   ├── cub-e2p.1/
    │   │   │   ├── cub-e2p.2/
    │   │   │   ├── cub-e2p.3/
    │   │   │   ├── cub-fail/
    │   │   │   ├── cub-j1a.1/
    │   │   │   ├── cub-j1a.2/
    │   │   │   ├── cub-j1a.3/
    │   │   │   ├── cub-j1a.4/
    │   │   │   ├── cub-j1a.5/
    │   │   │   ├── cub-j1b.1/
    │   │   │   ├── cub-j1b.2/
    │   │   │   ├── cub-j1b.3/
    │   │   │   ├── cub-j1b.4/
    │   │   │   ├── cub-j1c.1/
    │   │   │   ├── cub-j1c.2/
    │   │   │   ├── cub-j1c.3/
    │   │   │   ├── cub-j1c.4/
    │   │   │   ├── cub-j1c.5/
    │   │   │   ├── cub-j1d.1/
    │   │   │   ├── cub-j1d.2/
    │   │   │   ├── cub-j1e.1/
    │   │   │   ├── cub-j1e.2/
    │   │   │   ├── cub-j1e.3/
    │   │   │   ├── cub-j1f.1/
    │   │   │   ├── cub-j1f.2/
    │   │   │   ├── cub-j1f.3/
    │   │   │   ├── cub-m3k.1/
    │   │   │   ├── cub-m3k.2/
    │   │   │   ├── cub-m3k.3/
    │   │   │   ├── cub-m3k.4/
    │   │   │   ├── cub-m3k.5/
    │   │   │   ├── cub-m3k.6/
    │   │   │   ├── cub-m3k.7/
    │   │   │   ├── cub-p1t.1/
    │   │   │   ├── cub-p1t.2/
    │   │   │   ├── cub-p1t.3/
    │   │   │   ├── cub-p1t.4/
    │   │   │   ├── cub-p1t.5/
    │   │   │   ├── cub-p2c.1/
    │   │   │   ├── cub-p2c.2/
    │   │   │   ├── cub-p2c.3/
    │   │   │   ├── cub-p2c.4/
    │   │   │   ├── cub-p2c.5/
    │   │   │   ├── cub-p3s.1/
    │   │   │   ├── cub-p3s.2/
    │   │   │   ├── cub-p9q.1/
    │   │   │   ├── cub-p9q.3/
    │   │   │   ├── cub-p9q.4/
    │   │   │   ├── cub-p9q.5/
    │   │   │   ├── cub-q2j.1/
    │   │   │   ├── cub-q2j.2/
    │   │   │   ├── cub-q2j.3/
    │   │   │   ├── cub-q2j.4/
    │   │   │   ├── cub-q2j.5/
    │   │   │   ├── cub-r1a/
    │   │   │   ├── cub-r1a.1/
    │   │   │   ├── cub-r1a.2/
    │   │   │   ├── cub-r1a.3/
    │   │   │   ├── cub-r1b.1/
    │   │   │   ├── cub-r1b.2/
    │   │   │   ├── cub-r1b.3/
    │   │   │   ├── cub-r1b.4/
    │   │   │   ├── cub-r1b.5/
    │   │   │   ├── cub-r1c.1/
    │   │   │   ├── cub-r1c.2/
    │   │   │   ├── cub-r1c.3/
    │   │   │   ├── cub-r1c.4/
    │   │   │   ├── cub-r1d.1/
    │   │   │   ├── cub-r1d.2/
    │   │   │   ├── cub-r1d.3/
    │   │   │   ├── cub-r2v.1/
    │   │   │   ├── cub-r2v.2/
    │   │   │   ├── cub-r2v.3/
    │   │   │   ├── cub-r2v.4/
    │   │   │   ├── cub-r4h.1/
    │   │   │   ├── cub-r4h.2/
    │   │   │   ├── cub-r4h.3/
    │   │   │   ├── cub-r4h.4/
    │   │   │   ├── cub-r5c.1/
    │   │   │   ├── cub-r5c.2/
    │   │   │   ├── cub-r5c.3/
    │   │   │   ├── cub-r5c.4/
    │   │   │   ├── cub-r5c.5/
    │   │   │   ├── cub-r6s.1/
    │   │   │   ├── cub-r6s.2/
    │   │   │   ├── cub-r6s.3/
    │   │   │   ├── cub-r6s.4/
    │   │   │   ├── cub-r6s.5/
    │   │   │   ├── cub-r6s.6/
    │   │   │   ├── cub-r9d.1/
    │   │   │   ├── cub-r9d.2/
    │   │   │   ├── cub-r9d.3/
    │   │   │   ├── cub-r9d.4/
    │   │   │   ├── cub-specific/
    │   │   │   ├── cub-success/
    │   │   │   ├── cub-t5w.1/
    │   │   │   ├── cub-t5w.2/
    │   │   │   ├── cub-t5w.3/
    │   │   │   ├── cub-t5w.4/
    │   │   │   ├── cub-v8n.1/
    │   │   │   ├── cub-v8n.2/
    │   │   │   ├── cub-v8n.3/
    │   │   │   ├── cub-v8n.4/
    │   │   │   ├── cub-w3f.1/
    │   │   │   ├── cub-w3f.2/
    │   │   │   ├── cub-w3f.3/
    │   │   │   ├── cub-w3f.4/
    │   │   │   ├── cub-w3f.5/
    │   │   │   ├── cub-x3s.1/
    │   │   │   ├── cub-x3s.2/
    │   │   │   ├── cub-x3s.3/
    │   │   │   ├── cub-x3s.4/
    │   │   │   ├── cub-x7f.1/
    │   │   │   ├── cub-x7f.2/
    │   │   │   ├── cub-x7f.3/
    │   │   │   ├── cub-x7f.4/
    │   │   │   ├── cub-x7f.5/
    │   │   │   ├── cub-001.json
    │   │   │   ├── cub-0qf0.json
    │   │   │   ├── cub-12be.json
    │   │   │   ├── cub-4eyt.json
    │   │   │   ├── cub-4fma.json
    │   │   │   ├── cub-a1f.1.json
    │   │   │   ├── cub-a1f.2.json
    │   │   │   ├── cub-a2s.1.json
    │   │   │   ├── cub-a3r.1.json
    │   │   │   ├── cub-a3r.2.json
    │   │   │   ├── cub-a3r.3.json
    │   │   │   ├── cub-a4e.1.json
    │   │   │   ├── cub-a4e.2.json
    │   │   │   ├── cub-a4e.3.json
    │   │   │   ├── cub-a7f.1.json
    │   │   │   ├── cub-a7f.2.json
    │   │   │   ├── cub-a7f.3.json
    │   │   │   ├── cub-a7f.4.json
    │   │   │   ├── cub-a7f.5.json
    │   │   │   ├── cub-aeim.json
    │   │   │   ├── cub-b1a.1.json
    │   │   │   ├── cub-b1a.2.json
    │   │   │   ├── cub-b1a.3.json
    │   │   │   ├── cub-b1a.4.json
    │   │   │   ├── cub-b1a.5.json
    │   │   │   ├── cub-b1b.1.json
    │   │   │   ├── cub-b1b.2.json
    │   │   │   ├── cub-b1b.3.json
    │   │   │   ├── cub-b1b.4.json
    │   │   │   ├── cub-b1b.5.json
    │   │   │   ├── cub-b1c.1.json
    │   │   │   ├── cub-b1c.2.json
    │   │   │   ├── cub-b1c.3.json
    │   │   │   ├── cub-b1c.4.json
    │   │   │   ├── cub-b1d.1.json
    │   │   │   ├── cub-b1d.2.json
    │   │   │   ├── cub-b1d.3.json
    │   │   │   ├── cub-b1e.1.json
    │   │   │   ├── cub-b1e.2.json
    │   │   │   ├── cub-b1e.3.json
    │   │   │   ├── cub-b1f.1.json
    │   │   │   ├── cub-b1f.2.json
    │   │   │   ├── cub-b1f.3.json
    │   │   │   ├── cub-c5i.1.json
    │   │   │   ├── cub-c5i.2.json
... (truncated to fit budget)
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

- **cub**: `src/cub` (288 files) (entry: __init__.py)

## Directory Structure

└── cub_sat/
    ├── .beads/
    │   ├── .gitignore
    │   ├── .local_version
    │   ├── README.md
    │   ├── bd.sock
    │   ├── beads.db
    │   ├── beads.db-shm
    │   ├── beads.db-wal
    │   ├── beads.left.jsonl
    │   ├── beads.left.meta.json
    │   ├── branches.yaml
    │   ├── config.yaml
    │   ├── daemon.lock
    │   ├── daemon.log
    │   ├── daemon.pid
    │   ├── interactions.jsonl
    │   ├── issues.jsonl
    │   ├── last-touched
    │   ├── metadata.json
    │   └── sync-state.json
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
    │   │   ├── cub:run.md
    │   │   ├── cub:spec-to-issues.md
    │   │   ├── cub:spec.md
    │   │   ├── cub:stage.md
    │   │   ├── cub:status.md
    │   │   ├── cub:suggest.md
    │   │   └── cub:tasks.md
    │   ├── settings.json
    │   └── settings.local.json
    ├── .cub/
    │   ├── cache/
    │   │   └── code_intel/
    │   │       ├── 0f/
    │   │       ├── 68/
    │   │       ├── 69/
    │   │       ├── a1/
    │   │       ├── fd/
    │   │       ├── cache.db
    │   │       ├── cache.db-shm
    │   │       └── cache.db-wal
    │   ├── docs/
    │   │   ├── claude-code-hooks.md
    │   │   └── run-exit-paths.md
    │   ├── hooks/
    │   │   ├── end-of-epic/
    │   │   ├── end-of-plan/
    │   │   ├── end-of-task/
    │   │   ├── pre-session/
    │   │   ├── README.md
    │   │   ├── post-tool-use.sh
    │   │   ├── session-end.sh
    │   │   ├── session-start.sh
    │   │   └── stop.sh
    │   ├── ledger/
    │   │   ├── by-epic/
    │   │   │   ├── cub-048a-0/
    │   │   │   ├── cub-048a-1/
    │   │   │   ├── cub-048a-2/
    │   │   │   ├── cub-048a-3/
    │   │   │   ├── cub-048a-4/
    │   │   │   ├── cub-048a-5/
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
    │   │   │   ├── cub-n6x/
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
    │   │   │   ├── cub-t44/
    │   │   │   ├── cub-t5w/
    │   │   │   ├── cub-v8n/
    │   │   │   ├── cub-w3f/
    │   │   │   ├── cub-x3s/
    │   │   │   └── cub-x7f/
    │   │   ├── by-run/
    │   │   │   ├── cub-20260204-165022/
    │   │   │   ├── cub-20260204-170945/
    │   │   │   ├── cub-20260204-172822/
    │   │   │   ├── cub-20260204-180030/
    │   │   │   ├── cub-20260204-215022.json
    │   │   │   ├── cub-20260204-215514.json
    │   │   │   ├── cub-20260204-215515.json
    │   │   │   ├── cub-20260204-220945.json
    │   │   │   ├── cub-20260204-221940.json
    │   │   │   ├── cub-20260204-221941.json
    │   │   │   ├── cub-20260204-222516.json
    │   │   │   ├── cub-20260204-222822.json
    │   │   │   ├── cub-20260204-223355.json
    │   │   │   ├── cub-20260204-223356.json
    │   │   │   ├── cub-20260204-230030.json
    │   │   │   ├── cub-20260204-231705.json
    │   │   │   ├── cub-20260204-231706.json
    │   │   │   ├── cub-20260204-231848.json
    │   │   │   ├── cub-20260204-232045.json
    │   │   │   ├── cub-20260207-032029.json
    │   │   │   ├── cub-20260207-032030.json
    │   │   │   ├── cub-20260207-032031.json
    │   │   │   ├── cub-20260207-032256.json
    │   │   │   ├── cub-20260207-032257.json
    │   │   │   ├── cub-20260207-033322.json
    │   │   │   ├── cub-20260207-033323.json
    │   │   │   ├── cub-20260207-033638.json
    │   │   │   ├── cub-20260207-033639.json
    │   │   │   ├── cub-20260207-034123.json
    │   │   │   ├── cub-20260207-034124.json
    │   │   │   ├── cub-20260207-034607.json
    │   │   │   └── cub-20260207-034608.json
    │   │   ├── by-task/
    │   │   │   ├── cub-001/
    │   │   │   ├── cub-048a-0.1/
    │   │   │   ├── cub-048a-0.2/
    │   │   │   ├── cub-048a-0.3/
    │   │   │   ├── cub-048a-0.4/
    │   │   │   ├── cub-048a-0.5/
    │   │   │   ├── cub-048a-1.1/
    │   │   │   ├── cub-048a-1.2/
    │   │   │   ├── cub-048a-1.3/
    │   │   │   ├── cub-048a-1.4/
    │   │   │   ├── cub-048a-1.5/
    │   │   │   ├── cub-048a-1.6/
    │   │   │   ├── cub-048a-2.1/
    │   │   │   ├── cub-048a-2.2/
    │   │   │   ├── cub-048a-2.3/
    │   │   │   ├── cub-048a-2.4/
    │   │   │   ├── cub-048a-3.1/
    │   │   │   ├── cub-048a-3.2/
    │   │   │   ├── cub-048a-3.3/
    │   │   │   ├── cub-048a-3.4/
    │   │   │   ├── cub-048a-4.1/
    │   │   │   ├── cub-048a-4.2/
    │   │   │   ├── cub-048a-4.3/
    │   │   │   ├── cub-048a-4.4/
    │   │   │   ├── cub-048a-4.5/
    │   │   │   ├── cub-048a-5.1/
    │   │   │   ├── cub-048a-5.2/
    │   │   │   ├── cub-048a-5.3/
    │   │   │   ├── cub-048a-5.4/
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
    │   │   │   ├── cub-n6x.1/
    │   │   │   ├── cub-n6x.10/
    │   │   │   ├── cub-n6x.11/
    │   │   │   ├── cub-n6x.2/
    │   │   │   ├── cub-n6x.3/
    │   │   │   ├── cub-n6x.4/
    │   │   │   ├── cub-n6x.5/
    │   │   │   ├── cub-n6x.6/
    │   │   │   ├── cub-n6x.7/
    │   │   │   ├── cub-n6x.8/
    │   │   │   ├── cub-n6x.9/
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
... (truncated to fit budget)
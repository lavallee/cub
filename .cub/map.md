# Project Map: cub

**Project Directory:** `/home/lavallee/clawdbot/cub`

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

- **cub**: `src/cub` (289 files) (entry: __init__.py)

## Directory Structure

└── cub/
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
    │   └── settings.json
    ├── .cub/
    │   ├── cache/
    │   │   └── code_intel/
    │   │       ├── 0f/
    │   │       ├── 68/
    │   │       ├── 69/
    │   │       ├── 98/
    │   │       ├── a1/
    │   │       ├── fd/
    │   │       └── cache.db
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
    │   │   │   ├── cub-20260207-034608.json
    │   │   │   ├── cub-20260211-173246.json
    │   │   │   ├── cub-20260211-200819.json
    │   │   │   └── cub-20260211-200820.json
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
... (truncated to fit budget)

## Ranked Symbols

Symbols ranked by importance (PageRank score):


### docs-src/site/assets/javascripts/lunr/tinyseg.js

- **TinySegmenter** (def, line 33, score: 0.0022)

### docs-src/site/assets/javascripts/lunr/wordcut.js

- **EventEmitter** (def, line 1283, score: 0.0022)
- **Glob** (def, line 1916, score: 0.0022)
- **GlobSync** (def, line 2597, score: 0.0022)
- **Item** (def, line 4485, score: 0.0022)
- **Minimatch** (def, line 3226, score: 0.0022)
- **_deepEqual** (def, line 793, score: 0.0022)
- **_throws** (def, line 927, score: 0.0022)
- **alphasort** (def, line 1589, score: 0.0022)
- **alphasorti** (def, line 1585, score: 0.0022)
- **arrayToHash** (def, line 6283, score: 0.0022)
- **balanced** (def, line 983, score: 0.0022)
- **braceExpand** (def, line 3349, score: 0.0022)
- **charSet** (def, line 3156, score: 0.0022)
- **childrenIgnored** (def, line 1803, score: 0.0022)
- **cleanUpNextTick** (def, line 4432, score: 0.0022)
- **clearStateChar** (def, line 3416, score: 0.0022)
- **collectNonEnumProps** (def, line 5432, score: 0.0022)
- **createIndexFinder** (def, line 5167, score: 0.0022)
- **createPredicateIndexFinder** (def, line 5137, score: 0.0022)
- **createReduce** (def, line 4701, score: 0.0022)
- **defaultClearTimeout** (def, line 4352, score: 0.0022)
- **defaultSetTimout** (def, line 4349, score: 0.0022)
- **deprecated** (def, line 6161, score: 0.0022)
- **deprecationWarning** (def, line 1684, score: 0.0022)
- **done** (def, line 1970, score: 0.0022)
- **drainQueue** (def, line 4447, score: 0.0022)
- **embrace** (def, line 1127, score: 0.0022)
- **escapeBraces** (def, line 1059, score: 0.0022)
- **expand** (def, line 1141, score: 0.0022)
- **expandTop** (def, line 1106, score: 0.0022)
- **expectedException** (def, line 911, score: 0.0022)
- **ext** (def, line 3174, score: 0.0022)
- **fail** (def, line 742, score: 0.0022)
- **filter** (def, line 4294, score: 0.0022)
- **filter** (def, line 3167, score: 0.0022)
- **finish** (def, line 1700, score: 0.0022)
- **formatArray** (def, line 6431, score: 0.0022)
- **formatError** (def, line 6426, score: 0.0022)
- **formatPrimitive** (def, line 6407, score: 0.0022)
- **formatProperty** (def, line 6451, score: 0.0022)
- **formatValue** (def, line 6294, score: 0.0022)
- **g** (def, line 1425, score: 0.0022)
- **getMessage** (def, line 725, score: 0.0022)
- **glob** (def, line 1878, score: 0.0022)
- **globSync** (def, line 2589, score: 0.0022)
- **globUnescape** (def, line 4033, score: 0.0022)
- **gte** (def, line 1137, score: 0.0022)
- **hasOwnProperty** (def, line 6667, score: 0.0022)
- **identity** (def, line 1123, score: 0.0022)
- **ignoreMap** (def, line 1604, score: 0.0022)
- **inflight** (def, line 3041, score: 0.0022)
- **inspect** (def, line 6208, score: 0.0022)
- **isArguments** (def, line 838, score: 0.0022)
- **isArray** (def, line 6533, score: 0.0022)
- **isBoolean** (def, line 6538, score: 0.0022)
- **isDate** (def, line 6583, score: 0.0022)
- **isError** (def, line 6588, score: 0.0022)
- **isFunction** (def, line 1548, score: 0.0022)
- **isFunction** (def, line 6594, score: 0.0022)
- **isIgnored** (def, line 1794, score: 0.0022)
- **isMatch** (def, line 421, score: 0.0022)
- **isNull** (def, line 6543, score: 0.0022)
- **isNullOrUndefined** (def, line 6548, score: 0.0022)
- **isNumber** (def, line 1552, score: 0.0022)
- **isNumber** (def, line 6553, score: 0.0022)
- **isObject** (def, line 6578, score: 0.0022)
- **isObject** (def, line 1556, score: 0.0022)
- **isPadded** (def, line 1130, score: 0.0022)
- **isPrimitive** (def, line 6599, score: 0.0022)
- **isRegExp** (def, line 6573, score: 0.0022)
- **isString** (def, line 6558, score: 0.0022)
- **isSymbol** (def, line 6563, score: 0.0022)
- **isUndefined** (def, line 1560, score: 0.0022)
- **isUndefined** (def, line 6568, score: 0.0022)
- **iterator** (def, line 4704, score: 0.0022)
- **lstatcb_** (def, line 2294, score: 0.0022)
- **lstatcb_** (def, line 2531, score: 0.0022)
- **lte** (def, line 1134, score: 0.0022)
- **make** (def, line 3258, score: 0.0022)
- **makeAbs** (def, line 1777, score: 0.0022)
- **makeRe** (def, line 3758, score: 0.0022)
- **makeres** (def, line 3051, score: 0.0022)
- **mark** (def, line 1753, score: 0.0022)
- **match** (def, line 3816, score: 0.0022)
- **maybeMatch** (def, line 998, score: 0.0022)
- **minimatch** (def, line 3208, score: 0.0022)
- **next** (def, line 2003, score: 0.0022)
- **noop** (def, line 4499, score: 0.0022)
- **normalizeArray** (def, line 4112, score: 0.0022)
- **numeric** (def, line 1053, score: 0.0022)
- **objEquiv** (def, line 842, score: 0.0022)
- **objectToString** (def, line 6611, score: 0.0022)
- **ok** (def, line 762, score: 0.0022)
- **once** (def, line 4062, score: 0.0022)
- **onceStrict** (def, line 4072, score: 0.0022)
- **ownProp** (def, line 1576, score: 0.0022)
- **pad** (def, line 6616, score: 0.0022)
- **parse** (def, line 3387, score: 0.0022)
- **parseCommaParts** (def, line 1079, score: 0.0022)
- **parseNegate** (def, line 3314, score: 0.0022)
- **posix** (def, line 4317, score: 0.0022)
- **range** (def, line 1004, score: 0.0022)
- **readdirCb** (def, line 2336, score: 0.0022)
- **reduceToSingleString** (def, line 6510, score: 0.0022)
- **regExpEscape** (def, line 4037, score: 0.0022)
- **replacer** (def, line 704, score: 0.0022)
- **runClearTimeout** (def, line 4400, score: 0.0022)
- **runTimeout** (def, line 4375, score: 0.0022)
- **s** (def, line 1, score: 0.0022)
- **setopts** (def, line 1617, score: 0.0022)
- **setupIgnores** (def, line 1593, score: 0.0022)
- **slice** (def, line 3082, score: 0.0022)
- **stylizeNoColor** (def, line 6278, score: 0.0022)
- **stylizeWithColor** (def, line 6266, score: 0.0022)
- **timestamp** (def, line 6625, score: 0.0022)
- **trim** (def, line 4221, score: 0.0022)
- **truncate** (def, line 717, score: 0.0022)
- **unescapeBraces** (def, line 1067, score: 0.0022)
- **win32** (def, line 4321, score: 0.0022)
- **wrapper** (def, line 6691, score: 0.0022)
- **wrappy** (def, line 6679, score: 0.0022)

### scripts/check_coverage_tiers.py

- **FileResult** (def, line 91, score: 0.0022)
- **check_coverage** (def, line 123, score: 0.0022)
- **get_tier** (def, line 101, score: 0.0022)
- **main** (def, line 205, score: 0.0022)
- **print_results** (def, line 157, score: 0.0022)

### scripts/compare-backends.py

- **format_divergence_summary** (def, line 43, score: 0.0022)
- **main** (def, line 93, score: 0.0022)
- **print_divergences** (def, line 66, score: 0.0022)

### scripts/generate_changelog.py

- **ChangelogEntry** (def, line 40, score: 0.0022)
- **Commit** (def, line 27, score: 0.0022)
- **format_changelog_section** (def, line 237, score: 0.0022)
- **format_commit_line** (def, line 132, score: 0.0022)
- **generate_changelog_entry** (def, line 198, score: 0.0022)
- **get_commit_message** (def, line 85, score: 0.0022)
- **get_commits_since_tag** (def, line 66, score: 0.0022)
- **get_previous_tag** (def, line 52, score: 0.0022)
- **main** (def, line 320, score: 0.0022)
- **parse_conventional_commit** (def, line 96, score: 0.0022)
- **prepend_to_changelog** (def, line 286, score: 0.0022)
- **should_skip_commit** (def, line 147, score: 0.0022)

### scripts/migrate-to-hierarchical-ids.py

- **build_old_to_new_task_id** (def, line 326, score: 0.0022)
- **build_plan_slug_to_id** (def, line 272, score: 0.0022)
- **build_spec_slug_to_id** (def, line 213, score: 0.0022)
- **discover_plans** (def, line 170, score: 0.0022)
- **discover_specs** (def, line 125, score: 0.0022)
- **format_epic_id** (def, line 241, score: 0.0022)
- **format_plan_id** (def, line 229, score: 0.0022)
- **format_standalone_id** (def, line 263, score: 0.0022)
- **format_task_id** (def, line 254, score: 0.0022)
- **get_epic_char** (def, line 42, score: 0.0022)
- **get_plan_char** (def, line 35, score: 0.0022)
- **get_sequence_char** (def, line 49, score: 0.0022)
- **get_sequence_index** (def, line 54, score: 0.0022)
- **get_spec_created_date** (def, line 105, score: 0.0022)
- **initialize_counters** (def, line 634, score: 0.0022)
- **load_tasks** (def, line 191, score: 0.0022)
- **main** (def, line 655, score: 0.0022)
- **parse_yaml_frontmatter** (def, line 65, score: 0.0022)
- **rename_plan_directories** (def, line 596, score: 0.0022)
- **rename_spec_files** (def, line 558, score: 0.0022)
- **save_tasks** (def, line 207, score: 0.0022)
- **sort_key** (def, line 155, score: 0.0022)
- **sort_key** (def, line 182, score: 0.0022)
- **str_representer** (def, line 94, score: 0.0022)
- **task_sort_key** (def, line 403, score: 0.0022)
- **update_plan_files** (def, line 458, score: 0.0022)
- **update_spec_files** (def, line 427, score: 0.0022)
- **update_tasks_file** (def, line 505, score: 0.0022)
- **write_yaml_frontmatter** (def, line 89, score: 0.0022)

### scripts/move_specs_released.py

- **main** (def, line 23, score: 0.0022)

### scripts/update_webpage_changelog.py

- **Release** (def, line 22, score: 0.0022)
- **extract_description** (def, line 91, score: 0.0022)
- **extract_highlights** (def, line 152, score: 0.0022)
- **extract_title** (def, line 71, score: 0.0022)
- **generate_html** (def, line 180, score: 0.0022)
- **main** (def, line 266, score: 0.0022)
- **parse_changelog** (def, line 32, score: 0.0022)
- **update_version_badge** (def, line 243, score: 0.0022)
- **update_webpage** (def, line 205, score: 0.0022)

### src/cub/audit/coverage.py

- **CoverageFile** (def, line 17, score: 0.0022)
- **CoverageReport** (def, line 26, score: 0.0022)
- **UncoveredLine** (def, line 46, score: 0.0022)
- **format_coverage_report** (def, line 240, score: 0.0022)
- **get_uncovered_lines** (def, line 205, score: 0.0022)
- **has_low_coverage** (def, line 40, score: 0.0022)
- **identify_low_coverage** (def, line 186, score: 0.0022)
- **parse_coverage_report** (def, line 116, score: 0.0022)
- **run_coverage** (def, line 53, score: 0.0022)

### src/cub/audit/dead_code.py

- **ASTDefinitionVisitor** (def, line 27, score: 0.0022)
- **ASTReferenceVisitor** (def, line 140, score: 0.0022)
- **BashDefinition** (def, line 339, score: 0.0022)
- **Definition** (def, line 18, score: 0.0022)
- **__init__** (def, line 147, score: 0.0022)
- **__init__** (def, line 38, score: 0.0022)
- **_is_in_function_scope** (def, line 132, score: 0.0022)
- **detect_unused** (def, line 264, score: 0.0022)
- **detect_unused_bash** (def, line 566, score: 0.0022)

... (210 more symbols omitted to fit budget)
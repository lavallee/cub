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

- **cub**: `src/cub` (254 files) (entry: __init__.py)

## Directory Structure

└── cub_sat/
    ├── .beads/
    │   ├── export-state/
    │   │   ├── 1e122c54fe76f139.json
    │   │   └── 7e7081d5443c1bc3.json
    │   ├── .gitignore
    │   ├── .local_version
    │   ├── README.md
    │   ├── bd.sock
    │   ├── beads.db
    │   ├── beads.db-shm
    │   ├── beads.db-wal
    │   ├── branches.yaml
    │   ├── config.yaml
    │   ├── daemon.lock
    │   ├── daemon.log
    │   ├── daemon.pid
    │   ├── interactions.jsonl
    │   ├── issues.jsonl
    │   ├── last-touched
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
    │   │   │   ├── cub-c5i.3.json
    │   │   │   ├── cub-c5i.4.json
    │   │   │   ├── cub-c5i.5.json
    │   │   │   ├── cub-d2v.1.json
    │   │   │   ├── cub-d2v.2.json
... (truncated to fit budget)

## Ranked Symbols

Symbols ranked by importance (PageRank score):


### scripts/check_coverage_tiers.py

- **FileResult** (def, line 91, score: 0.0025)
- **check_coverage** (def, line 123, score: 0.0025)
- **get_tier** (def, line 101, score: 0.0025)
- **main** (def, line 205, score: 0.0025)
- **print_results** (def, line 157, score: 0.0025)

### scripts/compare-backends.py

- **format_divergence_summary** (def, line 43, score: 0.0025)
- **main** (def, line 93, score: 0.0025)
- **print_divergences** (def, line 66, score: 0.0025)

### scripts/generate_changelog.py

- **ChangelogEntry** (def, line 40, score: 0.0025)
- **Commit** (def, line 27, score: 0.0025)
- **format_changelog_section** (def, line 237, score: 0.0025)
- **format_commit_line** (def, line 132, score: 0.0025)
- **generate_changelog_entry** (def, line 198, score: 0.0025)
- **get_commit_message** (def, line 85, score: 0.0025)
- **get_commits_since_tag** (def, line 66, score: 0.0025)
- **get_previous_tag** (def, line 52, score: 0.0025)
- **main** (def, line 320, score: 0.0025)
- **parse_conventional_commit** (def, line 96, score: 0.0025)
- **prepend_to_changelog** (def, line 286, score: 0.0025)
- **should_skip_commit** (def, line 147, score: 0.0025)

### scripts/move_specs_released.py

- **main** (def, line 23, score: 0.0025)

### scripts/update_webpage_changelog.py

- **Release** (def, line 22, score: 0.0025)
- **extract_description** (def, line 91, score: 0.0025)
- **extract_highlights** (def, line 152, score: 0.0025)
- **extract_title** (def, line 71, score: 0.0025)
- **generate_html** (def, line 180, score: 0.0025)
- **main** (def, line 266, score: 0.0025)
- **parse_changelog** (def, line 32, score: 0.0025)
- **update_version_badge** (def, line 243, score: 0.0025)
- **update_webpage** (def, line 205, score: 0.0025)

### src/cub/audit/coverage.py

- **CoverageFile** (def, line 17, score: 0.0025)
- **CoverageReport** (def, line 26, score: 0.0025)
- **UncoveredLine** (def, line 46, score: 0.0025)
- **format_coverage_report** (def, line 240, score: 0.0025)
- **get_uncovered_lines** (def, line 205, score: 0.0025)
- **has_low_coverage** (def, line 40, score: 0.0025)
- **identify_low_coverage** (def, line 186, score: 0.0025)
- **parse_coverage_report** (def, line 116, score: 0.0025)
- **run_coverage** (def, line 53, score: 0.0025)

### src/cub/audit/dead_code.py

- **ASTDefinitionVisitor** (def, line 27, score: 0.0025)
- **ASTReferenceVisitor** (def, line 140, score: 0.0025)
- **BashDefinition** (def, line 339, score: 0.0025)
- **Definition** (def, line 18, score: 0.0025)
- **__init__** (def, line 147, score: 0.0025)
- **__init__** (def, line 38, score: 0.0025)
- **_is_in_function_scope** (def, line 132, score: 0.0025)
- **detect_unused** (def, line 264, score: 0.0025)
- **detect_unused_bash** (def, line 566, score: 0.0025)
- **find_bash_calls** (def, line 402, score: 0.0025)
- **find_bash_functions** (def, line 347, score: 0.0025)
- **find_python_definitions** (def, line 164, score: 0.0025)
- **find_python_references** (def, line 186, score: 0.0025)
- **get_module_exports** (def, line 208, score: 0.0025)
- **run_shellcheck** (def, line 540, score: 0.0025)
- **should_exclude_definition** (def, line 236, score: 0.0025)
- **visit_Assign** (def, line 115, score: 0.0025)
- **visit_AsyncFunctionDef** (def, line 87, score: 0.0025)
- **visit_Attribute** (def, line 156, score: 0.0025)
- **visit_ClassDef** (def, line 100, score: 0.0025)
- **visit_FunctionDef** (def, line 74, score: 0.0025)
- **visit_Import** (def, line 43, score: 0.0025)
- **visit_ImportFrom** (def, line 57, score: 0.0025)
- **visit_Name** (def, line 150, score: 0.0025)

### src/cub/audit/docs.py

- **CodeBlock** (def, line 31, score: 0.0025)
- **Link** (def, line 23, score: 0.0025)
- **check_links** (def, line 139, score: 0.0025)
- **extract_code_blocks** (def, line 87, score: 0.0025)
- **extract_links** (def, line 40, score: 0.0025)
- **validate_code** (def, line 284, score: 0.0025)
- **validate_docs** (def, line 370, score: 0.0025)

### src/cub/audit/models.py

- **AuditReport** (def, line 120, score: 0.0025)
- **CategoryScore** (def, line 112, score: 0.0025)
- **CodeBlockFinding** (def, line 73, score: 0.0025)
- **DeadCodeFinding** (def, line 17, score: 0.0025)
- **DeadCodeReport** (def, line 34, score: 0.0025)
- **DocsReport** (def, line 85, score: 0.0025)
- **LinkFinding** (def, line 59, score: 0.0025)
- **findings_by_kind** (def, line 51, score: 0.0025)
- **has_failures** (def, line 161, score: 0.0025)
- **has_findings** (def, line 46, score: 0.0025)
- **has_findings** (def, line 99, score: 0.0025)
- **total_issues** (def, line 151, score: 0.0025)
- **total_issues** (def, line 104, score: 0.0025)

### src/cub/cli/__init__.py

- **cli_main** (def, line 285, score: 0.0025)
- **main** (def, line 79, score: 0.0025)
- **version** (def, line 259, score: 0.0025)

### src/cub/cli/argv.py

- **_hoist_global_flags** (def, line 51, score: 0.0025)
- **_rewrite_help** (def, line 36, score: 0.0025)
- **preprocess_argv** (def, line 13, score: 0.0025)

### src/cub/cli/audit.py

- **calculate_grade** (def, line 54, score: 0.0025)
- **calculate_overall_grade** (def, line 142, score: 0.0025)
- **format_detailed_findings** (def, line 270, score: 0.0025)
- **format_summary_report** (def, line 189, score: 0.0025)
- **get_grade_color** (def, line 213, score: 0.0025)
- **grade_coverage** (def, line 119, score: 0.0025)
- **grade_dead_code** (def, line 70, score: 0.0025)
- **grade_documentation** (def, line 94, score: 0.0025)
- **run** (def, line 331, score: 0.0025)

### src/cub/cli/capture.py

- **capture** (def, line 23, score: 0.0025)

### src/cub/cli/captures.py

- **_display_capture_table** (def, line 251, score: 0.0025)
- **_find_capture** (def, line 297, score: 0.0025)
- **_format_date** (def, line 564, score: 0.0025)
- **_parse_since** (def, line 527, score: 0.0025)
- **archive** (def, line 482, score: 0.0025)
- **edit** (def, line 376, score: 0.0025)
- **filter_captures** (def, line 123, score: 0.0025)
- **import_capture** (def, line 416, score: 0.0025)
- **list_captures** (def, line 30, score: 0.0025)
- **show** (def, line 329, score: 0.0025)

### src/cub/cli/dashboard.py

- **_get_examples_dir** (def, line 424, score: 0.0025)
- **_get_project_paths** (def, line 31, score: 0.0025)
- **dashboard** (def, line 57, score: 0.0025)
- **export** (def, line 318, score: 0.0025)
- **init** (def, line 532, score: 0.0025)
- **open_browser** (def, line 172, score: 0.0025)
- **sync** (def, line 204, score: 0.0025)
- **views** (def, line 433, score: 0.0025)

### src/cub/cli/default.py

- **_get_welcome_message** (def, line 146, score: 0.0025)
- **_handle_no_project** (def, line 250, score: 0.0025)
- **_render_full_welcome** (def, line 81, score: 0.0025)
- **_render_inline_status** (def, line 43, score: 0.0025)
- **default_command** (def, line 172, score: 0.0025)
- **render_welcome** (def, line 29, score: 0.0025)

### src/cub/cli/delegated/__init__.py

- **_delegate** (def, line 16, score: 0.0025)
- **architect** (def, line 56, score: 0.0025)
- **artifacts** (def, line 164, score: 0.0025)
- **bootstrap** (def, line 116, score: 0.0025)
- **branch** (def, line 198, score: 0.0025)
- **branches** (def, line 214, score: 0.0025)
- **checkpoints** (def, line 231, score: 0.0025)
- **close_task** (def, line 322, score: 0.0025)
- **explain_task** (def, line 149, score: 0.0025)
- **guardrails** (def, line 282, score: 0.0025)
- **import_cmd** (def, line 266, score: 0.0025)
- **interview** (def, line 250, score: 0.0025)
- **plan** (def, line 71, score: 0.0025)
- **prep** (def, line 36, score: 0.0025)
- **sessions** (def, line 131, score: 0.0025)
- **spec** (def, line 101, score: 0.0025)
- **stage** (def, line 85, score: 0.0025)
- **triage** (def, line 41, score: 0.0025)
- **update** (def, line 298, score: 0.0025)
- **validate** (def, line 179, score: 0.0025)
- **verify_task** (def, line 337, score: 0.0025)

### src/cub/cli/delegated/runner.py

- **BashCubNotFoundError** (def, line 24, score: 0.0025)
- **delegate_to_bash** (def, line 117, score: 0.0025)
- **find_bash_cub** (def, line 30, score: 0.0025)
- **is_bash_command** (def, line 79, score: 0.0025)

### src/cub/cli/docs.py

- **docs** (def, line 16, score: 0.0025)

### src/cub/cli/doctor.py

- **_check_command** (def, line 175, score: 0.0025)
- **_get_command_version** (def, line 189, score: 0.0025)
- **check_environment** (def, line 125, score: 0.0025)
- **check_hooks** (def, line 211, score: 0.0025)
- **check_stale_epics** (def, line 28, score: 0.0025)
- **doctor** (def, line 352, score: 0.0025)

### src/cub/cli/errors.py

- **ExitCode** (def, line 15, score: 0.0025)
- **print_backend_not_initialized_error** (def, line 144, score: 0.0025)
- **print_dirty_working_tree_error** (def, line 153, score: 0.0025)
- **print_error** (def, line 31, score: 0.0025)
- **print_harness_not_found_error** (def, line 67, score: 0.0025)
- **print_harness_not_installed_error** (def, line 77, score: 0.0025)
- **print_incompatible_flags_error** (def, line 162, score: 0.0025)
- **print_invalid_option_error** (def, line 194, score: 0.0025)
- **print_main_branch_error** (def, line 184, score: 0.0025)
- **print_missing_dependency_error** (def, line 172, score: 0.0025)
- **print_no_tasks_found_error** (def, line 113, score: 0.0025)
- **print_not_git_repo_error** (def, line 95, score: 0.0025)
- **print_not_project_root_error** (def, line 104, score: 0.0025)
- **print_sync_not_initialized_error** (def, line 135, score: 0.0025)
- **print_task_not_found_error** (def, line 126, score: 0.0025)

### src/cub/cli/hooks.py

- **check** (def, line 136, score: 0.0025)
- **install** (def, line 26, score: 0.0025)
- **uninstall** (def, line 101, score: 0.0025)

### src/cub/cli/init_cmd.py

- **_detect_dev_mode** (def, line 83, score: 0.0025)
- **_ensure_cub_json** (def, line 331, score: 0.0025)
- **_ensure_dev_mode_config** (def, line 107, score: 0.0025)
- **_ensure_prompt_md** (def, line 261, score: 0.0025)
- **_ensure_runloop** (def, line 152, score: 0.0025)
- **_ensure_specs_dir** (def, line 325, score: 0.0025)
- **_get_templates_dir** (def, line 136, score: 0.0025)
- **_init_backend** (def, line 232, score: 0.0025)
- **_init_global** (def, line 348, score: 0.0025)
- **_install_claude_commands** (def, line 290, score: 0.0025)
- **_load_project_config** (def, line 52, score: 0.0025)
- **_save_project_config** (def, line 65, score: 0.0025)
- **_update_gitignore** (def, line 310, score: 0.0025)
- **detect_backend** (def, line 213, score: 0.0025)
- **detect_project_type** (def, line 172, score: 0.0025)
- **generate_instruction_files** (def, line 390, score: 0.0025)
- **init_project** (def, line 517, score: 0.0025)
- **main** (def, line 609, score: 0.0025)

### src/cub/cli/investigate.py

- **CaptureCategory** (def, line 28, score: 0.0025)
- **_ensure_investigations_dir** (def, line 196, score: 0.0025)

... (216 more symbols omitted to fit budget)
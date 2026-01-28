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

- **cub**: `src/cub` (224 files) (entry: __init__.py)

## Directory Structure

└── cub/
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
    │   │   ├── cub:architect.md
    │   │   ├── cub:capture.md
    │   │   ├── cub:itemize.md
    │   │   ├── cub:orient.md
    │   │   ├── cub:plan.md
    │   │   ├── cub:spec-to-issues.md
    │   │   ├── cub:spec.md
    │   │   └── cub:triage.md
    │   └── settings.json
    ├── .cub/
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
    │   │   │   ├── cub-c5i/
    │   │   │   ├── cub-d8b/
    │   │   │   ├── cub-j1a/
    │   │   │   ├── cub-j1b/
    │   │   │   ├── cub-j1c/
    │   │   │   ├── cub-j1d/
    │   │   │   ├── cub-j1e/
    │   │   │   ├── cub-j1f/
    │   │   │   ├── cub-m3k/
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
    │   │   │   ├── cub-p9q.1/
    │   │   │   ├── cub-p9q.3/
    │   │   │   ├── cub-p9q.4/
    │   │   │   ├── cub-p9q.5/
    │   │   │   ├── cub-q2j.1/
    │   │   │   ├── cub-q2j.2/
    │   │   │   ├── cub-q2j.3/
    │   │   │   ├── cub-q2j.4/
    │   │   │   ├── cub-q2j.5/
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
    │   │   │   ├── cub-a7f.1.json
    │   │   │   ├── cub-a7f.2.json
    │   │   │   ├── cub-a7f.3.json
    │   │   │   ├── cub-a7f.4.json
    │   │   │   ├── cub-a7f.5.json
    │   │   │   ├── cub-aeim.json
    │   │   │   ├── cub-c5i.1.json
    │   │   │   ├── cub-c5i.2.json
    │   │   │   ├── cub-c5i.3.json
    │   │   │   ├── cub-c5i.4.json
    │   │   │   ├── cub-c5i.5.json
    │   │   │   ├── cub-d2v.1.json
    │   │   │   ├── cub-d2v.2.json
    │   │   │   ├── cub-d2v.3.json
    │   │   │   ├── cub-d2v.4.json
    │   │   │   ├── cub-d2v.5.json
    │   │   │   ├── cub-d2v.6.json
    │   │   │   ├── cub-d8b.1.json
    │   │   │   ├── cub-d8b.2.json
    │   │   │   ├── cub-d8b.3.json
    │   │   │   ├── cub-dmxf.json
    │   │   │   ├── cub-e2p.1.json
    │   │   │   ├── cub-e2p.2.json
    │   │   │   ├── cub-e2p.3.json
    │   │   │   ├── cub-f7m.1.json
    │   │   │   ├── cub-f7m.2.json
    │   │   │   ├── cub-f7m.3.json
    │   │   │   ├── cub-f7m.4.json
    │   │   │   ├── cub-fail.json
    │   │   │   ├── cub-hj6j.json
    │   │   │   ├── cub-j1a.1.json
    │   │   │   ├── cub-j1a.2.json
    │   │   │   ├── cub-j1a.3.json
    │   │   │   ├── cub-j1a.4.json
    │   │   │   ├── cub-j1a.5.json
    │   │   │   ├── cub-j1b.1.json
    │   │   │   ├── cub-j1b.2.json
    │   │   │   ├── cub-j1b.3.json
    │   │   │   ├── cub-j1b.4.json
    │   │   │   ├── cub-j1c.1.json
    │   │   │   ├── cub-j1c.2.json
    │   │   │   ├── cub-j1c.3.json
    │   │   │   ├── cub-j1c.4.json
    │   │   │   ├── cub-j1c.5.json
    │   │   │   ├── cub-j1d.1.json
    │   │   │   ├── cub-j1d.2.json
    │   │   │   ├── cub-j1e.1.json
    │   │   │   ├── cub-j1e.2.json
    │   │   │   ├── cub-j1e.3.json
    │   │   │   ├── cub-j1f.1.json
    │   │   │   ├── cub-j1f.2.json
    │   │   │   ├── cub-j1f.3.json
    │   │   │   ├── cub-k3p.1.json
    │   │   │   ├── cub-k3p.2.json
    │   │   │   ├── cub-k3p.3.json
    │   │   │   ├── cub-k3p.4.json
    │   │   │   ├── cub-k3p.5.json
    │   │   │   ├── cub-k3p.6.json
    │   │   │   ├── cub-k8d.1.json
    │   │   │   ├── cub-k8d.2.json
    │   │   │   ├── cub-k8d.3.json
    │   │   │   ├── cub-k8d.4.json
    │   │   │   ├── cub-k8d.5.json
    │   │   │   ├── cub-k8d.6.json
    │   │   │   ├── cub-k8d.7.json
    │   │   │   ├── cub-k8d.8.json
    │   │   │   ├── cub-l7e.1.json
    │   │   │   ├── cub-l7e.2.json
    │   │   │   ├── cub-l7e.3.json
    │   │   │   ├── cub-l7e.4.json
    │   │   │   ├── cub-l7e.5.json
    │   │   │   ├── cub-m3k.1.json
    │   │   │   ├── cub-m3k.2.json
    │   │   │   ├── cub-m3k.3.json
    │   │   │   ├── cub-m3k.4.json
    │   │   │   ├── cub-m3k.5.json
    │   │   │   ├── cub-m3k.6.json
    │   │   │   ├── cub-m3k.7.json
    │   │   │   ├── cub-m3x.1.json
    │   │   │   ├── cub-m3x.2.json
    │   │   │   ├── cub-m3x.3.json
    │   │   │   ├── cub-m3x.4.json
    │   │   │   ├── cub-m3x.5.json
    │   │   │   ├── cub-m3x.6.json
    │   │   │   ├── cub-p71l.json
    │   │   │   ├── cub-p9q.1.json
    │   │   │   ├── cub-p9q.3.json
    │   │   │   ├── cub-p9q.4.json
    │   │   │   ├── cub-p9q.5.json
    │   │   │   ├── cub-p9w.1.json
    │   │   │   ├── cub-p9w.2.json
    │   │   │   ├── cub-p9w.4.json
    │   │   │   ├── cub-p9w.5.json
    │   │   │   ├── cub-p9w.6.json
    │   │   │   ├── cub-q2j.1.json
    │   │   │   ├── cub-q2j.2.json
    │   │   │   ├── cub-q2j.3.json
    │   │   │   ├── cub-q2j.4.json
    │   │   │   ├── cub-q2j.5.json
    │   │   │   ├── cub-q2w.1.json
    │   │   │   ├── cub-q2w.2.json
    │   │   │   ├── cub-q2w.3.json
    │   │   │   ├── cub-q2w.4.json
... (truncated to fit budget)

## Ranked Symbols

Symbols ranked by importance (PageRank score):


### scripts/check_coverage_tiers.py

- **FileResult** (def, line 91, score: 0.0029)
- **check_coverage** (def, line 123, score: 0.0029)
- **get_tier** (def, line 101, score: 0.0029)
- **main** (def, line 205, score: 0.0029)
- **print_results** (def, line 157, score: 0.0029)

### scripts/compare-backends.py

- **format_divergence_summary** (def, line 43, score: 0.0029)
- **main** (def, line 93, score: 0.0029)
- **print_divergences** (def, line 66, score: 0.0029)

### scripts/generate_changelog.py

- **ChangelogEntry** (def, line 40, score: 0.0029)
- **Commit** (def, line 27, score: 0.0029)
- **format_changelog_section** (def, line 237, score: 0.0029)
- **format_commit_line** (def, line 132, score: 0.0029)
- **generate_changelog_entry** (def, line 198, score: 0.0029)
- **get_commit_message** (def, line 85, score: 0.0029)
- **get_commits_since_tag** (def, line 66, score: 0.0029)
- **get_previous_tag** (def, line 52, score: 0.0029)
- **main** (def, line 320, score: 0.0029)
- **parse_conventional_commit** (def, line 96, score: 0.0029)
- **prepend_to_changelog** (def, line 286, score: 0.0029)
- **should_skip_commit** (def, line 147, score: 0.0029)

### scripts/move_specs_released.py

- **main** (def, line 23, score: 0.0029)

### scripts/update_webpage_changelog.py

- **Release** (def, line 22, score: 0.0029)
- **extract_description** (def, line 91, score: 0.0029)
- **extract_highlights** (def, line 152, score: 0.0029)
- **extract_title** (def, line 71, score: 0.0029)
- **generate_html** (def, line 180, score: 0.0029)
- **main** (def, line 266, score: 0.0029)
- **parse_changelog** (def, line 32, score: 0.0029)
- **update_version_badge** (def, line 243, score: 0.0029)
- **update_webpage** (def, line 205, score: 0.0029)

### src/cub/audit/coverage.py

- **CoverageFile** (def, line 17, score: 0.0029)
- **CoverageReport** (def, line 26, score: 0.0029)
- **UncoveredLine** (def, line 46, score: 0.0029)
- **format_coverage_report** (def, line 240, score: 0.0029)
- **get_uncovered_lines** (def, line 205, score: 0.0029)
- **has_low_coverage** (def, line 40, score: 0.0029)
- **identify_low_coverage** (def, line 186, score: 0.0029)
- **parse_coverage_report** (def, line 116, score: 0.0029)
- **run_coverage** (def, line 53, score: 0.0029)

### src/cub/audit/dead_code.py

- **ASTDefinitionVisitor** (def, line 27, score: 0.0029)
- **ASTReferenceVisitor** (def, line 140, score: 0.0029)
- **BashDefinition** (def, line 339, score: 0.0029)
- **Definition** (def, line 18, score: 0.0029)
- **__init__** (def, line 147, score: 0.0029)
- **__init__** (def, line 38, score: 0.0029)
- **_is_in_function_scope** (def, line 132, score: 0.0029)
- **detect_unused** (def, line 264, score: 0.0029)
- **detect_unused_bash** (def, line 566, score: 0.0029)
- **find_bash_calls** (def, line 402, score: 0.0029)
- **find_bash_functions** (def, line 347, score: 0.0029)
- **find_python_definitions** (def, line 164, score: 0.0029)
- **find_python_references** (def, line 186, score: 0.0029)
- **get_module_exports** (def, line 208, score: 0.0029)
- **run_shellcheck** (def, line 540, score: 0.0029)
- **should_exclude_definition** (def, line 236, score: 0.0029)
- **visit_Assign** (def, line 115, score: 0.0029)
- **visit_AsyncFunctionDef** (def, line 87, score: 0.0029)
- **visit_Attribute** (def, line 156, score: 0.0029)
- **visit_ClassDef** (def, line 100, score: 0.0029)
- **visit_FunctionDef** (def, line 74, score: 0.0029)
- **visit_Import** (def, line 43, score: 0.0029)
- **visit_ImportFrom** (def, line 57, score: 0.0029)
- **visit_Name** (def, line 150, score: 0.0029)

### src/cub/audit/docs.py

- **CodeBlock** (def, line 31, score: 0.0029)
- **Link** (def, line 23, score: 0.0029)
- **check_links** (def, line 139, score: 0.0029)
- **extract_code_blocks** (def, line 87, score: 0.0029)
- **extract_links** (def, line 40, score: 0.0029)
- **validate_code** (def, line 284, score: 0.0029)
- **validate_docs** (def, line 370, score: 0.0029)

### src/cub/audit/models.py

- **AuditReport** (def, line 120, score: 0.0029)
- **CategoryScore** (def, line 112, score: 0.0029)
- **CodeBlockFinding** (def, line 73, score: 0.0029)
- **DeadCodeFinding** (def, line 17, score: 0.0029)
- **DeadCodeReport** (def, line 34, score: 0.0029)
- **DocsReport** (def, line 85, score: 0.0029)
- **LinkFinding** (def, line 59, score: 0.0029)
- **findings_by_kind** (def, line 51, score: 0.0029)
- **has_failures** (def, line 161, score: 0.0029)
- **has_findings** (def, line 99, score: 0.0029)
- **has_findings** (def, line 46, score: 0.0029)
- **total_issues** (def, line 104, score: 0.0029)
- **total_issues** (def, line 151, score: 0.0029)

### src/cub/cli/__init__.py

- **cli_main** (def, line 250, score: 0.0029)
- **main** (def, line 77, score: 0.0029)
- **version** (def, line 224, score: 0.0029)

### src/cub/cli/argv.py

- **_hoist_global_flags** (def, line 51, score: 0.0029)
- **_rewrite_help** (def, line 36, score: 0.0029)
- **preprocess_argv** (def, line 13, score: 0.0029)

### src/cub/cli/audit.py

- **calculate_grade** (def, line 54, score: 0.0029)
- **calculate_overall_grade** (def, line 142, score: 0.0029)
- **format_detailed_findings** (def, line 270, score: 0.0029)
- **format_summary_report** (def, line 189, score: 0.0029)
- **get_grade_color** (def, line 213, score: 0.0029)
- **grade_coverage** (def, line 119, score: 0.0029)
- **grade_dead_code** (def, line 70, score: 0.0029)
- **grade_documentation** (def, line 94, score: 0.0029)
- **run** (def, line 331, score: 0.0029)

### src/cub/cli/capture.py

- **capture** (def, line 23, score: 0.0029)

### src/cub/cli/captures.py

- **_display_capture_table** (def, line 251, score: 0.0029)
- **_find_capture** (def, line 297, score: 0.0029)
- **_format_date** (def, line 564, score: 0.0029)
- **_parse_since** (def, line 527, score: 0.0029)
- **archive** (def, line 482, score: 0.0029)
- **edit** (def, line 376, score: 0.0029)
- **filter_captures** (def, line 123, score: 0.0029)
- **import_capture** (def, line 416, score: 0.0029)
- **list_captures** (def, line 30, score: 0.0029)
- **show** (def, line 329, score: 0.0029)

### src/cub/cli/dashboard.py

- **_get_examples_dir** (def, line 424, score: 0.0029)
- **_get_project_paths** (def, line 31, score: 0.0029)
- **dashboard** (def, line 57, score: 0.0029)
- **export** (def, line 318, score: 0.0029)
- **init** (def, line 532, score: 0.0029)
- **open_browser** (def, line 172, score: 0.0029)
- **sync** (def, line 204, score: 0.0029)
- **views** (def, line 433, score: 0.0029)

### src/cub/cli/delegated.py

- **_delegate** (def, line 16, score: 0.0029)
- **architect** (def, line 56, score: 0.0029)
- **artifacts** (def, line 164, score: 0.0029)
- **bootstrap** (def, line 116, score: 0.0029)
- **branch** (def, line 198, score: 0.0029)
- **branches** (def, line 214, score: 0.0029)
- **checkpoints** (def, line 231, score: 0.0029)
- **close_task** (def, line 322, score: 0.0029)
- **explain_task** (def, line 149, score: 0.0029)
- **guardrails** (def, line 282, score: 0.0029)
- **import_cmd** (def, line 266, score: 0.0029)
- **interview** (def, line 250, score: 0.0029)
- **plan** (def, line 71, score: 0.0029)
- **prep** (def, line 36, score: 0.0029)
- **sessions** (def, line 131, score: 0.0029)
- **spec** (def, line 101, score: 0.0029)
- **stage** (def, line 85, score: 0.0029)
- **triage** (def, line 41, score: 0.0029)
- **update** (def, line 298, score: 0.0029)
- **validate** (def, line 179, score: 0.0029)
- **verify_task** (def, line 337, score: 0.0029)

### src/cub/cli/docs.py

- **docs** (def, line 16, score: 0.0029)

### src/cub/cli/doctor.py

- **_check_command** (def, line 175, score: 0.0029)
- **_get_command_version** (def, line 189, score: 0.0029)
- **check_environment** (def, line 125, score: 0.0029)
- **check_hooks** (def, line 211, score: 0.0029)
- **check_stale_epics** (def, line 28, score: 0.0029)
- **doctor** (def, line 352, score: 0.0029)

### src/cub/cli/errors.py

- **ExitCode** (def, line 15, score: 0.0029)
- **print_backend_not_initialized_error** (def, line 144, score: 0.0029)
- **print_dirty_working_tree_error** (def, line 153, score: 0.0029)
- **print_error** (def, line 31, score: 0.0029)
- **print_harness_not_found_error** (def, line 67, score: 0.0029)
- **print_harness_not_installed_error** (def, line 77, score: 0.0029)
- **print_incompatible_flags_error** (def, line 162, score: 0.0029)
- **print_invalid_option_error** (def, line 194, score: 0.0029)
- **print_main_branch_error** (def, line 184, score: 0.0029)
- **print_missing_dependency_error** (def, line 172, score: 0.0029)
- **print_no_tasks_found_error** (def, line 113, score: 0.0029)
- **print_not_git_repo_error** (def, line 95, score: 0.0029)
- **print_not_project_root_error** (def, line 104, score: 0.0029)
- **print_sync_not_initialized_error** (def, line 135, score: 0.0029)
- **print_task_not_found_error** (def, line 126, score: 0.0029)

### src/cub/cli/hooks.py

- **check** (def, line 136, score: 0.0029)
- **install** (def, line 26, score: 0.0029)
- **uninstall** (def, line 101, score: 0.0029)

### src/cub/cli/init_cmd.py

- **_detect_dev_mode** (def, line 83, score: 0.0029)
- **_ensure_cub_json** (def, line 331, score: 0.0029)
- **_ensure_dev_mode_config** (def, line 107, score: 0.0029)
- **_ensure_prompt_md** (def, line 261, score: 0.0029)
- **_ensure_runloop** (def, line 152, score: 0.0029)
- **_ensure_specs_dir** (def, line 325, score: 0.0029)
- **_get_templates_dir** (def, line 136, score: 0.0029)
- **_init_backend** (def, line 232, score: 0.0029)
- **_init_global** (def, line 348, score: 0.0029)
- **_install_claude_commands** (def, line 290, score: 0.0029)
- **_load_project_config** (def, line 52, score: 0.0029)
- **_save_project_config** (def, line 65, score: 0.0029)
- **_update_gitignore** (def, line 310, score: 0.0029)
- **detect_backend** (def, line 213, score: 0.0029)
- **detect_project_type** (def, line 172, score: 0.0029)
- **generate_instruction_files** (def, line 390, score: 0.0029)
- **init_project** (def, line 517, score: 0.0029)
- **main** (def, line 609, score: 0.0029)

### src/cub/cli/investigate.py

- **CaptureCategory** (def, line 28, score: 0.0029)
- **_ensure_investigations_dir** (def, line 196, score: 0.0029)
- **_extract_body_content** (def, line 202, score: 0.0029)
- **categorize_capture** (def, line 39, score: 0.0029)
- **investigate** (def, line 710, score: 0.0029)
- **process_audit** (def, line 246, score: 0.0029)
- **process_design** (def, line 478, score: 0.0029)
- **process_quick_fix** (def, line 212, score: 0.0029)
- **process_research** (def, line 389, score: 0.0029)
- **process_spike** (def, line 595, score: 0.0029)
- **process_unclear** (def, line 632, score: 0.0029)

### src/cub/cli/ledger.py

- **_export_csv** (def, line 873, score: 0.0029)
- **_export_json** (def, line 860, score: 0.0029)

... (215 more symbols omitted to fit budget)
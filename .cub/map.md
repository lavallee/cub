# Project Map: cub

**Project Directory:** `/home/marc/Projects/cub`

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

- **cub**: `src/cub` (268 files) (entry: __init__.py)

## Directory Structure

└── cub/
    ├── .beads/
    │   ├── .gitignore
    │   ├── README.md
    │   ├── branches.yaml
    │   ├── config.yaml
    │   ├── interactions.jsonl
    │   ├── issues.jsonl
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
    │   │       ├── 68/
    │   │       ├── 69/
    │   │       ├── a1/
    │   │       ├── fd/
    │   │       └── cache.db
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
    │   │   ├── by-task/
    │   │   │   ├── cub-001/
    │   │   │   ├── cub-048a-0.1/
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
    │   │   │   ├── cub-t44.1/
    │   │   │   ├── cub-t44.10/
    │   │   │   ├── cub-t44.11/
    │   │   │   ├── cub-t44.12/
    │   │   │   ├── cub-t44.2/
    │   │   │   ├── cub-t44.3/
    │   │   │   ├── cub-t44.4/
    │   │   │   ├── cub-t44.5/
    │   │   │   ├── cub-t44.6/
    │   │   │   ├── cub-t44.7/
    │   │   │   ├── cub-t44.8/
    │   │   │   ├── cub-t44.9/
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
    │   │   │   ├── cub-048a-0.1.json
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
... (truncated to fit budget)

## Ranked Symbols

Symbols ranked by importance (PageRank score):


### scripts/check_coverage_tiers.py

- **FileResult** (def, line 91, score: 0.0024)
- **check_coverage** (def, line 123, score: 0.0024)
- **get_tier** (def, line 101, score: 0.0024)
- **main** (def, line 205, score: 0.0024)
- **print_results** (def, line 157, score: 0.0024)

### scripts/compare-backends.py

- **format_divergence_summary** (def, line 43, score: 0.0024)
- **main** (def, line 93, score: 0.0024)
- **print_divergences** (def, line 66, score: 0.0024)

### scripts/generate_changelog.py

- **ChangelogEntry** (def, line 40, score: 0.0024)
- **Commit** (def, line 27, score: 0.0024)
- **format_changelog_section** (def, line 237, score: 0.0024)
- **format_commit_line** (def, line 132, score: 0.0024)
- **generate_changelog_entry** (def, line 198, score: 0.0024)
- **get_commit_message** (def, line 85, score: 0.0024)
- **get_commits_since_tag** (def, line 66, score: 0.0024)
- **get_previous_tag** (def, line 52, score: 0.0024)
- **main** (def, line 320, score: 0.0024)
- **parse_conventional_commit** (def, line 96, score: 0.0024)
- **prepend_to_changelog** (def, line 286, score: 0.0024)
- **should_skip_commit** (def, line 147, score: 0.0024)

### scripts/migrate-to-hierarchical-ids.py

- **build_old_to_new_task_id** (def, line 326, score: 0.0024)
- **build_plan_slug_to_id** (def, line 272, score: 0.0024)
- **build_spec_slug_to_id** (def, line 213, score: 0.0024)
- **discover_plans** (def, line 170, score: 0.0024)
- **discover_specs** (def, line 125, score: 0.0024)
- **format_epic_id** (def, line 241, score: 0.0024)
- **format_plan_id** (def, line 229, score: 0.0024)
- **format_standalone_id** (def, line 263, score: 0.0024)
- **format_task_id** (def, line 254, score: 0.0024)
- **get_epic_char** (def, line 42, score: 0.0024)
- **get_plan_char** (def, line 35, score: 0.0024)
- **get_sequence_char** (def, line 49, score: 0.0024)
- **get_sequence_index** (def, line 54, score: 0.0024)
- **get_spec_created_date** (def, line 105, score: 0.0024)
- **initialize_counters** (def, line 634, score: 0.0024)
- **load_tasks** (def, line 191, score: 0.0024)
- **main** (def, line 655, score: 0.0024)
- **parse_yaml_frontmatter** (def, line 65, score: 0.0024)
- **rename_plan_directories** (def, line 596, score: 0.0024)
- **rename_spec_files** (def, line 558, score: 0.0024)
- **save_tasks** (def, line 207, score: 0.0024)
- **sort_key** (def, line 155, score: 0.0024)
- **sort_key** (def, line 182, score: 0.0024)
- **str_representer** (def, line 94, score: 0.0024)
- **task_sort_key** (def, line 403, score: 0.0024)
- **update_plan_files** (def, line 458, score: 0.0024)
- **update_spec_files** (def, line 427, score: 0.0024)
- **update_tasks_file** (def, line 505, score: 0.0024)
- **write_yaml_frontmatter** (def, line 89, score: 0.0024)

### scripts/move_specs_released.py

- **main** (def, line 23, score: 0.0024)

### scripts/update_webpage_changelog.py

- **Release** (def, line 22, score: 0.0024)
- **extract_description** (def, line 91, score: 0.0024)
- **extract_highlights** (def, line 152, score: 0.0024)
- **extract_title** (def, line 71, score: 0.0024)
- **generate_html** (def, line 180, score: 0.0024)
- **main** (def, line 266, score: 0.0024)
- **parse_changelog** (def, line 32, score: 0.0024)
- **update_version_badge** (def, line 243, score: 0.0024)
- **update_webpage** (def, line 205, score: 0.0024)

### src/cub/audit/coverage.py

- **CoverageFile** (def, line 17, score: 0.0024)
- **CoverageReport** (def, line 26, score: 0.0024)
- **UncoveredLine** (def, line 46, score: 0.0024)
- **format_coverage_report** (def, line 240, score: 0.0024)
- **get_uncovered_lines** (def, line 205, score: 0.0024)
- **has_low_coverage** (def, line 40, score: 0.0024)
- **identify_low_coverage** (def, line 186, score: 0.0024)
- **parse_coverage_report** (def, line 116, score: 0.0024)
- **run_coverage** (def, line 53, score: 0.0024)

### src/cub/audit/dead_code.py

- **ASTDefinitionVisitor** (def, line 27, score: 0.0024)
- **ASTReferenceVisitor** (def, line 140, score: 0.0024)
- **BashDefinition** (def, line 339, score: 0.0024)
- **Definition** (def, line 18, score: 0.0024)
- **__init__** (def, line 38, score: 0.0024)
- **__init__** (def, line 147, score: 0.0024)
- **_is_in_function_scope** (def, line 132, score: 0.0024)
- **detect_unused** (def, line 264, score: 0.0024)
- **detect_unused_bash** (def, line 566, score: 0.0024)
- **find_bash_calls** (def, line 402, score: 0.0024)
- **find_bash_functions** (def, line 347, score: 0.0024)
- **find_python_definitions** (def, line 164, score: 0.0024)
- **find_python_references** (def, line 186, score: 0.0024)
- **get_module_exports** (def, line 208, score: 0.0024)
- **run_shellcheck** (def, line 540, score: 0.0024)
- **should_exclude_definition** (def, line 236, score: 0.0024)
- **visit_Assign** (def, line 115, score: 0.0024)
- **visit_AsyncFunctionDef** (def, line 87, score: 0.0024)
- **visit_Attribute** (def, line 156, score: 0.0024)
- **visit_ClassDef** (def, line 100, score: 0.0024)
- **visit_FunctionDef** (def, line 74, score: 0.0024)
- **visit_Import** (def, line 43, score: 0.0024)
- **visit_ImportFrom** (def, line 57, score: 0.0024)
- **visit_Name** (def, line 150, score: 0.0024)

### src/cub/audit/docs.py

- **CodeBlock** (def, line 31, score: 0.0024)
- **Link** (def, line 23, score: 0.0024)
- **check_links** (def, line 139, score: 0.0024)
- **extract_code_blocks** (def, line 87, score: 0.0024)
- **extract_links** (def, line 40, score: 0.0024)
- **validate_code** (def, line 284, score: 0.0024)
- **validate_docs** (def, line 370, score: 0.0024)

### src/cub/audit/models.py

- **AuditReport** (def, line 120, score: 0.0024)
- **CategoryScore** (def, line 112, score: 0.0024)
- **CodeBlockFinding** (def, line 73, score: 0.0024)
- **DeadCodeFinding** (def, line 17, score: 0.0024)
- **DeadCodeReport** (def, line 34, score: 0.0024)
- **DocsReport** (def, line 85, score: 0.0024)
- **LinkFinding** (def, line 59, score: 0.0024)
- **findings_by_kind** (def, line 51, score: 0.0024)
- **has_failures** (def, line 161, score: 0.0024)
- **has_findings** (def, line 46, score: 0.0024)
- **has_findings** (def, line 99, score: 0.0024)
- **total_issues** (def, line 151, score: 0.0024)
- **total_issues** (def, line 104, score: 0.0024)

### src/cub/cli/__init__.py

- **cli_main** (def, line 289, score: 0.0024)
- **main** (def, line 81, score: 0.0024)
- **version** (def, line 263, score: 0.0024)

### src/cub/cli/argv.py

- **_hoist_global_flags** (def, line 51, score: 0.0024)
- **_rewrite_help** (def, line 36, score: 0.0024)
- **preprocess_argv** (def, line 13, score: 0.0024)

### src/cub/cli/audit.py

- **calculate_grade** (def, line 54, score: 0.0024)
- **calculate_overall_grade** (def, line 142, score: 0.0024)
- **format_detailed_findings** (def, line 270, score: 0.0024)
- **format_summary_report** (def, line 189, score: 0.0024)
- **get_grade_color** (def, line 213, score: 0.0024)
- **grade_coverage** (def, line 119, score: 0.0024)
- **grade_dead_code** (def, line 70, score: 0.0024)
- **grade_documentation** (def, line 94, score: 0.0024)
- **run** (def, line 331, score: 0.0024)

### src/cub/cli/build_plan.py

- **_find_build_plan_script** (def, line 19, score: 0.0024)
- **main** (def, line 46, score: 0.0024)

### src/cub/cli/capture.py

- **capture** (def, line 23, score: 0.0024)

### src/cub/cli/captures.py

- **_display_capture_table** (def, line 251, score: 0.0024)
- **_find_capture** (def, line 297, score: 0.0024)
- **_format_date** (def, line 564, score: 0.0024)
- **_parse_since** (def, line 527, score: 0.0024)
- **archive** (def, line 482, score: 0.0024)
- **edit** (def, line 376, score: 0.0024)
- **filter_captures** (def, line 123, score: 0.0024)
- **import_capture** (def, line 416, score: 0.0024)
- **list_captures** (def, line 30, score: 0.0024)
- **show** (def, line 329, score: 0.0024)

### src/cub/cli/dashboard.py

- **_get_examples_dir** (def, line 424, score: 0.0024)
- **_get_project_paths** (def, line 31, score: 0.0024)
- **dashboard** (def, line 57, score: 0.0024)
- **export** (def, line 318, score: 0.0024)
- **init** (def, line 532, score: 0.0024)
- **open_browser** (def, line 172, score: 0.0024)
- **sync** (def, line 204, score: 0.0024)
- **views** (def, line 433, score: 0.0024)

### src/cub/cli/default.py

- **_get_welcome_message** (def, line 146, score: 0.0024)
- **_handle_no_project** (def, line 251, score: 0.0024)
- **_render_full_welcome** (def, line 81, score: 0.0024)
- **_render_inline_status** (def, line 43, score: 0.0024)
- **default_command** (def, line 172, score: 0.0024)
- **render_welcome** (def, line 29, score: 0.0024)

### src/cub/cli/delegated/__init__.py

- **_delegate** (def, line 16, score: 0.0024)
- **architect** (def, line 56, score: 0.0024)
- **artifacts** (def, line 164, score: 0.0024)
- **bootstrap** (def, line 116, score: 0.0024)
- **branch** (def, line 198, score: 0.0024)
- **branches** (def, line 214, score: 0.0024)
- **checkpoints** (def, line 231, score: 0.0024)
- **close_task** (def, line 322, score: 0.0024)
- **explain_task** (def, line 149, score: 0.0024)
- **guardrails** (def, line 282, score: 0.0024)
- **import_cmd** (def, line 266, score: 0.0024)
- **interview** (def, line 250, score: 0.0024)
- **plan** (def, line 71, score: 0.0024)
- **prep** (def, line 36, score: 0.0024)
- **sessions** (def, line 131, score: 0.0024)
- **spec** (def, line 101, score: 0.0024)
- **stage** (def, line 85, score: 0.0024)
- **triage** (def, line 41, score: 0.0024)
- **update** (def, line 298, score: 0.0024)
- **validate** (def, line 179, score: 0.0024)
- **verify_task** (def, line 337, score: 0.0024)

### src/cub/cli/delegated/runner.py

- **BashCubNotFoundError** (def, line 24, score: 0.0024)
- **delegate_to_bash** (def, line 117, score: 0.0024)
- **find_bash_cub** (def, line 30, score: 0.0024)
- **is_bash_command** (def, line 79, score: 0.0024)

### src/cub/cli/docs.py

- **docs** (def, line 16, score: 0.0024)

### src/cub/cli/doctor.py

- **DiagnosticResult** (def, line 30, score: 0.0024)
- **_check_command** (def, line 41, score: 0.0024)
- **_get_command_version** (def, line 55, score: 0.0024)
- **check_environment** (def, line 680, score: 0.0024)
- **check_hooks** (def, line 730, score: 0.0024)
- **check_stale_epics** (def, line 583, score: 0.0024)
- **check_tasks_file** (def, line 421, score: 0.0024)
- **collect_environment_checks** (def, line 77, score: 0.0024)
- **collect_hooks_check** (def, line 164, score: 0.0024)
- **collect_stale_epics_check** (def, line 468, score: 0.0024)
- **collect_tasks_file_check** (def, line 349, score: 0.0024)
- **doctor** (def, line 871, score: 0.0024)

### src/cub/cli/errors.py

- **ExitCode** (def, line 15, score: 0.0024)
- **print_backend_not_initialized_error** (def, line 144, score: 0.0024)

... (215 more symbols omitted to fit budget)
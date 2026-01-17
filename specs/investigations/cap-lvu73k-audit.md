# Audit Report: let's track all the places we are using claude models directly so we can make...

**Capture ID:** cap-lvu73k
**Generated:** 2026-01-17 02:23:00 UTC
**Category:** audit

## Original Capture

let's track all the places we are using claude models directly so we can make sure to keep this as pluggable as possible with a main driver/harness

## Search Patterns

The following patterns were extracted and searched:

- `let's`
- `places`
- `are`
- `using`
- `claude`

## Findings

### Pattern: `places`

Found in 5 file(s):

- `src/cub/audit/dead_code.py`
- `src/cub/dashboard/tmux.py`
- `src/cub/core/bash_delegate.py`
- `src/cub/core/tasks/json.py`
- `tests/test_config_loader.py`

### Pattern: `are`

Found in 20 file(s):

- `src/cub/audit/coverage.py`
- `src/cub/audit/docs.py`
- `src/cub/audit/models.py`
- `src/cub/audit/dead_code.py`
- `src/cub/dashboard/status.py`
- `src/cub/dashboard/renderer.py`
- `src/cub/cli/status.py`
- `src/cub/cli/investigate.py`
- `src/cub/cli/delegated.py`
- `src/cub/cli/worktree.py`
- `src/cub/cli/uninstall.py`
- `src/cub/cli/capture.py`
- `src/cub/cli/captures.py`
- `src/cub/cli/organize_captures.py`
- `src/cub/cli/sandbox.py`
- `src/cub/cli/__init__.py`
- `src/cub/cli/audit.py`
- `src/cub/cli/run.py`
- `src/cub/utils/hooks.py`
- `src/cub/utils/logging.py`

### Pattern: `using`

Found in 19 file(s):

- `src/cub/audit/dead_code.py`
- `src/cub/dashboard/status.py`
- `src/cub/dashboard/__init__.py`
- `src/cub/dashboard/tmux.py`
- `src/cub/dashboard/renderer.py`
- `src/cub/cli/investigate.py`
- `src/cub/cli/uninstall.py`
- `src/cub/cli/upgrade.py`
- `src/cub/cli/audit.py`
- `src/cub/cli/run.py`
- `src/cub/utils/logging.py`
- `src/cub/core/sandbox/docker.py`
- `src/cub/core/worktree/parallel.py`
- `src/cub/core/tasks/json.py`
- `tests/test_dashboard_status_watcher.py`
- `scripts/generate_changelog.py`
- `tests/test_parallel_runner.py`
- `src/cub/core/captures/slug.py`
- `src/cub/core/captures/tagging.py`

### Pattern: `claude`

Found in 18 file(s):

- `src/cub/dashboard/tmux.py`
- `src/cub/cli/capture.py`
- `src/cub/cli/run.py`
- `src/cub/utils/hooks.py`
- `src/cub/utils/logging.py`
- `src/cub/core/harness/__init__.py`
- `src/cub/core/harness/claude.py`
- `src/cub/core/harness/backend.py`
- `src/cub/core/config/models.py`
- `tests/test_hooks.py`
- `tests/test_harness_backend.py`
- `tests/test_harness_claude.py`
- `tests/test_parallel_runner.py`
- `src/cub/core/worktree/parallel.py`
- `tests/test_logging.py`
- `tests/conftest.py`
- `tests/test_models.py`
- `src/cub/core/captures/slug.py`

## Next Steps

- [ ] Review the findings above
- [ ] Identify patterns that need changes
- [ ] Create tasks for necessary modifications

## Notes

*Add your analysis notes here.*

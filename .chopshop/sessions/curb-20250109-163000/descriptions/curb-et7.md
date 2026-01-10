## Context
Structured logs enable post-run analysis and debugging. JSONL is grep-friendly and jq-queryable.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Simple functions that build JSON and append to log file. Use jq -n for safe JSON construction.

## Implementation Steps
1. Create lib/logger.sh
2. Add _LOG_FILE variable (set during init)
3. Add logger_init(project_name, session_id) - sets up log file path
4. Add logger_write(event_type, data_json) - appends JSONL line
5. Ensure log directory exists before writing

## Acceptance Criteria
- [ ] Log file created at ~/.local/share/curb/logs/{project}/{session}.jsonl
- [ ] Each line is valid JSON
- [ ] Timestamps in ISO 8601 format
- [ ] Log file is append-only

## Files Likely Involved
- lib/logger.sh (new)
- lib/xdg.sh (for directory helpers)

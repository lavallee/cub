# Lifecycle Hooks

Cub supports custom hooks that execute at key points during autonomous execution. This directory contains hook scripts that run automatically during the session lifecycle.

## Hook Points

Cub provides four lifecycle hooks that you can use to integrate external tools or monitoring systems:

### pre-session
Runs **before** the harness session starts, before any tasks are executed.

**Use cases:**
- Notify external systems that a session is starting
- Set up monitoring or logging
- Perform initial validation or setup

**Context available via environment variables:**
- `CUB_HOOK_NAME`: "pre-session"
- `CUB_PROJECT_DIR`: Project directory path
- `CUB_HOOK_CONTEXT`: JSON object containing:
  - `session_id`: Unique session identifier
  - `harness_name`: Name of the harness being used (e.g., "claude")
  - `model`: Model name being used
  - `task_count`: Total number of tasks to execute
  - `epic_count`: Total number of epics
  - `project_dir`: Project directory path

### end-of-task
Runs **after** a task completes, whether it succeeded or failed.

**Use cases:**
- Post-task analysis or reporting
- Trigger dependent tasks in external systems
- Update progress dashboards
- Log task results to centralized systems

**Context available via environment variables:**
- `CUB_HOOK_NAME`: "end-of-task"
- `CUB_PROJECT_DIR`: Project directory path
- `CUB_HOOK_CONTEXT`: JSON object containing:
  - `task_id`: Task identifier
  - `task_title`: Task title/description
  - `status`: Task status ("closed" or "failed")
  - `success`: Boolean indicating success
  - `project_dir`: Project directory path
  - `session_id`: Session identifier
  - `parent_epic`: Parent epic ID if any
  - `duration_seconds`: How long the task took
  - `iterations`: Number of iterations/attempts
  - `error_message`: Error message if task failed

### end-of-epic
Runs **after** all tasks within an epic are completed.

**Use cases:**
- Generate epic completion reports
- Trigger post-epic analysis
- Update roadmap tracking systems
- Notify stakeholders of epic completion

**Context available via environment variables:**
- `CUB_HOOK_NAME`: "end-of-epic"
- `CUB_PROJECT_DIR`: Project directory path
- `CUB_HOOK_CONTEXT`: JSON object containing:
  - `epic_id`: Epic identifier
  - `epic_title`: Epic title
  - `project_dir`: Project directory path
  - `session_id`: Session identifier
  - `parent_plan`: Parent plan ID if any
  - `total_tasks`: Total number of tasks in epic
  - `completed_tasks`: Number of completed tasks
  - `failed_tasks`: Number of failed tasks
  - `skipped_tasks`: Number of skipped tasks
  - `duration_seconds`: Total time for the epic

### end-of-plan
Runs **after** all epics and tasks in a plan are completed.

**Use cases:**
- Generate comprehensive plan completion reports
- Post-execution analysis and metrics
- Release notifications
- Archive or finalize project deliverables

**Context available via environment variables:**
- `CUB_HOOK_NAME`: "end-of-plan"
- `CUB_PROJECT_DIR`: Project directory path
- `CUB_HOOK_CONTEXT`: JSON object containing:
  - `plan_id`: Plan identifier
  - `plan_title`: Plan title
  - `project_dir`: Project directory path
  - `session_id`: Session identifier
  - `total_epics`: Total number of epics
  - `completed_epics`: Number of completed epics
  - `total_tasks`: Total number of tasks
  - `completed_tasks`: Number of completed tasks
  - `failed_tasks`: Number of failed tasks
  - `duration_seconds`: Total time for the plan

## Hook Script Placement

Each hook point has its own subdirectory:

```
.cub/hooks/
├── pre-session/
│   ├── 01-setup.sh
│   └── 02-notify.sh
├── end-of-task/
│   ├── slack-notify.py
│   └── log-results.sh
├── end-of-epic/
│   └── update-dashboard.sh
└── end-of-plan/
    └── generate-report.sh
```

### Naming Convention

- Script files should be **executable** (have the execute permission bit set)
- Scripts are discovered and run in **sorted filename order** (alphanumeric)
- Use numbered prefixes (01-, 02-, etc.) to control execution order
- Only files with execute permission are run; non-executable files are ignored
- Hidden files (starting with `.`) are ignored

### Example Script

Create a simple hook script with a `.sh` extension:

```bash
#!/bin/bash
# .cub/hooks/end-of-task/01-notify.sh

# The hook context is available as JSON in an environment variable
CONTEXT="$CUB_HOOK_CONTEXT"

# Extract fields from the context (requires `jq`)
TASK_ID=$(echo "$CONTEXT" | jq -r '.task_id')
TASK_TITLE=$(echo "$CONTEXT" | jq -r '.task_title')
STATUS=$(echo "$CONTEXT" | jq -r '.status')

echo "Task $TASK_ID ($TASK_TITLE) completed with status: $STATUS"

# Example: Send notification to Slack
# curl -X POST -H 'Content-type: application/json' \
#     --data "{\"text\":\"Task $TASK_TITLE completed with status $STATUS\"}" \
#     $SLACK_WEBHOOK_URL

exit 0
```

### Debugging Hooks

To debug a hook script, you can:

1. Run it manually with sample context:
   ```bash
   export CUB_HOOK_NAME="end-of-task"
   export CUB_PROJECT_DIR="$(pwd)"
   export CUB_HOOK_CONTEXT='{"task_id":"test-1","task_title":"Test","status":"closed","success":true}'
   .cub/hooks/end-of-task/01-notify.sh
   ```

2. Add debugging to your script:
   ```bash
   #!/bin/bash
   set -x  # Enable debug output
   # ... rest of script
   ```

3. Check hook execution logs in the session logs

## Hook Configuration

Hooks are configured in `.cub/config.json` under the `hooks` section:

```json
{
  "hooks": {
    "enabled": true,
    "fail_fast": false
  }
}
```

- `enabled`: Set to `false` to disable all hooks
- `fail_fast`: If `true`, hook failures will stop execution (default: `false`)

## Best Practices

1. **Keep hooks lightweight**: Hooks should complete quickly to avoid slowing down execution
2. **Handle failures gracefully**: Use `exit 0` for non-critical hooks
3. **Log important events**: Write to files or external systems for auditing
4. **Use consistent naming**: Prefix scripts with numbers for execution order
5. **Document your hooks**: Add comments explaining what the hook does
6. **Test your hooks**: Run them manually to ensure they work as expected
7. **Avoid side effects**: Don't modify project files from hooks unless necessary
8. **Set proper permissions**: Use `chmod +x script.sh` to make scripts executable

## Troubleshooting

### Hooks not running
- Check that `enabled: true` in `.cub/config.json`
- Verify scripts have execute permission: `chmod +x .cub/hooks/*/script.sh`
- Check hook script directory exists: `.cub/hooks/{hook_name}/`

### Hook script fails silently
- Set `fail_fast: true` in config to see hook errors
- Add `set -e` at the top of shell scripts to exit on errors
- Check stderr output from hook execution

### Context not available
- Verify you're reading from `CUB_HOOK_CONTEXT` environment variable (not stdin)
- Use `jq` or your language's JSON parser to extract fields
- Check that hook point provides the fields you need (see context sections above)

## Global Hooks

In addition to project-level hooks in `.cub/hooks/`, cub also supports global hooks in:
- **macOS/Linux**: `~/.config/cub/hooks/`
- **Windows**: `%APPDATA%\cub\hooks\`

Global hooks run before project hooks, allowing you to set up organization-wide automation while projects can override with their own hooks.

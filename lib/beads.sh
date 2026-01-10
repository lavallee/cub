#!/usr/bin/env bash
#
# beads.sh - Beads CLI wrapper functions for curb
#
# Provides the same interface as tasks.sh but uses the beads (bd) CLI
# for task management instead of direct JSON manipulation.
#
# Requires: beads CLI (bd) to be installed
#   - npm: npm install -g @beads/bd
#   - brew: brew install steveyegge/beads/bd
#   - go: go install github.com/steveyegge/beads/cmd/bd@latest
#

# Check if beads is available
beads_available() {
    command -v bd >/dev/null 2>&1
}

# Check if beads is initialized in a project directory
# Usage: beads_initialized [project_dir]
beads_initialized() {
    local project_dir="${1:-.}"
    [[ -d "${project_dir}/.beads" ]] || [[ -f "${project_dir}/.beads/issues.jsonl" ]]
}

# Initialize beads in a project
beads_init() {
    local stealth="${1:-false}"

    if [[ "$stealth" == "true" ]]; then
        bd init --stealth
    else
        bd init
    fi
}

# Get in-progress task (if any)
# Returns single task JSON or empty
beads_get_in_progress_task() {
    bd list --status in_progress --limit 1 --json 2>/dev/null | jq '.[0] // empty | {
        id: .id,
        title: .title,
        type: (.issue_type // .type // "task"),
        status: .status,
        priority: ("P" + ((.priority // 2) | tostring)),
        description: (.description // ""),
        labels: (.labels // []),
        dependsOn: (.blocks // [])
    }'
}

# Get all ready tasks (no open blockers)
# Returns JSON array sorted by priority
# Optional filters: epic (parent ID), label (label name)
beads_get_ready_tasks() {
    local epic="${1:-}"
    local label="${2:-}"
    local flags=""

    if [[ -n "$epic" ]]; then
        flags="${flags} --parent ${epic}"
    fi
    if [[ -n "$label" ]]; then
        flags="${flags} --label ${label}"
    fi

    bd ready ${flags} --json 2>/dev/null | jq '
        # Transform beads output to match prd.json format
        [.[] | {
            id: .id,
            title: .title,
            type: (.issue_type // .type // "task"),
            status: .status,
            priority: ("P" + ((.priority // 2) | tostring)),
            description: (.description // ""),
            labels: (.labels // []),
            dependsOn: (.blocks // [])
        }]
        | sort_by(.priority)
    '
}

# Get a specific task by ID
beads_get_task() {
    local task_id="$1"

    bd show "$task_id" --json 2>/dev/null | jq '.[0] | {
        id: .id,
        title: .title,
        type: (.issue_type // .type // "task"),
        status: .status,
        priority: ("P" + ((.priority // 2) | tostring)),
        description: (.description // ""),
        labels: (.labels // []),
        acceptanceCriteria: (.acceptance_criteria // []),
        dependsOn: (.blocks // [])
    }'
}

# Update task status
beads_update_task_status() {
    local task_id="$1"
    local new_status="$2"

    bd update "$task_id" --status "$new_status"
}

# Add a note/comment to a task
beads_add_task_note() {
    local task_id="$1"
    local note="$2"

    bd comment "$task_id" "$note"
}

# Create a new task
# Expects JSON with: title, type, priority, description, dependsOn
beads_create_task() {
    local task_json="$1"

    local title=$(echo "$task_json" | jq -r '.title')
    local type=$(echo "$task_json" | jq -r '.type // "task"')
    local priority=$(echo "$task_json" | jq -r '.priority // "P2"' | sed 's/P//')
    local desc=$(echo "$task_json" | jq -r '.description // ""')

    # Create the task
    local new_id
    new_id=$(bd create "$title" -p "$priority" --type "$type" --json 2>/dev/null | jq -r '.id')

    # Add description if present
    if [[ -n "$desc" && "$desc" != "null" ]]; then
        bd update "$new_id" --description "$desc"
    fi

    # Add dependencies
    local deps
    deps=$(echo "$task_json" | jq -r '.dependsOn // [] | .[]')
    for dep in $deps; do
        bd dep add "$new_id" "$dep" --type blocks
    done

    echo "$new_id"
}

# Get task counts by status
beads_get_task_counts() {
    bd list --json 2>/dev/null | jq '{
        total: length,
        open: ([.[] | select(.status == "open")] | length),
        in_progress: ([.[] | select(.status == "in_progress")] | length),
        closed: ([.[] | select(.status == "closed")] | length)
    }'
}

# Check if all tasks are complete
beads_all_tasks_complete() {
    local remaining
    remaining=$(bd list --json 2>/dev/null | jq '[.[] | select(.status != "closed")] | length')
    [[ "$remaining" -eq 0 ]]
}

# Get blocked tasks
beads_get_blocked_tasks() {
    bd list --json 2>/dev/null | jq '
        # Get IDs of closed tasks
        ([.[] | select(.status == "closed") | .id]) as $closed |
        # Filter to open tasks with unsatisfied dependencies
        [
            .[]
            | select(.status == "open")
            | select(
                (.blocks // []) | any(. as $dep | $closed | contains([$dep]) | not)
            )
        ]
    '
}

# List all tasks (for status display)
beads_list_tasks() {
    bd list --json 2>/dev/null | jq '[.[] | {
        id: .id,
        title: .title,
        type: (.type // "task"),
        status: .status,
        priority: ("P" + ((.priority // 2) | tostring)),
        description: (.description // "")
    }]'
}

# Sync beads state (useful after changes)
beads_sync() {
    bd sync 2>/dev/null
}

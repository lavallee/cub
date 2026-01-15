#!/usr/bin/env bash
#
# tasks.sh - Unified task management interface for cub
#
# Supports two backends:
#   1. beads (bd CLI) - preferred when available
#   2. prd.json - JSON file fallback
#
# Backend selection:
#   - CUB_BACKEND=beads|json  - explicit selection
#   - Auto-detect: uses beads if available and initialized, else json
#

# Include guard to prevent re-sourcing and resetting _TASK_BACKEND
if [[ -n "${_TASKS_SH_LOADED:-}" ]]; then
    return 0
fi
_TASKS_SH_LOADED=1

CUB_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source beads wrapper if available
if [[ -f "${CUB_LIB_DIR}/beads.sh" ]]; then
    source "${CUB_LIB_DIR}/beads.sh"
fi

# Backend state (set by detect_backend)
_TASK_BACKEND=""

# Detect which backend to use
detect_backend() {
    local project_dir="${1:-.}"

    # Check for explicit override
    if [[ -n "${CUB_BACKEND:-}" ]]; then
        case "$CUB_BACKEND" in
            beads|bd)
                if ! beads_available; then
                    echo "WARNING: CUB_BACKEND=beads but beads (bd) not installed, falling back to json" >&2
                    _TASK_BACKEND="json"
                elif ! beads_initialized "$project_dir"; then
                    echo "WARNING: CUB_BACKEND=beads but .beads/ not found in ${project_dir}. Run 'bd init' first, falling back to json" >&2
                    _TASK_BACKEND="json"
                else
                    _TASK_BACKEND="beads"
                fi
                ;;
            json|prd)
                _TASK_BACKEND="json"
                ;;
            auto)
                # Will be handled in auto-detect below
                ;;
            *)
                echo "WARNING: Unknown CUB_BACKEND=$CUB_BACKEND, using auto-detect" >&2
                ;;
        esac
    fi

    # Auto-detect if not explicitly set
    if [[ -z "$_TASK_BACKEND" ]]; then
        if beads_available && beads_initialized "$project_dir"; then
            _TASK_BACKEND="beads"
        elif [[ -f "${project_dir}/prd.json" ]]; then
            _TASK_BACKEND="json"
        else
            # Default to json (will be created)
            _TASK_BACKEND="json"
        fi
    fi

    echo "$_TASK_BACKEND"
}

# Get the current backend
# Optional parameter: project_dir (defaults to current directory)
get_backend() {
    local project_dir="${1:-.}"
    if [[ -z "$_TASK_BACKEND" ]]; then
        detect_backend "$project_dir" >/dev/null
    fi
    echo "$_TASK_BACKEND"
}

#
# ============================================================================
# Unified Interface - delegates to appropriate backend
# ============================================================================
#

# Check if a task is ready (unblocked)
# Returns 0 if ready, 1 if blocked
is_task_ready() {
    local prd="$1"
    local task_id="$2"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_is_task_ready "$task_id"
    else
        json_is_task_ready "$prd" "$task_id"
    fi
}

# Get in-progress task (if any)
# Returns single task JSON or empty
# Optional filters: epic (parent ID), label (label name)
get_in_progress_task() {
    local prd="$1"
    local epic="${2:-}"
    local label="${3:-}"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_get_in_progress_task "$epic" "$label"
    else
        json_get_in_progress_task "$prd" "$epic" "$label"
    fi
}

# Get all in-progress tasks
# Returns JSON array of all tasks with status=in_progress
# Used by doctor command to detect stuck tasks
get_in_progress_tasks() {
    local prd="$1"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_get_in_progress_tasks
    else
        json_get_in_progress_tasks "$prd"
    fi
}

# Get all ready tasks (status=open, all dependencies closed)
# Returns JSON array sorted by priority
# Optional filters: epic (parent ID), label (label name)
get_ready_tasks() {
    local prd="$1"
    local epic="${2:-}"   # Optional epic/parent filter
    local label="${3:-}"  # Optional label filter

    local backend=$(get_backend)
    if [[ "${DEBUG:-}" == "true" ]]; then
        echo "[DEBUG get_ready_tasks] backend=$backend prd=$prd _TASK_BACKEND=$_TASK_BACKEND" >&2
    fi

    if [[ "$backend" == "beads" ]]; then
        beads_get_ready_tasks "$epic" "$label"
    else
        json_get_ready_tasks "$prd" "$epic" "$label"
    fi
}

# Get a specific task by ID
get_task() {
    local prd="$1"
    local task_id="$2"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_get_task "$task_id"
    else
        json_get_task "$prd" "$task_id"
    fi
}

# Update task status
update_task_status() {
    local prd="$1"
    local task_id="$2"
    local new_status="$3"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_update_task_status "$task_id" "$new_status"
    else
        json_update_task_status "$prd" "$task_id" "$new_status"
    fi
}

# Claim a task (mark as in_progress and set assignee for beads backend)
# Usage: claim_task <prd> <task_id> <session_name>
# Returns: 0 on success, 1 on error
claim_task() {
    local prd="$1"
    local task_id="$2"
    local session_name="$3"

    if [[ -z "$task_id" ]] || [[ -z "$session_name" ]]; then
        echo "ERROR: claim_task requires task_id and session_name" >&2
        return 1
    fi

    if [[ "$(get_backend)" == "beads" ]]; then
        # For beads: set both status and assignee
        beads_claim_task "$task_id" "$session_name"
    else
        # For JSON: just update status to in_progress
        json_update_task_status "$prd" "$task_id" "in_progress"
    fi
}

# Add a note to a task
add_task_note() {
    local prd="$1"
    local task_id="$2"
    local note="$3"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_add_task_note "$task_id" "$note"
    else
        json_add_task_note "$prd" "$task_id" "$note"
    fi
}

# Create a new task
create_task() {
    local prd="$1"
    local task_json="$2"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_create_task "$task_json"
    else
        json_create_task "$prd" "$task_json"
    fi
}

# Get task counts by status
get_task_counts() {
    local prd="$1"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_get_task_counts
    else
        json_get_task_counts "$prd"
    fi
}

# Check if all tasks are complete
all_tasks_complete() {
    local prd="$1"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_all_tasks_complete
    else
        json_all_tasks_complete "$prd"
    fi
}

# Get count of remaining (non-closed) tasks
# Optional filters: epic (parent ID), label (label name)
get_remaining_count() {
    local prd="$1"
    local epic="${2:-}"
    local label="${3:-}"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_get_remaining_count "$epic" "$label"
    else
        json_get_remaining_count "$prd" "$epic" "$label"
    fi
}

# Get blocked tasks
get_blocked_tasks() {
    local prd="$1"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_get_blocked_tasks
    else
        json_get_blocked_tasks "$prd"
    fi
}

# Verify a task is properly closed
# Returns 0 if task is closed, 1 otherwise
# Usage: verify_task_closed <prd> <task_id>
verify_task_closed() {
    local prd="$1"
    local task_id="$2"

    if [[ -z "$task_id" ]]; then
        echo "ERROR: verify_task_closed requires task_id" >&2
        return 1
    fi

    local backend=$(get_backend)

    if [[ "$backend" == "beads" ]]; then
        # Check status via beads
        local status
        status=$(bd show "$task_id" --json 2>/dev/null | jq -r '.status // "unknown"')
        if [[ "$status" == "closed" ]]; then
            return 0
        else
            echo "Task $task_id not closed in beads (status: $status)" >&2
            return 1
        fi
    else
        # Check status in prd.json
        if [[ ! -f "$prd" ]]; then
            echo "ERROR: prd.json not found at $prd" >&2
            return 1
        fi
        local status
        status=$(jq -r --arg id "$task_id" '.tasks[] | select(.id == $id) | .status' "$prd" 2>/dev/null)
        if [[ "$status" == "closed" ]]; then
            return 0
        else
            echo "Task $task_id not closed in prd.json (status: $status)" >&2
            return 1
        fi
    fi
}

# Auto-close a task (for use after successful harness completion)
# Returns 0 on success, 1 on failure
# Usage: auto_close_task <prd> <task_id>
auto_close_task() {
    local prd="$1"
    local task_id="$2"

    if [[ -z "$task_id" ]]; then
        echo "ERROR: auto_close_task requires task_id" >&2
        return 1
    fi

    local backend=$(get_backend)

    # Check if already closed
    if verify_task_closed "$prd" "$task_id" 2>/dev/null; then
        return 0  # Already closed, nothing to do
    fi

    if [[ "$backend" == "beads" ]]; then
        # Close via beads
        if bd close "$task_id" 2>/dev/null; then
            echo "Auto-closed task $task_id via beads" >&2
            return 0
        else
            echo "Failed to auto-close task $task_id via beads" >&2
            return 1
        fi
    else
        # Close via prd.json update
        json_update_task_status "$prd" "$task_id" "closed"
        echo "Auto-closed task $task_id in prd.json" >&2
        return 0
    fi
}

#
# ============================================================================
# JSON Backend Implementation (prd.json)
# ============================================================================
#

# Check if a task is ready (unblocked) in prd.json
# Returns 0 if ready, 1 if blocked
json_is_task_ready() {
    local prd="$1"
    local task_id="$2"

    # Check if task's dependencies are all closed
    jq -e --arg id "$task_id" '
        (.tasks | map(select(.status == "closed") | .id)) as $closed |
        .tasks[]
        | select(.id == $id)
        | (.dependsOn // []) | all(. as $dep | $closed | contains([$dep]))
    ' "$prd" >/dev/null 2>&1
}

# Get in-progress task from prd.json
# Optional filters: epic (parent ID), label (label name)
json_get_in_progress_task() {
    local prd="$1"
    local epic="${2:-}"
    local label="${3:-}"

    jq --arg epic "$epic" --arg label "$label" '
        [
            .tasks[]
            | select(.status == "in_progress")
            | if $epic != "" then select(.parent == $epic) else . end
            | if $label != "" then select((.labels // []) | any(. == $label)) else . end
        ] | first // empty
    ' "$prd"
}

# Get all in-progress tasks from prd.json
# Returns JSON array of all tasks with status=in_progress
# Used by doctor command to detect stuck tasks
json_get_in_progress_tasks() {
    local prd="$1"

    jq '[.tasks[] | select(.status == "in_progress")]' "$prd"
}

# Get all ready tasks from prd.json
# Optional filters: epic (parent ID), label (label name)
json_get_ready_tasks() {
    local prd="$1"
    local epic="${2:-}"
    local label="${3:-}"

    if [[ "${DEBUG:-}" == "true" ]]; then
        echo "[DEBUG json_get_ready_tasks] prd=$prd epic=$epic label=$label" >&2
    fi

    # Check if file exists first
    if [[ ! -f "$prd" ]]; then
        echo "Error: PRD file not found: $prd" >&2
        return 1
    fi

    local result
    result=$(jq --arg epic "$epic" --arg label "$label" '
        # Build a set of closed task IDs
        (.tasks | map(select(.status == "closed") | .id)) as $closed |

        # Filter to open tasks where all dependencies are satisfied
        [
            .tasks[]
            | select(.status == "open")
            | select(
                (.dependsOn // []) | all(. as $dep | $closed | contains([$dep]))
            )
            # Apply epic filter if specified
            | if $epic != "" then select(.parent == $epic) else . end
            # Apply label filter if specified
            | if $label != "" then select((.labels // []) | any(. == $label)) else . end
        ]
        # Sort by priority (P0 < P1 < P2 < P3 < P4)
        | sort_by(.priority)
    ' "$prd" 2>&1) || return $?

    if [[ "${DEBUG:-}" == "true" ]]; then
        echo "[DEBUG json_get_ready_tasks] result=${result:0:200}" >&2
    fi

    echo "$result"
}

# Get a specific task by ID from prd.json
json_get_task() {
    local prd="$1"
    local task_id="$2"

    jq --arg id "$task_id" '.tasks[] | select(.id == $id)' "$prd"
}

# Update task status in prd.json
json_update_task_status() {
    local prd="$1"
    local task_id="$2"
    local new_status="$3"

    local tmp=$(mktemp)

    jq --arg id "$task_id" --arg status "$new_status" '
        .tasks = [
            .tasks[] |
            if .id == $id then
                .status = $status
            else
                .
            end
        ]
    ' "$prd" > "$tmp" && mv "$tmp" "$prd"
}

# Add a note to a task in prd.json
json_add_task_note() {
    local prd="$1"
    local task_id="$2"
    local note="$3"

    local tmp=$(mktemp)
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    jq --arg id "$task_id" --arg note "$note" --arg ts "$timestamp" '
        .tasks = [
            .tasks[] |
            if .id == $id then
                .notes = ((.notes // "") + "\n[" + $ts + "] " + $note)
            else
                .
            end
        ]
    ' "$prd" > "$tmp" && mv "$tmp" "$prd"
}

# Create a new task in prd.json
json_create_task() {
    local prd="$1"
    local task_json="$2"

    local tmp=$(mktemp)

    jq --argjson task "$task_json" '.tasks += [$task]' "$prd" > "$tmp" && mv "$tmp" "$prd"
}

# Generate a new task ID with the project prefix
generate_task_id() {
    local prd="$1"

    if [[ "$(get_backend)" == "beads" ]]; then
        # Beads generates IDs automatically
        echo "bd-auto"
    else
        local prefix=$(jq -r '.prefix // "prd"' "$prd")
        local hash=$(head -c 100 /dev/urandom | shasum | head -c 4)
        echo "${prefix}-${hash}"
    fi
}

# Get task counts from prd.json
json_get_task_counts() {
    local prd="$1"

    jq '{
        total: (.tasks | length),
        open: ([.tasks[] | select(.status == "open")] | length),
        in_progress: ([.tasks[] | select(.status == "in_progress")] | length),
        closed: ([.tasks[] | select(.status == "closed")] | length)
    }' "$prd"
}

# Check if all tasks are complete in prd.json
json_all_tasks_complete() {
    local prd="$1"

    local remaining=$(jq '[.tasks[] | select(.status != "closed")] | length' "$prd")
    [[ "$remaining" -eq 0 ]]
}

# Get count of remaining (non-closed) tasks from prd.json
json_get_remaining_count() {
    local prd="$1"
    local epic="${2:-}"
    local label="${3:-}"

    # Build jq filter based on optional epic/label
    if [[ -n "$epic" ]]; then
        jq --arg epic "$epic" '[.tasks[] | select(.status != "closed") | select(.parent == $epic or .epic == $epic)] | length' "$prd"
    elif [[ -n "$label" ]]; then
        jq --arg label "$label" '[.tasks[] | select(.status != "closed") | select(.labels | contains([$label]))] | length' "$prd"
    else
        jq '[.tasks[] | select(.status != "closed")] | length' "$prd"
    fi
}

# Get blocked tasks from prd.json
json_get_blocked_tasks() {
    local prd="$1"

    jq '
        (.tasks | map(select(.status == "closed") | .id)) as $closed |
        [
            .tasks[]
            | select(.status == "open")
            | select(
                (.dependsOn // []) | any(. as $dep | $closed | contains([$dep]) | not)
            )
        ]
    ' "$prd"
}

# Validate prd.json structure
validate_prd() {
    local prd="$1"

    # For beads, validation is handled by bd
    if [[ "$(get_backend)" == "beads" ]]; then
        echo "OK (beads backend)"
        return 0
    fi

    # Check required fields
    if ! jq -e '.tasks' "$prd" >/dev/null 2>&1; then
        echo "ERROR: prd.json missing 'tasks' array"
        return 1
    fi

    # Check each task has required fields
    local invalid
    invalid=$(jq '[.tasks[] | select(.id == null or .title == null or .status == null)] | length' "$prd")

    if [[ "$invalid" -gt 0 ]]; then
        echo "ERROR: ${invalid} tasks missing required fields (id, title, status)"
        return 1
    fi

    # Check for duplicate IDs
    local total=$(jq '.tasks | length' "$prd")
    local unique=$(jq '.tasks | map(.id) | unique | length' "$prd")

    if [[ "$total" -ne "$unique" ]]; then
        echo "ERROR: Duplicate task IDs found"
        return 1
    fi

    # Check dependency references
    local bad_deps
    bad_deps=$(jq '
        (.tasks | map(.id)) as $all_ids |
        [
            .tasks[]
            | .id as $tid
            | (.dependsOn // [])[]
            | select(. as $dep | $all_ids | contains([$dep]) | not)
        ]
    ' "$prd")

    if [[ "$bad_deps" != "[]" ]]; then
        echo "ERROR: Invalid dependency references: $bad_deps"
        return 1
    fi

    echo "OK"
    return 0
}

# Export task to beads CLI format (for migration)
export_to_beads() {
    local prd="$1"
    local task_id="$2"

    local task
    task=$(json_get_task "$prd" "$task_id")

    if [[ -z "$task" || "$task" == "null" ]]; then
        echo "Task not found: $task_id"
        return 1
    fi

    local title=$(echo "$task" | jq -r '.title')
    local type=$(echo "$task" | jq -r '.type // "task"')
    local priority=$(echo "$task" | jq -r '.priority // "P2"' | sed 's/P//')
    local desc=$(echo "$task" | jq -r '.description // ""')

    echo "bd create \"${title}\" -p ${priority} --type ${type}"
}

# Import from beads to prd.json (for migration)
import_from_beads() {
    local prd="$1"

    if ! beads_available; then
        echo "ERROR: beads not installed"
        return 1
    fi

    local tasks
    tasks=$(beads_list_tasks)

    # Create prd.json structure
    local prefix=$(basename "$(pwd)" | cut -c1-3)
    echo "{\"prefix\": \"${prefix}\", \"tasks\": ${tasks}}" | jq '.' > "$prd"
}

# Migrate from prd.json to beads
# Creates all tasks in beads and sets up dependencies
migrate_json_to_beads() {
    local prd="$1"
    local dry_run="${2:-false}"

    if ! beads_available; then
        echo "ERROR: beads (bd) not installed"
        echo "Install with: brew install steveyegge/beads/bd"
        return 1
    fi

    if [[ ! -f "$prd" ]]; then
        echo "ERROR: prd.json not found at $prd"
        return 1
    fi

    # Initialize beads if not already
    if ! beads_initialized; then
        echo "Initializing beads..."
        if [[ "$dry_run" == "true" ]]; then
            echo "[DRY RUN] Would run: bd init"
        else
            bd init
        fi
    fi

    # Create a mapping file for old ID -> new ID
    local id_map=$(mktemp)
    echo "{}" > "$id_map"

    # Get all tasks sorted by dependencies (tasks with no deps first)
    local tasks
    tasks=$(jq '[.tasks[]] | sort_by(.dependsOn | length)' "$prd")
    local task_count
    task_count=$(echo "$tasks" | jq 'length')

    echo "Migrating $task_count tasks from prd.json to beads..."
    echo ""

    # First pass: create all tasks
    echo "Pass 1: Creating tasks..."
    local i=0
    while [[ $i -lt $task_count ]]; do
        local task
        task=$(echo "$tasks" | jq ".[$i]")

        local old_id=$(echo "$task" | jq -r '.id')
        local title=$(echo "$task" | jq -r '.title')
        local task_type=$(echo "$task" | jq -r '.type // "task"')
        local priority=$(echo "$task" | jq -r '.priority // "P2"' | sed 's/P//')
        local status=$(echo "$task" | jq -r '.status // "open"')
        local desc=$(echo "$task" | jq -r '.description // ""')

        echo "  [$((i+1))/$task_count] $old_id: $title"

        if [[ "$dry_run" == "true" ]]; then
            echo "    [DRY RUN] Would create task with priority $priority, type $task_type"
            # Use placeholder ID for dry run
            local new_id="bd-dry-$i"
        else
            # Create the task in beads
            local create_output
            create_output=$(bd create "$title" -p "$priority" --json 2>/dev/null)
            local new_id
            new_id=$(echo "$create_output" | jq -r '.id // empty')

            if [[ -z "$new_id" ]]; then
                echo "    ERROR: Failed to create task"
                ((i++))
                continue
            fi

            echo "    Created: $new_id"

            # Update description if present
            if [[ -n "$desc" && "$desc" != "null" && "$desc" != "" ]]; then
                bd update "$new_id" --description "$desc" 2>/dev/null
            fi

            # Update status if not open
            if [[ "$status" != "open" ]]; then
                bd update "$new_id" --status "$status" 2>/dev/null
                echo "    Status: $status"
            fi
        fi

        # Store ID mapping
        local tmp_map=$(mktemp)
        jq --arg old "$old_id" --arg new "$new_id" '. + {($old): $new}' "$id_map" > "$tmp_map"
        mv "$tmp_map" "$id_map"

        ((i++))
    done

    echo ""
    echo "Pass 2: Setting up dependencies..."

    # Second pass: set up dependencies
    i=0
    while [[ $i -lt $task_count ]]; do
        local task
        task=$(echo "$tasks" | jq ".[$i]")

        local old_id=$(echo "$task" | jq -r '.id')
        local deps
        deps=$(echo "$task" | jq -r '.dependsOn // [] | .[]')

        if [[ -n "$deps" ]]; then
            local new_id
            new_id=$(jq -r --arg id "$old_id" '.[$id] // empty' "$id_map")

            for dep_old_id in $deps; do
                local dep_new_id
                dep_new_id=$(jq -r --arg id "$dep_old_id" '.[$id] // empty' "$id_map")

                if [[ -n "$new_id" && -n "$dep_new_id" ]]; then
                    echo "  $new_id depends on $dep_new_id (was: $old_id -> $dep_old_id)"
                    if [[ "$dry_run" != "true" ]]; then
                        bd dep add "$new_id" "$dep_new_id" --type blocks 2>/dev/null
                    fi
                fi
            done
        fi

        ((i++))
    done

    # Save ID mapping for reference
    local mapping_file="${prd%.json}_id_mapping.json"
    if [[ "$dry_run" != "true" ]]; then
        cp "$id_map" "$mapping_file"
        echo ""
        echo "ID mapping saved to: $mapping_file"
    fi

    rm -f "$id_map"

    echo ""
    echo "Migration complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Verify with: bd list"
    echo "  2. Check ready tasks: bd ready"
    echo "  3. Run cub (will auto-detect beads): cub --status"
    if [[ "$dry_run" != "true" ]]; then
        echo "  4. Optionally backup and remove prd.json"
    fi
}

# ============================================================================
# Acceptance Criteria Parsing
# ============================================================================
#
# Functions to parse and verify acceptance criteria from task descriptions.
# Acceptance criteria are typically markdown checkboxes:
#   - [ ] Unchecked criterion
#   - [x] Checked criterion
#
# These functions support both beads and prd.json backends.

# Parse acceptance criteria from a task description
# Returns one criterion per line (just the text, without checkbox)
# Usage: parse_acceptance_criteria "task description"
# Example output:
#   All tests pass
#   Documentation updated
parse_acceptance_criteria() {
    local description="$1"

    if [[ -z "$description" ]]; then
        return 0
    fi

    # Extract lines that match markdown checkbox pattern
    # - [ ] unchecked item
    # - [x] or - [X] checked item
    # Supports both with and without leading whitespace
    # Note: Using POSIX character classes for macOS compatibility
    echo "$description" | grep -E '^[[:space:]]*-[[:space:]]*\[[xX ]\]' | \
        sed 's/^[[:space:]]*-[[:space:]]*\[[xX ]\][[:space:]]*//' | \
        sed 's/[[:space:]]*$//'
}

# Count acceptance criteria in a description
# Usage: count_acceptance_criteria "description"
count_acceptance_criteria() {
    local description="$1"
    local criteria
    criteria=$(parse_acceptance_criteria "$description")

    if [[ -z "$criteria" ]]; then
        echo "0"
    else
        echo "$criteria" | wc -l | tr -d ' '
    fi
}

# Get acceptance criteria for a task by ID
# Returns criteria as newline-separated list
# Usage: get_task_acceptance_criteria task_id [prd_file]
get_task_acceptance_criteria() {
    local task_id="$1"
    local prd="${2:-prd.json}"

    local description

    if [[ "$(get_backend)" == "beads" ]]; then
        # Get description from beads
        description=$(bd show "$task_id" 2>/dev/null | sed -n '/^Description:/,/^Labels:\|^Depends on/p' | \
            sed '1d;$d' | sed '/^$/d')
    else
        # Get description from prd.json
        description=$(json_get_task "$prd" "$task_id" | jq -r '.description // ""')
    fi

    parse_acceptance_criteria "$description"
}

# Check if a task has acceptance criteria
# Returns 0 if has criteria, 1 otherwise
# Usage: task_has_acceptance_criteria task_id [prd_file]
task_has_acceptance_criteria() {
    local task_id="$1"
    local prd="${2:-prd.json}"

    local count
    count=$(get_task_acceptance_criteria "$task_id" "$prd" | wc -l | tr -d ' ')

    [[ "$count" -gt 0 ]]
}

# Verify acceptance criteria for a task
# This is a placeholder for more sophisticated verification
# Currently just checks if criteria exist and logs them
# Returns 0 if no criteria or all criteria are checkable, 1 if verification fails
# Usage: verify_acceptance_criteria task_id [prd_file]
verify_acceptance_criteria() {
    local task_id="$1"
    local prd="${2:-prd.json}"

    local criteria
    criteria=$(get_task_acceptance_criteria "$task_id" "$prd")

    if [[ -z "$criteria" ]]; then
        # No criteria = default behavior (pass)
        echo "[verify] No acceptance criteria found for $task_id"
        return 0
    fi

    local count
    count=$(echo "$criteria" | wc -l | tr -d ' ')

    echo "[verify] Found $count acceptance criteria for $task_id:"
    echo "$criteria" | while IFS= read -r criterion; do
        echo "[verify]   - $criterion"
    done

    # For now, we don't auto-verify criteria (would require AI interpretation)
    # Future enhancement: parse criteria for verifiable patterns like:
    #   - "tests pass" -> run tests
    #   - "builds successfully" -> run build
    #   - "lint passes" -> run lint
    # For now, just log and return success (human/AI verifies)
    return 0
}

# Format acceptance criteria for prompt inclusion
# Returns markdown-formatted criteria suitable for AI prompt
# Usage: format_acceptance_criteria_for_prompt task_id [prd_file]
format_acceptance_criteria_for_prompt() {
    local task_id="$1"
    local prd="${2:-prd.json}"

    local criteria
    criteria=$(get_task_acceptance_criteria "$task_id" "$prd")

    if [[ -z "$criteria" ]]; then
        return 0
    fi

    echo ""
    echo "## Acceptance Criteria"
    echo ""
    echo "The following criteria must be met before this task can be considered complete:"
    echo ""
    echo "$criteria" | while IFS= read -r criterion; do
        echo "- [ ] $criterion"
    done
    echo ""
    echo "Please verify each criterion is satisfied before marking the task as done."
}

# ============================================================================
# Task Completeness Validation
# ============================================================================
#
# Functions to validate task completeness across title, description,
# and acceptance criteria fields.

# Validate task completeness for a single task
# Checks:
#   1. Title is present and at least 10 characters
#   2. Description is present and non-empty
#   3. Acceptance criteria are defined (via description markdown or acceptanceCriteria field)
#
# Returns JSON object with completeness status:
# {
#   "id": "task-id",
#   "is_complete": true|false,
#   "issues": ["issue1", "issue2"]
# }
# Usage: validate_task_completeness task_id [prd_file]
validate_task_completeness() {
    local task_id="$1"
    local prd="${2:-prd.json}"

    if [[ -z "$task_id" ]]; then
        echo '{"error": "task_id is required"}' >&2
        return 1
    fi

    local backend=$(get_backend)
    local title=""
    local description=""
    local criteria_count=0
    local issues=()

    if [[ "$backend" == "beads" ]]; then
        # Get task from beads
        local task_json
        task_json=$(bd show "$task_id" --json 2>/dev/null) || {
            echo "{\"error\": \"task not found: $task_id\"}" >&2
            return 1
        }

        title=$(echo "$task_json" | jq -r '.title // ""')
        description=$(echo "$task_json" | jq -r '.description // ""')

        # Check for acceptance_criteria field if present
        criteria_count=$(echo "$task_json" | jq '(.acceptance_criteria // []) | length')
    else
        # Get task from prd.json
        local task
        task=$(json_get_task "$prd" "$task_id")

        if [[ -z "$task" || "$task" == "null" ]]; then
            echo "{\"error\": \"task not found: $task_id\"}" >&2
            return 1
        fi

        title=$(echo "$task" | jq -r '.title // ""')
        description=$(echo "$task" | jq -r '.description // ""')

        # Check for acceptanceCriteria field
        criteria_count=$(echo "$task" | jq '(.acceptanceCriteria // []) | length')
    fi

    # Validate title
    if [[ -z "$title" ]]; then
        issues+=("Title is missing")
    elif [[ ${#title} -lt 10 ]]; then
        issues+=("Title is too short (${#title} chars, minimum 10 required)")
    fi

    # Validate description
    if [[ -z "$description" ]]; then
        issues+=("Description is missing")
    fi

    # Validate acceptance criteria
    # Check if there are no criteria AND no markdown in description
    if [[ "$criteria_count" -eq 0 ]]; then
        # No criteria in dedicated field, check markdown in description
        local markdown_criteria
        markdown_criteria=$(parse_acceptance_criteria "$description")

        if [[ -z "$markdown_criteria" ]]; then
            issues+=("Acceptance criteria are not defined (no markdown checkboxes or acceptanceCriteria field)")
        fi
    fi

    # Build result JSON
    local is_complete="true"
    if [[ ${#issues[@]} -gt 0 ]]; then
        is_complete="false"
    fi

    # Output result as JSON
    printf '{\n'
    printf '  "id": "%s",\n' "$task_id"
    printf '  "is_complete": %s,\n' "$is_complete"
    printf '  "issues": ['

    if [[ ${#issues[@]} -gt 0 ]]; then
        for i in "${!issues[@]}"; do
            if [[ $i -gt 0 ]]; then
                printf ', '
            fi
            printf '"%s"' "$(printf '%s\n' "${issues[$i]}" | sed 's/"/\\"/g')"
        done
    fi

    printf ']\n'
    printf '}\n'

    return 0
}

# Validate completeness for all tasks in a project
# Returns JSON array with completeness status for each task
# Optional parameter: prd_file (defaults to prd.json)
# Returns array of validation results:
# [
#   {"id": "task-1", "is_complete": true, "issues": []},
#   {"id": "task-2", "is_complete": false, "issues": ["Title is missing"]}
# ]
validate_all_tasks_completeness() {
    local prd="${1:-prd.json}"

    if [[ "$(get_backend)" == "beads" ]]; then
        # Get all tasks from beads
        local tasks
        tasks=$(bd list --json 2>/dev/null) || return 1

        echo "["
        local first=true

        echo "$tasks" | jq -r '.[] | .id' | while read -r task_id; do
            if [[ "$first" != "true" ]]; then
                echo ","
            fi
            first=false

            validate_task_completeness "$task_id" | tr '\n' ' '
        done

        echo ""
        echo "]"
    else
        # Get all tasks from prd.json
        if [[ ! -f "$prd" ]]; then
            echo "[]"
            return 0
        fi

        echo "["
        local first=true

        jq -r '.tasks[] | .id' "$prd" | while read -r task_id; do
            if [[ "$first" != "true" ]]; then
                echo ","
            fi
            first=false

            validate_task_completeness "$task_id" "$prd" | tr '\n' ' '
        done

        echo ""
        echo "]"
    fi

    return 0
}

# Get summary of completeness issues across all tasks
# Returns markdown-formatted list of incomplete tasks
# Usage: get_completeness_summary [prd_file]
get_completeness_summary() {
    local prd="${1:-prd.json}"

    local results
    results=$(validate_all_tasks_completeness "$prd")

    local incomplete_count
    incomplete_count=$(echo "$results" | jq '[.[] | select(.is_complete == false)] | length')

    if [[ "$incomplete_count" -eq 0 ]]; then
        echo "✓ All tasks are complete"
        return 0
    fi

    echo "⚠ Found $incomplete_count incomplete task(s):"
    echo ""

    echo "$results" | jq -r '.[] | select(.is_complete == false) | "**\(.id)**\n" + (.issues | map("  - \(.)") | join("\n"))' | while read -r line; do
        if [[ -n "$line" ]]; then
            echo "$line"
        fi
    done

    return 1
}

# Validate feasibility of a task
# Checks:
#   1. All task dependencies are complete (status: closed)
#   2. Required files referenced in description exist
#   3. External dependencies are available (jq, harness, etc.)
#
# Returns JSON object with feasibility status:
# {
#   "id": "task-id",
#   "is_feasible": true|false,
#   "issues": ["issue1", "issue2"]
# }
# Usage: validate_task_feasibility task_id [prd_file]
validate_task_feasibility() {
    local task_id="$1"
    local prd="${2:-prd.json}"

    if [[ -z "$task_id" ]]; then
        echo '{"error": "task_id is required"}' >&2
        return 1
    fi

    local backend=$(get_backend)
    local description=""
    local depends_on=()
    local issues=()

    if [[ "$backend" == "beads" ]]; then
        # Get task from beads
        local task_json
        task_json=$(bd show "$task_id" --json 2>/dev/null) || {
            echo "{\"error\": \"task not found: $task_id\"}" >&2
            return 1
        }

        description=$(echo "$task_json" | jq -r '.description // ""')
        # In beads, blocking is represented as "blocks" field (tasks that block this one)
        # Get tasks that this task depends on
        local blocking_tasks
        blocking_tasks=$(echo "$task_json" | jq -r '.blocks // [] | .[]' 2>/dev/null)
        while IFS= read -r dep; do
            [[ -n "$dep" ]] && depends_on+=("$dep")
        done <<< "$blocking_tasks"
    else
        # Get task from prd.json
        local task
        task=$(json_get_task "$prd" "$task_id")

        if [[ -z "$task" || "$task" == "null" ]]; then
            echo "{\"error\": \"task not found: $task_id\"}" >&2
            return 1
        fi

        description=$(echo "$task" | jq -r '.description // ""')
        local depends_on_str
        depends_on_str=$(echo "$task" | jq -r '.dependsOn // [] | .[]')
        while IFS= read -r dep; do
            [[ -n "$dep" ]] && depends_on+=("$dep")
        done <<< "$depends_on_str"
    fi

    # Check dependency completeness
    for dep in "${depends_on[@]}"; do
        local dep_status
        if [[ "$backend" == "beads" ]]; then
            dep_status=$(bd show "$dep" --json 2>/dev/null | jq -r '.status // "unknown"')
        else
            dep_status=$(json_get_task "$prd" "$dep" | jq -r '.status // "unknown"')
        fi

        if [[ "$dep_status" != "closed" ]]; then
            issues+=("Dependency '$dep' is not closed (status: $dep_status)")
        fi
    done

    # Check for file references in description
    # Look for patterns like [file: path/to/file] or @file:path/to/file or file paths in backticks
    if [[ -n "$description" ]]; then
        # Extract file references: [file: ...], @file:..., or `...` (code blocks)
        # Pattern 1: [file: /path/to/file]
        local file_refs
        file_refs=$(echo "$description" | grep -o '\[file:[^]]*\]' | sed 's/\[file:[[:space:]]*//;s/\][[:space:]]*$//' || true)

        while IFS= read -r file_ref; do
            if [[ -n "$file_ref" ]]; then
                # Expand ~ to home directory
                file_ref="${file_ref/#\~/$HOME}"
                # Skip relative paths starting with ./ or ../
                if [[ "$file_ref" == ./* ]] || [[ "$file_ref" == ../* ]]; then
                    # Relative paths are checked relative to project root
                    if [[ ! -e "$file_ref" ]]; then
                        issues+=("Referenced file not found: $file_ref")
                    fi
                elif [[ "$file_ref" == /* ]]; then
                    # Absolute paths
                    if [[ ! -e "$file_ref" ]]; then
                        issues+=("Referenced file not found: $file_ref")
                    fi
                fi
            fi
        done <<< "$file_refs"
    fi

    # Check external dependencies
    # These are always available in the environment where validation runs
    # but we can check critical ones
    if ! command -v jq &> /dev/null; then
        issues+=("Required dependency 'jq' is not installed or not in PATH")
    fi

    # Build result JSON
    local is_feasible="true"
    if [[ ${#issues[@]} -gt 0 ]]; then
        is_feasible="false"
    fi

    # Output result as JSON
    printf '{\n'
    printf '  "id": "%s",\n' "$task_id"
    printf '  "is_feasible": %s,\n' "$is_feasible"
    printf '  "issues": ['

    if [[ ${#issues[@]} -gt 0 ]]; then
        for i in "${!issues[@]}"; do
            if [[ $i -gt 0 ]]; then
                printf ', '
            fi
            printf '"%s"' "$(printf '%s\n' "${issues[$i]}" | sed 's/"/\\"/g')"
        done
    fi

    printf ']\n'
    printf '}\n'

    return 0
}

# Validate feasibility for all tasks in a project
# Returns JSON array with feasibility status for each task
# Optional parameter: prd_file (defaults to prd.json)
# Returns array of validation results:
# [
#   {"id": "task-1", "is_feasible": true, "issues": []},
#   {"id": "task-2", "is_feasible": false, "issues": ["Dependency 'dep-1' is not closed"]}
# ]
validate_all_tasks_feasibility() {
    local prd="${1:-prd.json}"

    if [[ "$(get_backend)" == "beads" ]]; then
        # Get all tasks from beads
        local tasks
        tasks=$(bd list --json 2>/dev/null) || return 1

        echo "["
        local first=true

        echo "$tasks" | jq -r '.[] | .id' | while read -r task_id; do
            if [[ "$first" != "true" ]]; then
                echo ","
            fi
            first=false

            validate_task_feasibility "$task_id" | tr '\n' ' '
        done

        echo ""
        echo "]"
    else
        # Get all tasks from prd.json
        if [[ ! -f "$prd" ]]; then
            echo "[]"
            return 0
        fi

        echo "["
        local first=true

        jq -r '.tasks[] | .id' "$prd" | while read -r task_id; do
            if [[ "$first" != "true" ]]; then
                echo ","
            fi
            first=false

            validate_task_feasibility "$task_id" "$prd" | tr '\n' ' '
        done

        echo ""
        echo "]"
    fi

    return 0
}

# Get summary of feasibility issues across all tasks
# Returns markdown-formatted list of infeasible tasks
# Usage: get_feasibility_summary [prd_file]
get_feasibility_summary() {
    local prd="${1:-prd.json}"

    local results
    results=$(validate_all_tasks_feasibility "$prd")

    local infeasible_count
    infeasible_count=$(echo "$results" | jq '[.[] | select(.is_feasible == false)] | length')

    if [[ "$infeasible_count" -eq 0 ]]; then
        echo "✓ All tasks are feasible"
        return 0
    fi

    echo "⚠ Found $infeasible_count infeasible task(s):"
    echo ""

    echo "$results" | jq -r '.[] | select(.is_feasible == false) | "**\(.id)**\n" + (.issues | map("  - \(.)") | join("\n"))' | while read -r line; do
        if [[ -n "$line" ]]; then
            echo "$line"
        fi
    done

    return 1
}

#
# ============================================================================
# DEPENDENCY GRAPH VALIDATION
# ============================================================================
#

# Validate dependencies for a single task
# Checks:
#   1. All dependencies exist and are valid task IDs
#   2. No circular dependencies
#   3. Correct dependency order (dependencies before dependents)
# Returns JSON: {"id": "task-id", "is_valid": true/false, "issues": ["issue1", "issue2"]}
# Usage: validate_task_dependencies <task_id> [prd_file]
validate_task_dependencies() {
    local task_id="$1"
    local prd="${2:-prd.json}"

    if [[ -z "$task_id" ]]; then
        echo '{"error": "task_id is required"}' >&2
        return 1
    fi

    local backend=$(get_backend)
    local issues=()
    local depends_on=()

    if [[ "$backend" == "beads" ]]; then
        # Get task from beads
        local task_json
        task_json=$(bd show "$task_id" --json 2>/dev/null) || {
            echo "{\"error\": \"task not found: $task_id\"}" >&2
            return 1
        }

        # Extract dependencies from blocks field
        local blocking_tasks
        blocking_tasks=$(echo "$task_json" | jq -r '.blocks // [] | .[]' 2>/dev/null)
        while IFS= read -r dep; do
            [[ -n "$dep" ]] && depends_on+=("$dep")
        done <<< "$blocking_tasks"
    else
        # Get task from prd.json
        if [[ ! -f "$prd" ]]; then
            echo "[]"
            return 0
        fi

        local task
        task=$(json_get_task "$prd" "$task_id")

        if [[ -z "$task" || "$task" == "null" ]]; then
            echo "{\"error\": \"task not found: $task_id\"}" >&2
            return 1
        fi

        # Extract dependencies
        local depends_on_str
        depends_on_str=$(echo "$task" | jq -r '.dependsOn // [] | .[]')
        while IFS= read -r dep; do
            [[ -n "$dep" ]] && depends_on+=("$dep")
        done <<< "$depends_on_str"
    fi

    # Get all task IDs for existence checking
    local all_task_ids
    if [[ "$backend" == "beads" ]]; then
        all_task_ids=$(bd list --json 2>/dev/null | jq -r '.[] | .id')
    else
        all_task_ids=$(jq -r '.tasks[].id' "$prd")
    fi

    # Check each dependency exists
    for dep in "${depends_on[@]}"; do
        if ! echo "$all_task_ids" | grep -q "^${dep}$"; then
            issues+=("Dependency '$dep' does not exist")
        fi
    done

    # Check for circular dependencies
    local cycle_found
    if [[ "$backend" == "beads" ]]; then
        # Use beads' built-in cycle detection
        if bd dep cycles 2>/dev/null | grep -q "cycle"; then
            issues+=("Circular dependency detected involving this task")
        fi
    else
        # Use DFS to detect cycles in JSON backend
        local cycles
        cycles=$(_detect_cycles_json "$prd" "$task_id")
        if [[ -n "$cycles" ]]; then
            issues+=("Circular dependency detected: $cycles")
        fi
    fi

    # Check dependency order (dependencies come before dependents in task list)
    if [[ "$backend" == "json" ]] && [[ -f "$prd" ]]; then
        local task_index
        task_index=$(jq --arg id "$task_id" '.tasks | to_entries | map(select(.value.id == $id)) | .[0].key' "$prd")

        for dep in "${depends_on[@]}"; do
            local dep_index
            dep_index=$(jq --arg id "$dep" '.tasks | to_entries | map(select(.value.id == $id)) | .[0].key' "$prd")

            if [[ -n "$dep_index" && -n "$task_index" ]] && [[ "$dep_index" -gt "$task_index" ]]; then
                issues+=("Dependency '$dep' appears after this task in the task list (order issue)")
            fi
        done
    fi

    # Build result JSON
    local is_valid="true"
    if [[ ${#issues[@]} -gt 0 ]]; then
        is_valid="false"
    fi

    # Output result as JSON
    printf '{\n'
    printf '  "id": "%s",\n' "$task_id"
    printf '  "is_valid": %s,\n' "$is_valid"
    printf '  "issues": ['

    if [[ ${#issues[@]} -gt 0 ]]; then
        for i in "${!issues[@]}"; do
            if [[ $i -gt 0 ]]; then
                printf ', '
            fi
            printf '"%s"' "$(printf '%s\n' "${issues[$i]}" | sed 's/"/\\"/g')"
        done
    fi

    printf ']\n'
    printf '}\n'

    return 0
}

# Validate dependencies for all tasks
# Returns JSON array with validation results for each task
# Usage: validate_all_dependencies [prd_file]
validate_all_dependencies() {
    local prd="${1:-prd.json}"

    if [[ "$(get_backend)" == "beads" ]]; then
        # Get all task IDs from beads
        echo "["
        local first=true

        bd list --json 2>/dev/null | jq -r '.[].id' | while read -r task_id; do
            if [[ "$first" != "true" ]]; then
                echo ","
            fi
            first=false

            validate_task_dependencies "$task_id" | tr '\n' ' '
        done

        echo ""
        echo "]"
    else
        # Get all tasks from prd.json
        if [[ ! -f "$prd" ]]; then
            echo "[]"
            return 0
        fi

        echo "["
        local first=true

        jq -r '.tasks[] | .id' "$prd" | while read -r task_id; do
            if [[ "$first" != "true" ]]; then
                echo ","
            fi
            first=false

            validate_task_dependencies "$task_id" "$prd" | tr '\n' ' '
        done

        echo ""
        echo "]"
    fi

    return 0
}

# Get dependency order (topological sort)
# Returns tasks in order such that all dependencies are satisfied
# Usage: get_dependency_order [prd_file]
get_dependency_order() {
    local prd="${1:-prd.json}"

    if [[ "$(get_backend)" == "beads" ]]; then
        # Use beads' built-in dependency ordering
        bd list --json 2>/dev/null | jq -r '.[].id'
    else
        # Topological sort for prd.json
        if [[ ! -f "$prd" ]]; then
            echo "[]"
            return 0
        fi

        # Use jq to perform topological sort
        # Strategy: repeatedly output tasks with no unresolved dependencies
        # Track completed within loop state to avoid infinite loop
        jq -r '
            .tasks as $tasks |
            ($tasks | map(.id)) as $all_ids |
            ($tasks | map(select(.status == "closed") | .id)) as $initially_completed |

            # Build a function to check if task has unresolved deps
            def has_unresolved($completed):
                (.dependsOn // []) | any(. as $dep | ($completed | contains([$dep])) | not);

            # Topological sort via iterative removal
            # Include completed in state so it gets updated each iteration
            {remaining: $tasks, ordered: [], completed: $initially_completed} |
            until(.remaining | length == 0;
                .completed as $done |
                ([.remaining[] | select((has_unresolved($done)) | not)]) as $ready_tasks |
                if ($ready_tasks | length) == 0 then
                    # No progress - remaining tasks have unresolvable deps (cycle or missing)
                    .remaining = []
                else
                    ($ready_tasks | map(.id)) as $ready_ids |
                    .ordered += $ready_ids |
                    .completed += $ready_ids |
                    .remaining = [.remaining[] | select(.id as $id | ($ready_ids | index($id)) == null)]
                end
            ) |
            .ordered
        ' "$prd"
    fi

    return 0
}

# Get detailed report on blocked tasks
# Shows which tasks are blocking which
# Usage: get_blocked_tasks_report [prd_file]
get_blocked_tasks_report() {
    local prd="${1:-prd.json}"

    if [[ "$(get_backend)" == "beads" ]]; then
        # Use beads' blocked command
        bd blocked 2>/dev/null || echo "No blocked tasks"
    else
        # Report for prd.json
        if [[ ! -f "$prd" ]]; then
            echo "No tasks found"
            return 0
        fi

        # Get all closed tasks
        local closed_tasks
        closed_tasks=$(jq -r '.tasks[] | select(.status == "closed") | .id' "$prd")

        # Find open tasks with unresolved dependencies
        echo "Blocked Tasks Report:"
        echo "===================="
        echo ""

        local has_blocked=false
        jq -r '.tasks[] | select(.status == "open") | .id' "$prd" | while read -r task_id; do
            local task
            task=$(json_get_task "$prd" "$task_id")

            local deps
            deps=$(echo "$task" | jq -r '.dependsOn // [] | .[]')

            # Find which deps are not closed
            local blocking_deps=()
            while IFS= read -r dep; do
                if [[ -n "$dep" ]] && ! echo "$closed_tasks" | grep -q "^${dep}$"; then
                    blocking_deps+=("$dep")
                fi
            done <<< "$deps"

            if [[ ${#blocking_deps[@]} -gt 0 ]]; then
                has_blocked=true
                echo "**$task_id** is blocked by:"
                for dep in "${blocking_deps[@]}"; do
                    local dep_status
                    dep_status=$(json_get_task "$prd" "$dep" | jq -r '.status // "unknown"')
                    echo "  - $dep (status: $dep_status)"
                done
                echo ""
            fi
        done

        if [[ "$has_blocked" == "false" ]]; then
            echo "No blocked tasks found."
            return 0
        fi
    fi

    return 0
}

# Internal helper: Detect cycles in JSON dependency graph using DFS
# Returns cycle path if found, empty otherwise
_detect_cycles_json() {
    local prd="$1"
    local task_id="$2"

    # Build the dependency graph and check for cycles
    # Uses proper jq recursive approach with immutable variable bindings
    jq --arg task "$task_id" '
        def has_cycle($graph; $visited; $rec_stack; $node):
            # jq variables are immutable - use proper recursive binding
            ($visited | .[$node] = true) as $new_visited |
            ($rec_stack | .[$node] = true) as $new_rec_stack |
            (($graph[$node] // []) | map(
                if $new_visited[.] == true then
                    if $new_rec_stack[.] == true then
                        {cycle: true, path: [$node, .]}
                    else
                        {cycle: false}
                    end
                else
                    has_cycle($graph; $new_visited; $new_rec_stack; .)
                end
            ) | map(select(.cycle == true)) | first // {cycle: false});

        # Build adjacency list
        (.tasks | map({id, deps: (.dependsOn // [])}) | map({(.id): .deps}) | add // {}) as $graph |

        # Check for cycles starting from given task
        has_cycle($graph; {}; {}; $task)
    ' "$prd" 2>/dev/null | jq -r 'select(.cycle == true) | .path | join(" -> ")'
}

# Get summary of all dependency issues
# Returns markdown-formatted report
# Usage: get_dependency_summary [prd_file]
get_dependency_summary() {
    local prd="${1:-prd.json}"

    local results
    results=$(validate_all_dependencies "$prd")

    local invalid_count
    invalid_count=$(echo "$results" | jq '[.[] | select(.is_valid == false)] | length')

    if [[ "$invalid_count" -eq 0 ]]; then
        echo "✓ All dependencies are valid"
        return 0
    fi

    echo "⚠ Found $invalid_count task(s) with dependency issues:"
    echo ""

    echo "$results" | jq -r '.[] | select(.is_valid == false) | "**\(.id)**\n" + (.issues | map("  - \(.)") | join("\n"))' | while read -r line; do
        if [[ -n "$line" ]]; then
            echo "$line"
        fi
    done

    echo ""
    echo "Blocked Tasks:"
    echo ""
    get_blocked_tasks_report "$prd"

    return 1
}

#
# ============================================================================
# ARCHITECTURE REVIEW
# ============================================================================
#

# Validate architectural alignment for a single task
# Uses AI (Sonnet) to review task against codebase patterns, conventions, and structure
# Checks:
#   1. Code location suggestions (where should implementation live)
#   2. Pattern consistency (follows existing conventions)
#   3. Naming conventions alignment
#   4. Integration points identification
# Returns JSON: {"id": "task-id", "is_aligned": true/false, "issues": ["issue1"], "suggestions": ["suggestion1"]}
# Usage: validate_task_architecture <task_id> [prd_file]
validate_task_architecture() {
    local task_id="$1"
    local prd="${2:-prd.json}"

    if [[ -z "$task_id" ]]; then
        echo '{"error": "task_id is required"}' >&2
        return 1
    fi

    # Source harness if not already loaded
    if ! command -v harness_invoke >/dev/null 2>&1; then
        local lib_dir
        lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        # shellcheck source=lib/harness.sh
        source "${lib_dir}/harness.sh"
    fi

    local backend=$(get_backend)
    local task_json=""
    local task_title=""
    local task_description=""
    local task_type=""
    local task_labels=""

    if [[ "$backend" == "beads" ]]; then
        # Get task from beads
        task_json=$(bd show "$task_id" --json 2>/dev/null) || {
            echo "{\"error\": \"task not found: $task_id\"}" >&2
            return 1
        }

        task_title=$(echo "$task_json" | jq -r '.title // ""')
        task_description=$(echo "$task_json" | jq -r '.description // ""')
        task_type=$(echo "$task_json" | jq -r '.type // "task"')
        task_labels=$(echo "$task_json" | jq -r '.labels // [] | join(", ")')
    else
        # Get task from prd.json
        if [[ ! -f "$prd" ]]; then
            echo '{"id": "'"$task_id"'", "is_aligned": true, "issues": [], "suggestions": []}'
            return 0
        fi

        task_json=$(json_get_task "$prd" "$task_id")

        if [[ -z "$task_json" || "$task_json" == "null" ]]; then
            echo "{\"error\": \"task not found: $task_id\"}" >&2
            return 1
        fi

        task_title=$(echo "$task_json" | jq -r '.title // ""')
        task_description=$(echo "$task_json" | jq -r '.description // ""')
        task_type=$(echo "$task_json" | jq -r '.type // "task"')
        task_labels=$(echo "$task_json" | jq -r '.labels // [] | join(", ")')
    fi

    # Build codebase context (file structure, patterns)
    local codebase_context=""

    # Get project structure
    if [[ -d "lib" ]]; then
        codebase_context+="Library modules:\n"
        codebase_context+="$(find lib -type f -name "*.sh" 2>/dev/null | head -20 | sed 's/^/  /')\n\n"
    fi

    if [[ -d "tests" ]]; then
        codebase_context+="Test files:\n"
        codebase_context+="$(find tests -type f -name "*.bats" 2>/dev/null | head -10 | sed 's/^/  /')\n\n"
    fi

    # Get existing function patterns from lib/tasks.sh if this is a tasks-related feature
    if echo "$task_description" | grep -qi "task\|validate\|plan\|review"; then
        if [[ -f "lib/tasks.sh" ]]; then
            codebase_context+="Existing validation patterns in lib/tasks.sh:\n"
            codebase_context+="$(grep -E "^(validate_|get_|_detect_)" lib/tasks.sh | head -15 | sed 's/^/  /')\n\n"
        fi
    fi

    # Build AI prompt for architecture review
    local system_prompt="You are an expert code reviewer analyzing architectural alignment for a bash project.
Your task is to review whether a planned task fits well with the existing codebase patterns and conventions.

Output ONLY valid JSON with this structure:
{
  \"is_aligned\": true or false,
  \"issues\": [\"issue1\", \"issue2\"],
  \"suggestions\": [\"suggestion1\", \"suggestion2\"]
}

Issues should identify architectural problems or pattern violations.
Suggestions should recommend where code should live and what patterns to follow."

    local task_prompt="Review this task for architectural consistency:

## Task
ID: ${task_id}
Title: ${task_title}
Type: ${task_type}
Labels: ${task_labels}

Description:
${task_description}

## Codebase Structure
${codebase_context}

## Analysis Criteria
1. Code Location: Where should implementation code live based on existing patterns?
2. Naming Conventions: Does task align with bash function naming (snake_case, prefixes)?
3. Module Organization: Which lib/*.sh file should contain the code?
4. Test Location: Where should tests be added?
5. Integration Points: How should this integrate with existing code?

Provide architectural review as JSON."

    # Invoke AI for architecture review (use sonnet for deeper analysis)
    local ai_response=""
    local original_model="${CUB_MODEL:-}"
    export CUB_MODEL="sonnet"

    ai_response=$(harness_invoke "$system_prompt" "$task_prompt" false 2>/dev/null) || {
        # If AI fails, return a basic response
        export CUB_MODEL="$original_model"
        echo '{"id": "'"$task_id"'", "is_aligned": true, "issues": ["AI review unavailable"], "suggestions": []}'
        return 0
    }

    export CUB_MODEL="$original_model"

    # Parse AI response and validate JSON
    local is_aligned="true"
    local issues_json="[]"
    local suggestions_json="[]"

    if echo "$ai_response" | jq -e '.' >/dev/null 2>&1; then
        # Extract fields (don't use -r for boolean or it becomes a string)
        local aligned_raw
        aligned_raw=$(echo "$ai_response" | jq '.is_aligned')
        if [[ "$aligned_raw" == "null" || -z "$aligned_raw" ]]; then
            is_aligned="true"
        else
            is_aligned="$aligned_raw"
        fi
        issues_json=$(echo "$ai_response" | jq -c '.issues // []')
        suggestions_json=$(echo "$ai_response" | jq -c '.suggestions // []')
    else
        # AI returned non-JSON, treat as suggestion
        is_aligned="true"
        suggestions_json='["AI review: '"$(echo "$ai_response" | head -1 | sed 's/"/\\"/g')"'"]'
    fi

    # Build result JSON
    printf '{\n'
    printf '  "id": "%s",\n' "$task_id"
    printf '  "is_aligned": %s,\n' "$is_aligned"
    printf '  "issues": %s,\n' "$issues_json"
    printf '  "suggestions": %s\n' "$suggestions_json"
    printf '}\n'

    return 0
}

# Validate architecture for all tasks
# Returns JSON array of architecture validation results
# Usage: validate_all_architecture [prd_file]
validate_all_architecture() {
    local prd="${1:-prd.json}"
    local backend=$(get_backend)
    local task_ids=()

    if [[ "$backend" == "beads" ]]; then
        # Get all task IDs from beads
        local ids_str
        ids_str=$(bd list --json 2>/dev/null | jq -r '.[].id')
        while IFS= read -r id; do
            [[ -n "$id" ]] && task_ids+=("$id")
        done <<< "$ids_str"
    else
        # Get all task IDs from prd.json
        if [[ ! -f "$prd" ]]; then
            echo "[]"
            return 0
        fi

        local ids_str
        ids_str=$(jq -r '.tasks[].id' "$prd")
        while IFS= read -r id; do
            [[ -n "$id" ]] && task_ids+=("$id")
        done <<< "$ids_str"
    fi

    # Validate each task
    local results="["
    local first=true

    for task_id in "${task_ids[@]}"; do
        if [[ "$first" == true ]]; then
            first=false
        else
            results+=","
        fi

        local result
        result=$(validate_task_architecture "$task_id" "$prd" | tr '\n' ' ')
        results+="$result"
    done

    results+="]"
    echo "$results"
}

# Get human-readable architecture review summary
# Returns markdown-formatted summary with pass/fail and suggestions
# Usage: get_architecture_summary [prd_file]
get_architecture_summary() {
    local prd="${1:-prd.json}"

    local results
    results=$(validate_all_architecture "$prd")

    # Count total, aligned, and issues
    local total
    local aligned
    local with_issues

    total=$(echo "$results" | jq '. | length')
    aligned=$(echo "$results" | jq '[.[] | select(.is_aligned == true)] | length')
    with_issues=$(echo "$results" | jq '[.[] | select(.issues | length > 0)] | length')

    echo "Architecture Review Summary"
    echo "==========================="
    echo ""
    echo "Total tasks: $total"
    echo "Architecturally aligned: $aligned"
    echo "Tasks with concerns: $with_issues"
    echo ""

    if [[ "$with_issues" -eq 0 ]]; then
        echo "✓ All tasks are architecturally aligned with the codebase."
        return 0
    fi

    echo "Tasks with architectural concerns:"
    echo ""

    # Show tasks with issues
    echo "$results" | jq -r '.[] | select(.issues | length > 0) | "**\(.id)**\nIssues:\n" + (.issues | map("  - \(.)") | join("\n")) + "\nSuggestions:\n" + (.suggestions | map("  - \(.)") | join("\n")) + "\n"' | while read -r line; do
        if [[ -n "$line" ]]; then
            echo "$line"
        fi
    done

    return 1
}

#!/usr/bin/env bash
#
# tasks.sh - Unified task management interface for curb
#
# Supports two backends:
#   1. beads (bd CLI) - preferred when available
#   2. prd.json - JSON file fallback
#
# Backend selection:
#   - CURB_BACKEND=beads|json  - explicit selection
#   - Auto-detect: uses beads if available and initialized, else json
#

# Include guard to prevent re-sourcing and resetting _TASK_BACKEND
if [[ -n "${_TASKS_SH_LOADED:-}" ]]; then
    return 0
fi
_TASKS_SH_LOADED=1

CURB_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source beads wrapper if available
if [[ -f "${CURB_LIB_DIR}/beads.sh" ]]; then
    source "${CURB_LIB_DIR}/beads.sh"
fi

# Backend state (set by detect_backend)
_TASK_BACKEND=""

# Detect which backend to use
detect_backend() {
    local project_dir="${1:-.}"

    # Check for explicit override
    if [[ -n "${CURB_BACKEND:-}" ]]; then
        case "$CURB_BACKEND" in
            beads|bd)
                if ! beads_available; then
                    echo "WARNING: CURB_BACKEND=beads but beads (bd) not installed, falling back to json" >&2
                    _TASK_BACKEND="json"
                elif ! beads_initialized "$project_dir"; then
                    echo "WARNING: CURB_BACKEND=beads but .beads/ not found in ${project_dir}. Run 'bd init' first, falling back to json" >&2
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
                echo "WARNING: Unknown CURB_BACKEND=$CURB_BACKEND, using auto-detect" >&2
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
get_remaining_count() {
    local prd="$1"

    if [[ "$(get_backend)" == "beads" ]]; then
        beads_get_remaining_count
    else
        json_get_remaining_count "$prd"
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

    jq '[.tasks[] | select(.status != "closed")] | length' "$prd"
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
    echo "  3. Run curb (will auto-detect beads): curb --status"
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

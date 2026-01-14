#!/usr/bin/env bash
#
# lib/dependencies.sh - Dependency detection engine for tasks
#
# Detects task dependencies from text content using multiple strategies:
# 1. Explicit patterns: "depends on X", "blocked by Y", "requires Z", "after A"
# 2. Numbered sequences: "1. Task A, 2. Task B" implying order
# 3. Contextual patterns: "then", "after that", "once", "when"
#
# Usage:
#   detect_dependencies_from_content "$content" "$known_tasks"
#   infer_blocking_relationships "$content"
#
# Returns: Space-separated list of task IDs or task names detected as dependencies
#

# Detect dependencies from arbitrary content
# Matches patterns like "depends on X", "blocked by Y", "requires A", "after B"
# Also detects numbered sequences implying execution order
#
# Usage: detect_dependencies_from_content "$content" "$known_tasks_array"
# Arguments:
#   $1: The text content to analyze
#   $2: Space-separated list of known task names/IDs (for matching)
# Output: Space-separated list of detected dependency identifiers
# Returns: 0 on success, 1 if no dependencies found
detect_dependencies_from_content() {
    local content="$1"
    local known_tasks="$2"

    if [[ -z "$content" ]]; then
        return 1
    fi

    local dependencies=""

    # Strategy 1: Explicit dependency patterns
    dependencies+=$(_extract_explicit_dependencies "$content" "$known_tasks")

    # Strategy 2: Numbered sequences implying order
    dependencies+=$(_extract_numbered_sequence_dependencies "$content" "$known_tasks")

    # Clean up duplicates and trim
    dependencies=$(echo "$dependencies" | tr ' ' '\n' | sort -u | tr '\n' ' ' | xargs)

    if [[ -n "$dependencies" ]]; then
        echo "$dependencies"
        return 0
    fi

    return 1
}

# Extract dependencies from explicit patterns
# Patterns: "depends on X", "blocked by Y", "requires Z", "after A"
# Case-insensitive matching
_extract_explicit_dependencies() {
    local content="$1"
    local known_tasks="$2"

    local text_lower
    text_lower=$(echo "$content" | tr '[:upper:]' '[:lower:]')

    local dependencies=""

    # Pattern 1: "depends on <task>"
    # Try to match against known tasks first for higher accuracy
    if [[ -n "$known_tasks" ]]; then
        for task in $known_tasks; do
            if echo "$text_lower" | grep -q "\bdepends\? on.*\b${task}\b"; then
                dependencies+=" $task"
            fi
        done
    fi
    # Fall back to pattern matching for unknown tasks
    if [[ -z "$dependencies" ]]; then
        local depends_matches
        depends_matches=$(echo "$text_lower" | grep -oE '\bdepends? on [a-zA-Z0-9_-]+' | sed 's/^depends* on //' | sed 's/^depend on //')
        if [[ -n "$depends_matches" ]]; then
            dependencies+=" $depends_matches"
        fi
    fi

    # Pattern 2: "blocked by <task>"
    local temp_deps=""
    if [[ -n "$known_tasks" ]]; then
        for task in $known_tasks; do
            if echo "$text_lower" | grep -q "\bblocked by.*\b${task}\b"; then
                temp_deps+=" $task"
            fi
        done
    fi
    if [[ -z "$temp_deps" ]]; then
        temp_deps=$(echo "$text_lower" | grep -oE '\bblocked by [a-zA-Z0-9_-]+' | sed 's/^blocked by //')
    fi
    if [[ -n "$temp_deps" ]]; then
        dependencies+=" $temp_deps"
    fi

    # Pattern 3: "requires <task>"
    temp_deps=""
    if [[ -n "$known_tasks" ]]; then
        for task in $known_tasks; do
            if echo "$text_lower" | grep -q "\brequires.*\b${task}\b"; then
                temp_deps+=" $task"
            fi
        done
    fi
    if [[ -z "$temp_deps" ]]; then
        temp_deps=$(echo "$text_lower" | grep -oE '\brequires [a-zA-Z0-9_-]+' | sed 's/^requires //')
    fi
    if [[ -n "$temp_deps" ]]; then
        dependencies+=" $temp_deps"
    fi

    # Pattern 4: "after <task>"
    temp_deps=""
    if [[ -n "$known_tasks" ]]; then
        for task in $known_tasks; do
            if echo "$text_lower" | grep -q "\bafter.*\b${task}\b"; then
                temp_deps+=" $task"
            fi
        done
    fi
    if [[ -z "$temp_deps" ]]; then
        temp_deps=$(echo "$text_lower" | grep -oE '\bafter [a-zA-Z0-9_-]+' | sed 's/^after //')
    fi
    if [[ -n "$temp_deps" ]]; then
        dependencies+=" $temp_deps"
    fi

    # Pattern 5: "once <task>"
    temp_deps=""
    if [[ -n "$known_tasks" ]]; then
        for task in $known_tasks; do
            if echo "$text_lower" | grep -q "\bonce.*\b${task}\b"; then
                temp_deps+=" $task"
            fi
        done
    fi
    if [[ -z "$temp_deps" ]]; then
        temp_deps=$(echo "$text_lower" | grep -oE '\bonce [a-zA-Z0-9_-]+' | sed 's/^once //')
    fi
    if [[ -n "$temp_deps" ]]; then
        dependencies+=" $temp_deps"
    fi

    # Pattern 6: "before <task>"
    temp_deps=""
    if [[ -n "$known_tasks" ]]; then
        for task in $known_tasks; do
            if echo "$text_lower" | grep -q "\bbefore.*\b${task}\b"; then
                temp_deps+=" $task"
            fi
        done
    fi
    if [[ -z "$temp_deps" ]]; then
        temp_deps=$(echo "$text_lower" | grep -oE '\bbefore [a-zA-Z0-9_-]+' | sed 's/^before //')
    fi
    if [[ -n "$temp_deps" ]]; then
        dependencies+=" $temp_deps"
    fi

    echo "$dependencies"
}

# Extract dependencies from numbered sequences
# Numbered lists often imply execution order: first must complete before second, etc.
# This extracts task names/IDs from sequences like:
#   1. Build API
#   2. Add tests (depends on 1)
#   3. Deploy (depends on 1, 2)
#
# For task N, returns all earlier tasks (N-1, N-2, etc.) as dependencies
_extract_numbered_sequence_dependencies() {
    local content="$1"
    local known_tasks="$2"

    # Extract numbered list items with task names
    # Pattern: "1. TaskName", "2. Task description", etc.
    # Since bash 3.2 doesn't support associative arrays, use indexed arrays
    # and track items sequentially

    local dependencies=""
    local item_count=0
    local items=""

    # Build list of numbered items
    while IFS= read -r line; do
        # Match pattern like "1. TaskName" or "1) TaskName"
        # Using simpler sed pattern to extract number
        local num
        num=$(echo "$line" | sed -n 's/^[[:space:]]*\([0-9][0-9]*\)[.)].*/\1/p')

        if [[ -n "$num" ]]; then
            item_count=$((item_count + 1))
            # Store item number for ordering
            items+="$num "
        fi
    done <<< "$content"

    # For each item after the first, all prior items are dependencies
    local idx=1
    for item_num in $items; do
        if (( idx > 1 )); then
            # Just use item numbers as dependencies (sequence-based)
            local prev_idx=1
            while (( prev_idx < idx )); do
                dependencies+="$prev_idx "
                prev_idx=$((prev_idx + 1))
            done
        fi
        idx=$((idx + 1))
    done

    echo "$dependencies" | xargs
}

# Infer blocking relationships from content
# Identifies which tasks block which other tasks based on dependency signals
# Returns structured format: "blocker_task->blocked_task"
#
# Usage: infer_blocking_relationships "$content" "$current_task_id"
# Output: Space-separated list of "task1->task2" relationships where task1 blocks task2
infer_blocking_relationships() {
    local content="$1"
    local current_task_id="${2:---}"

    local relationships=""

    # If current task depends on something, that something blocks current task
    # Pattern: task depends on X means X blocks task
    if [[ "$content" =~ [Dd]epends[[:space:]]+on[[:space:]]+([a-zA-Z0-9_-]+) ]]; then
        local dep="${BASH_REMATCH[1]}"
        relationships+="$dep->$current_task_id "
    fi

    # Pattern: task blocked by X
    if [[ "$content" =~ [Bb]locked[[:space:]]+by[[:space:]]+([a-zA-Z0-9_-]+) ]]; then
        local blocker="${BASH_REMATCH[1]}"
        relationships+="$blocker->$current_task_id "
    fi

    echo "$relationships" | xargs
}

# Check if content indicates a numbered sequence (task list with ordering)
# Returns 0 if numbered sequence detected, 1 otherwise
_has_numbered_sequence() {
    local content="$1"

    # Check for numbered list pattern: "1. ", "2. ", etc.
    if echo "$content" | grep -qE '^[[:space:]]*[0-9]+[.)][[:space:]]' ; then
        return 0
    fi

    return 1
}

# Check if content explicitly signals dependencies
# Returns 0 if dependency signals found, 1 otherwise
_has_dependency_signals() {
    local content="$1"
    local text_lower
    text_lower=$(echo "$content" | tr '[:upper:]' '[:lower:]')

    # Check for any explicit dependency keywords
    if [[ "$text_lower" =~ depends[[:space:]]*on ]] || \
       [[ "$text_lower" =~ blocked[[:space:]]*by ]] || \
       [[ "$text_lower" =~ require[ds] ]] || \
       [[ "$text_lower" =~ [[:space:]]after[[:space:]] ]] || \
       [[ "$text_lower" =~ [[:space:]]once[[:space:]] ]] || \
       [[ "$text_lower" =~ [[:space:]]before[[:space:]] ]]; then
        return 0
    fi

    return 1
}

# Get dependency description
# Describes the relationship in human-readable form
# Usage: get_dependency_description "task1" "task2"
# Output: "task1 blocks task2" or "task1 is required by task2"
get_dependency_description() {
    local source="$1"
    local target="$2"
    local pattern="${3:-blocks}"  # blocks, requires, precedes

    case "$pattern" in
        blocks)
            echo "$source blocks $target"
            ;;
        requires)
            echo "$target requires $source"
            ;;
        precedes)
            echo "$source must complete before $target"
            ;;
        depends_on)
            echo "$target depends on $source"
            ;;
        *)
            echo "$source -> $target"
            ;;
    esac
}

# Validate dependency references
# Checks if all detected dependencies are valid task identifiers
# Usage: validate_dependency_references "$dependency_list" "$known_tasks"
# Returns: 0 if all valid, 1 if any invalid
validate_dependency_references() {
    local dependencies="$1"
    local known_tasks="$2"

    if [[ -z "$dependencies" ]]; then
        return 0  # Empty list is valid
    fi

    # Check each dependency against known tasks
    for dep in $dependencies; do
        # Handle arrow syntax: "task-1->task-2" means both task-1 and task-2 should be valid
        local source_task
        local target_task
        if [[ "$dep" == *"->"* ]]; then
            # Use parameter expansion to split on ->
            source_task="${dep%%->*}"
            target_task="${dep##*->}"

            # Validate both parts
            if ! echo "$known_tasks" | grep -qw "$source_task"; then
                return 1
            fi
            if ! echo "$known_tasks" | grep -qw "$target_task"; then
                return 1
            fi
        else
            # Single task reference
            if ! echo "$known_tasks" | grep -qw "$dep"; then
                return 1  # Invalid dependency found
            fi
        fi
    done

    return 0
}

# Extract task names from content
# Finds potential task names/identifiers in content
# Useful for pattern matching when known_tasks not provided
# Usage: extract_task_names "$content"
# Output: Space-separated list of task-like identifiers found
extract_task_names() {
    local content="$1"

    # Match patterns like: task-1, task_name, TASK-123, etc.
    echo "$content" | grep -oE '[a-zA-Z0-9_-]{3,}' | sort -u | tr '\n' ' '
}


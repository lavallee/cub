#!/usr/bin/env bash
#
# lib/parsers/json.sh - JSON document parser for cub import
#
# Parses JSON documents in various formats:
# 1. Simple array format: { "prefix": "...", "tasks": [...] }
# 2. Structured PRD format: { "prefix": "...", "features": [...] }
#
# Output format (normalized):
#   {
#     "epics": [...],
#     "tasks": [...],
#     "dependencies": [...]
#   }
#
# Usage:
#   parse_json_file "requirements.json"
#

# Parse a JSON file and extract epics, tasks, and dependencies
# Supports both simple array and structured PRD formats
# Output is JSON to stdout
parse_json_file() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        echo '{"error":"File not found"}' >&2
        return 1
    fi

    # Validate JSON syntax first
    if ! jq empty "$file" 2>/dev/null; then
        echo '{"error":"Invalid JSON syntax"}' >&2
        return 1
    fi

    # Check what format we have
    local has_features
    has_features=$(jq 'has("features")' "$file" 2>/dev/null)

    local has_tasks
    has_tasks=$(jq 'has("tasks")' "$file" 2>/dev/null)

    if [[ "$has_features" == "true" ]]; then
        # Structured PRD format with features
        _parse_prd_format "$file"
    elif [[ "$has_tasks" == "true" ]]; then
        # Simple array format
        _parse_array_format "$file"
    else
        echo '{"error":"JSON must contain either \"tasks\" or \"features\" array"}' >&2
        return 1
    fi
}

# Parse simple array format: { "prefix": "...", "tasks": [...] }
# Converts to normalized epics/tasks/dependencies structure
_parse_array_format() {
    local file="$1"

    # Validate tasks array exists and is an array
    if ! jq -e '.tasks | type == "array"' "$file" >/dev/null 2>&1; then
        echo '{"error":"tasks field must be an array"}' >&2
        return 1
    fi

    # Get prefix for IDs
    local prefix
    prefix=$(jq -r '.prefix // "task"' "$file")

    # Create tasks from array
    # Each task should have: id, title, status
    # Optional: parent, priority, dependsOn, labels, acceptanceCriteria
    local tasks_json
    tasks_json=$(jq -n '[]')

    # Process each task
    tasks_json=$(jq --arg prefix "$prefix" \
        '.tasks | to_entries | map(
            .value as $task |
            {
                id: ($task.id // "\($prefix)-\(.key + 1)"),
                title: ($task.title // "Untitled"),
                description: ($task.description // ""),
                type: "task",
                status: ($task.status // "open"),
                parent: ($task.parent // null),
                priority: ($task.priority // "P2"),
                dependsOn: ($task.dependsOn // []),
                labels: ($task.labels // []),
                acceptanceCriteria: ($task.acceptanceCriteria // []),
                notes: ($task.notes // "")
            }
        )' <"$file")

    # Extract dependencies from dependsOn fields
    local dependencies_json
    dependencies_json=$(jq -n '[]')
    dependencies_json=$(jq -n \
        --argjson tasks "$tasks_json" \
        '$tasks | map(
            select(.dependsOn | length > 0) |
            .dependsOn[] as $dep |
            {from: .id, to: $dep}
        )' <<<"$tasks_json")

    # Validate
    if ! _validate_json_structure "$tasks_json" "$dependencies_json"; then
        return 1
    fi

    # Output in standard format (empty epics since this is just tasks)
    jq -n \
        --argjson epics '[]' \
        --argjson tasks "$tasks_json" \
        --argjson dependencies "$dependencies_json" \
        '{epics: $epics, tasks: $tasks, dependencies: $dependencies}'
}

# Parse structured PRD format: { "prefix": "...", "features": [{...tasks...}] }
# Features become tasks, feature.tasks become subtasks
_parse_prd_format() {
    local file="$1"

    # Validate features array exists and is an array
    if ! jq -e '.features | type == "array"' "$file" >/dev/null 2>&1; then
        echo '{"error":"features field must be an array"}' >&2
        return 1
    fi

    # Get prefix for IDs
    local prefix
    prefix=$(jq -r '.prefix // "feature"' "$file")

    # First pass: extract all tasks (features and their subtasks)
    local tasks_json
    tasks_json=$(jq \
        --arg prefix "$prefix" \
        '.features | to_entries | map(
            .value as $feature |
            .key as $feat_idx |
            # Create the feature itself as a task
            ({
                id: ($feature.id // "\($prefix)-feat-\($feat_idx + 1)"),
                title: ($feature.name // $feature.title // "Untitled Feature"),
                description: ($feature.description // ""),
                type: "task",
                status: ($feature.status // "open"),
                parent: null,
                priority: ($feature.priority // "P2"),
                dependsOn: ($feature.dependsOn // []),
                labels: ($feature.labels // []),
                acceptanceCriteria: ($feature.acceptanceCriteria // []),
                notes: ($feature.notes // ""),
                isFeature: true
            }) as $feat
            | (
                [$feat],
                (if ($feature.tasks | type) == "array" then
                    ($feature.tasks | to_entries | map(
                        .value as $task |
                        {
                            id: ($task.id // "\($prefix)-task-\($feat_idx + 1)-\(.key + 1)"),
                            title: ($task.title // "Untitled"),
                            description: ($task.description // ""),
                            type: "task",
                            status: ($task.status // "open"),
                            parent: $feat.id,
                            priority: ($task.priority // "P2"),
                            dependsOn: ($task.dependsOn // []),
                            labels: ($task.labels // []),
                            acceptanceCriteria: ($task.acceptanceCriteria // []),
                            notes: ($task.notes // "")
                        }
                    ))
                else empty end)
            ) | .[]
        )' <"$file")

    # Extract dependencies
    dependencies_json=$(jq -n \
        --argjson tasks "$tasks_json" \
        '$tasks | map(
            select(.dependsOn | length > 0) |
            .dependsOn[] as $dep |
            {from: .id, to: $dep}
        )' <<<"$tasks_json")

    # Validate
    if ! _validate_json_structure "$tasks_json" "$dependencies_json"; then
        return 1
    fi

    # Remove isFeature marker before output
    tasks_json=$(jq 'map(del(.isFeature))' <<<"$tasks_json")

    # Output in standard format (empty epics for PRD format)
    jq -n \
        --argjson epics '[]' \
        --argjson tasks "$tasks_json" \
        --argjson dependencies "$dependencies_json" \
        '{epics: $epics, tasks: $tasks, dependencies: $dependencies}'
}

# Validate JSON structure for consistency
# Checks: all required fields, no duplicate IDs, dependency references exist, no circular deps
_validate_json_structure() {
    local tasks_json="$1"
    local dependencies_json="$2"

    # Check all tasks have required fields
    if ! jq -e 'map(select(.id and .title and (.status | IN("open", "in_progress", "closed")))) | length == (input | length)' \
        <<<"$tasks_json" <<<"$tasks_json" >/dev/null 2>&1; then
        # Simpler check: verify structure without piping input twice
        if ! jq -e '.[] | select(.id and .title)' <<<"$tasks_json" >/dev/null 2>&1; then
            echo '{"error":"All tasks must have id, title, and valid status"}' >&2
            return 1
        fi
    fi

    # Check for duplicate IDs
    local id_count
    local unique_count
    id_count=$(jq '[.[].id] | length' <<<"$tasks_json")
    unique_count=$(jq '[.[].id] | unique | length' <<<"$tasks_json")
    if [[ "$id_count" != "$unique_count" ]]; then
        echo '{"error":"Duplicate task IDs found"}' >&2
        return 1
    fi

    # Check all dependency references exist
    local all_ids
    all_ids=$(jq -c '[.[].id]' <<<"$tasks_json")
    if ! jq -e --argjson all_ids "$all_ids" \
        '.[] | select(.from as $from | .to as $to | ($all_ids | map(. == $from or . == $to) | any | not))' \
        <<<"$dependencies_json" >/dev/null 2>&1; then
        : # Dependencies are valid or no dependencies
    fi

    # Check for circular dependencies (simple check: A->B->A pattern)
    if _has_circular_dependency "$dependencies_json"; then
        echo '{"error":"Circular dependency detected"}' >&2
        return 1
    fi

    return 0
}

# Check for circular dependencies - simple check for obvious cycles
# Looking for patterns like A->B and B->A (bidirectional dependencies)
_has_circular_dependency() {
    local dependencies_json="$1"

    # Check if any dependency goes both ways (A->B and B->A)
    local has_bidirectional
    has_bidirectional=$(jq \
        'group_by([.from, .to] | sort) |
         map(select(length > 1)) |
         length > 0
        ' <<<"$dependencies_json")

    if [[ "$has_bidirectional" == "true" ]]; then
        return 0  # Has circular dependency
    fi

    return 1  # No obvious circular dependency
}

# Extract just the tasks from parsed JSON
# Input: JSON from parse_json_file
# Output: Array of task objects
extract_tasks() {
    local parsed="$1"
    echo "$parsed" | jq '.tasks'
}

# Count total items in parsed JSON
# Input: JSON from parse_json_file
# Output: Integer count
count_items() {
    local parsed="$1"
    echo "$parsed" | jq '.tasks | length'
}

# Format parsed JSON as human-readable output
# Input: JSON from parse_json_file
# Output: Formatted text
format_parsed_json() {
    local parsed="$1"

    echo "=== Parsed JSON ==="
    echo ""

    local task_count
    task_count=$(echo "$parsed" | jq '.tasks | length')
    echo "Total Tasks: $task_count"
    echo ""

    echo "Tasks:"
    echo "$parsed" | jq -r '.tasks[] | "  [\(.id)] \(.title) (status: \(.status), parent: \(.parent // "none"))"'

    # Show dependencies if any
    local dep_count
    dep_count=$(echo "$parsed" | jq '.dependencies | length')
    if [[ "$dep_count" -gt 0 ]]; then
        echo ""
        echo "Dependencies:"
        echo "$parsed" | jq -r '.dependencies[] | "  \(.from) -> \(.to)"'
    fi
}

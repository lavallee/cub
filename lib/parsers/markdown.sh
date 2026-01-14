#!/usr/bin/env bash
#
# lib/parsers/markdown.sh - Markdown document parser for cub import
#
# Parses markdown documents and converts them into structured task format:
# - # headings -> epics
# - ## subheadings -> task groups (features)
# - - [ ] checkboxes -> individual tasks
# - - bullet points -> tasks or acceptance criteria
#
# Features:
# - Priority inference from content (title, description)
# - Supports explicit priority markers ([P0], [P1], etc.)
# - Detects priority from keywords: critical, blocker, high, low, optional, etc.
#
# Usage:
#   parse_markdown_file "requirements.md"
#
# Output: JSON with structure:
#   {
#     "epics": [...],
#     "tasks": [...],
#     "dependencies": [...]
#   }
#

# Source priority inference library
if [[ -f "$(dirname "${BASH_SOURCE[0]}")/../priority.sh" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/../priority.sh"
fi

# Source criteria extraction library
if [[ -f "$(dirname "${BASH_SOURCE[0]}")/criteria.sh" ]]; then
    source "$(dirname "${BASH_SOURCE[0]}")/criteria.sh"
fi

# Parse a markdown file and extract epics, tasks, and dependencies
# Output is JSON to stdout
parse_markdown_file() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        echo '{"error":"File not found"}' >&2
        return 1
    fi

    local current_epic=""
    local current_feature=""
    local current_task_id=""
    local task_counter=0
    local epic_counter=0
    local in_task=false

    # Temporary arrays (as JSON strings)
    local epics_json="[]"
    local tasks_json="[]"
    local dependencies_json="[]"
    local acceptance_criteria="[]"

    local line_number=0

    # Store normalized file path for source reference
    local source_file
    source_file=$(cd "$(dirname "$file")" && pwd)
    source_file="$source_file/$(basename "$file")"

    while IFS= read -r line || [[ -n "$line" ]]; do
        ((line_number++))

        # Skip empty lines
        if [[ -z "$line" ]]; then
            continue
        fi

        # Match H1 headings (epics): ^#
        if [[ "$line" =~ ^#[[:space:]] ]]; then
            # Extract title after "# "
            local epic_title="${line#\# }"

            # If we were building a task, finalize it with acceptance criteria
            if [[ "$in_task" == "true" && -n "$current_task_id" ]]; then
                tasks_json=$(finalize_task "$tasks_json" "$current_task_id" "$acceptance_criteria")
                acceptance_criteria="[]"
                in_task=false
            fi

            # Create epic with inferred priority
            ((epic_counter++))
            current_epic="epic-$epic_counter"
            local priority_epic
            priority_epic=$(infer_priority_from_title "$epic_title" 2>/dev/null || echo "P2")
            local epic_obj=$(jq -n \
                --arg id "$current_epic" \
                --arg title "$epic_title" \
                --arg file "$source_file" \
                --arg line "$line_number" \
                --arg priority "$priority_epic" \
                '{id: $id, title: $title, description: "", type: "epic", priority: $priority, source: {file: $file, line: ($line | tonumber)}}')
            epics_json=$(jq --argjson obj "$epic_obj" '. += [$obj]' <<<"$epics_json")
            current_feature=""

            continue
        fi

        # Match H2 headings (features/task groups): ^##
        if [[ "$line" =~ ^##[[:space:]] ]]; then
            # Extract title after "## "
            local feature_title="${line#\#\# }"

            # If we were building a task, finalize it
            if [[ "$in_task" == "true" && -n "$current_task_id" ]]; then
                tasks_json=$(finalize_task "$tasks_json" "$current_task_id" "$acceptance_criteria")
                acceptance_criteria="[]"
                in_task=false
            fi

            # Create feature (as a task) with inferred priority
            ((task_counter++))
            current_feature="$current_epic:$task_counter"
            local priority_feature
            priority_feature=$(infer_priority_from_title "$feature_title" 2>/dev/null || echo "P2")
            local feature_obj=$(jq -n \
                --arg id "$current_feature" \
                --arg title "$feature_title" \
                --arg epic "$current_epic" \
                --arg file "$source_file" \
                --arg line "$line_number" \
                --arg priority "$priority_feature" \
                '{id: $id, title: $title, description: "", type: "task", parent: $epic, priority: $priority, source: {file: $file, line: ($line | tonumber)}}')
            tasks_json=$(jq --argjson obj "$feature_obj" '. += [$obj]' <<<"$tasks_json")

            continue
        fi

        # Match checkbox items (tasks): ^- [ ] or ^- [x] or ^- [X]
        if [[ "$line" =~ ^-[[:space:]]*\[[[:space:]]*[xX]?[[:space:]]*\][[:space:]]+ ]]; then
            # Extract title after checkbox
            # Find where the checkbox ends
            local checkbox_match="${line%%\]*}"
            checkbox_match="${checkbox_match##*\[}"
            local task_title="${line#*\] }"
            task_title="${task_title#[\[:space:]]}"

            # Finalize previous task if there was one
            if [[ "$in_task" == "true" && -n "$current_task_id" ]]; then
                tasks_json=$(finalize_task "$tasks_json" "$current_task_id" "$acceptance_criteria")
                acceptance_criteria="[]"
            fi

            # Create new task with inferred priority
            ((task_counter++))
            current_task_id="$current_epic:$task_counter"
            in_task=true

            local priority_task
            priority_task=$(infer_priority_from_title "$task_title" 2>/dev/null || echo "P2")
            local task_obj=$(jq -n \
                --arg id "$current_task_id" \
                --arg title "$task_title" \
                --arg parent "$current_feature" \
                --arg epic "$current_epic" \
                --arg file "$source_file" \
                --arg line "$line_number" \
                --arg priority "$priority_task" \
                '{id: $id, title: $title, description: "", type: "task", parent: $parent, epic: $epic, priority: $priority, acceptanceCriteria: [], source: {file: $file, line: ($line | tonumber)}}')
            tasks_json=$(jq --argjson obj "$task_obj" '. += [$obj]' <<<"$tasks_json")

            continue
        fi

        # Match section headers for acceptance criteria (### Acceptance criteria:, ### Done when:)
        # These appear within task description areas
        if [[ "$line" =~ ^###[[:space:]]+(Acceptance[[:space:]]+[Cc]riteria|[Dd]one[[:space:]]+[Ww]hen) ]]; then
            # When we encounter a section header, switch to section mode
            # The next bullets will be parsed as section criteria
            if [[ "$in_task" == "true" ]]; then
                # Extract section name from the line
                local section_type="${line#\#\#\# }"
                # Mark that we're in a criteria section
                # (inline criteria collection will continue until next section)
            fi
            continue
        fi

        # Match bullet points (potential acceptance criteria or subtasks): ^-
        # But not checkboxes (those are handled above)
        if [[ "$line" =~ ^-[[:space:]]+ ]] && [[ ! "$line" =~ ^-[[:space:]]*\\\[ ]]; then
            # Extract bullet text
            local bullet_text="${line#- }"

            # If we're in a task, treat this as acceptance criteria
            if [[ "$in_task" == "true" ]]; then
                acceptance_criteria=$(jq --arg text "$bullet_text" '. += [$text]' <<<"$acceptance_criteria")
            fi

            continue
        fi

        # Match numbered items (1. 2. 3. etc.) as acceptance criteria in task context
        if [[ "$line" =~ ^[[:space:]]*[0-9]+\.[[:space:]]+ ]]; then
            local criterion="${line#*. }"
            criterion="${criterion#[[:space:]]}"

            # If we're in a task, treat this as acceptance criteria
            if [[ "$in_task" == "true" ]]; then
                acceptance_criteria=$(jq --arg text "$criterion" '. += [$text]' <<<"$acceptance_criteria")
            fi

            continue
        fi
    done <"$file"

    # Finalize any remaining task
    if [[ "$in_task" == "true" && -n "$current_task_id" ]]; then
        tasks_json=$(finalize_task "$tasks_json" "$current_task_id" "$acceptance_criteria")
    fi

    # Combine into output JSON
    jq -n \
        --argjson epics "$epics_json" \
        --argjson tasks "$tasks_json" \
        --argjson dependencies "$dependencies_json" \
        '{epics: $epics, tasks: $tasks, dependencies: $dependencies}'
}

# Helper function to finalize a task by adding acceptance criteria
# Takes task_json (array), task_id, and acceptance_criteria (array)
# Returns updated task_json
finalize_task() {
    local tasks_json="$1"
    local task_id="$2"
    local acceptance_criteria="$3"

    jq --arg id "$task_id" \
        --argjson criteria "$acceptance_criteria" \
        '(.[] | select(.id == $id) | .acceptanceCriteria) |= $criteria' \
        <<<"$tasks_json"
}

# Extract just the epics from parsed markdown
# Input: JSON from parse_markdown_file
# Output: Array of epic objects
extract_epics() {
    local parsed="$1"
    echo "$parsed" | jq '.epics'
}

# Extract just the tasks from parsed markdown
# Input: JSON from parse_markdown_file
# Output: Array of task objects
extract_tasks() {
    local parsed="$1"
    echo "$parsed" | jq '.tasks'
}

# Count total items (epics + tasks)
# Input: JSON from parse_markdown_file
count_items() {
    local parsed="$1"
    local epic_count
    local task_count

    epic_count=$(echo "$parsed" | jq '.epics | length')
    task_count=$(echo "$parsed" | jq '.tasks | length')

    echo "$((epic_count + task_count))"
}

# Format parsed markdown as human-readable output
# Input: JSON from parse_markdown_file
# Output: Formatted text
format_parsed_markdown() {
    local parsed="$1"

    echo "=== Parsed Markdown ==="
    echo ""

    # Show epics
    echo "Epics:"
    echo "$parsed" | jq -r '.epics[] | "  [\(.id)] \(.title)"'

    echo ""
    echo "Tasks:"
    echo "$parsed" | jq -r '.tasks[] | "  [\(.id)] \(.title) (parent: \(.parent // "none"))"'

    echo ""
    echo "Acceptance Criteria:"
    echo "$parsed" | jq -r '.tasks[] | select(.acceptanceCriteria | length > 0) | "  Task \(.id):\n    \(.acceptanceCriteria | .[] | "- \(.)")"'
}

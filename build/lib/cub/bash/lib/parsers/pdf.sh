#!/usr/bin/env bash
#
# lib/parsers/pdf.sh - PDF document parser for cub import
#
# Parses PDF documents using pdftotext, then processes the extracted text
# as markdown-like content to create structured tasks.
#
# Features:
# - Converts PDF to text using pdftotext
# - Parses extracted text similar to markdown format
# - Preserves section structure and hierarchy
# - Priority inference from content
#
# Usage:
#   parse_pdf_file "document.pdf"
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

# Check if pdftotext is available
_check_pdftotext() {
    if ! command -v pdftotext &>/dev/null; then
        echo '{"error":"pdftotext not found. Please install poppler-utils."}' >&2
        return 1
    fi
    return 0
}

# Extract text from PDF and convert to markdown-like format
# Attempts to preserve section structure using heuristics
_pdf_to_markdown() {
    local pdf_file="$1"
    local temp_txt

    # Create temporary text file
    temp_txt=$(mktemp)
    trap "rm -f '$temp_txt'" EXIT

    # Use pdftotext with layout preservation for better structure
    if ! pdftotext -layout "$pdf_file" "$temp_txt" 2>/dev/null; then
        echo '{"error":"Failed to extract text from PDF"}' >&2
        rm -f "$temp_txt"
        return 1
    fi

    # Process the extracted text to convert to markdown-like format
    # Look for section patterns and convert to heading format
    local line_number=0
    local current_section=""
    local current_level=0

    while IFS= read -r line || [[ -n "$line" ]]; do
        ((line_number++))

        # Skip completely empty lines at the start
        [[ -z "$line" ]] && continue

        # Detect potential section headers
        # Look for lines that appear to be section titles:
        # - All caps with length 3-100 chars
        # - Numbered sections (1. 2. etc.)
        # - Standard capitalizations that span line width

        # All-caps section detection (e.g., "SECTION TITLE")
        if [[ "$line" =~ ^[[:space:]]*[A-Z][A-Z0-9\ \(\)\&\-]+[A-Z0-9]?[[:space:]]*$ ]] && \
           [[ ${#line} -gt 5 ]] && [[ ${#line} -lt 100 ]]; then
            # Remove leading/trailing whitespace
            local title="${line#[[:space:]]*}"
            title="${title%[[:space:]]*}"

            # Check if it's not just a short acronym (too short probably not a title)
            if [[ ${#title} -gt 3 ]]; then
                # Output as markdown h1
                echo "# $title"
                continue
            fi
        fi

        # Numbered section detection (e.g., "1. Introduction", "2.1 Background")
        if [[ "$line" =~ ^[0-9]+(\.[0-9]+)?[[:space:]]+[A-Z] ]]; then
            # Extract just the heading part
            local heading="${line#[0-9]*\. }"
            heading="${heading#[0-9]*\.[0-9]* }"

            # Only treat as heading if the number starts at beginning and is followed by text
            if [[ "$line" =~ ^[0-9]+(\.[0-9]+)?[[:space:]]+[A-Z] ]]; then
                echo "# $heading"
                continue
            fi
        fi

        # If line starts with multiple spaces, it might be a subsection or important item
        # Convert to bullet point for processing by markdown parser
        if [[ "$line" =~ ^[[:space:]][[:space:]][[:space:]][[:space:]] ]]; then
            # Preserve indentation as part of structure
            echo "  - ${line#[[:space:]]*}"
            continue
        fi

        # Regular lines - output as-is for markdown parser to handle
        echo "$line"
    done < "$temp_txt"

    rm -f "$temp_txt"
}

# Parse a PDF file and extract epics, tasks, and dependencies
# Output is JSON to stdout
parse_pdf_file() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        echo '{"error":"File not found"}' >&2
        return 1
    fi

    # Check if pdftotext is available
    if ! _check_pdftotext; then
        return 1
    fi

    # Convert PDF to markdown format
    local markdown_content
    markdown_content=$(_pdf_to_markdown "$file")

    if [[ $? -ne 0 ]]; then
        echo '{"error":"Failed to convert PDF to text"}' >&2
        return 1
    fi

    # Write markdown to temporary file
    local temp_md
    temp_md=$(mktemp)
    trap "rm -f '$temp_md'" EXIT

    echo "$markdown_content" > "$temp_md"

    # Store normalized file path for source reference
    local source_file
    source_file=$(cd "$(dirname "$file")" && pwd)
    source_file="$source_file/$(basename "$file")"

    # Now parse the markdown content similar to markdown parser
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

        # Match bullet points (potential acceptance criteria or subtasks): ^-
        # But not checkboxes (those are handled below)
        if [[ "$line" =~ ^-[[:space:]]+ ]] && [[ ! "$line" =~ ^-[[:space:]]*\\\[ ]]; then
            # Extract bullet text
            local bullet_text="${line#- }"

            # If we don't have a current epic, treat this as a task
            if [[ -z "$current_epic" ]]; then
                # Finalize previous task if there was one
                if [[ "$in_task" == "true" && -n "$current_task_id" ]]; then
                    tasks_json=$(finalize_task "$tasks_json" "$current_task_id" "$acceptance_criteria")
                    acceptance_criteria="[]"
                fi

                # Create new task with inferred priority
                ((task_counter++))
                current_task_id="task-$task_counter"
                in_task=true

                local priority_task
                priority_task=$(infer_priority_from_title "$bullet_text" 2>/dev/null || echo "P2")
                local task_obj=$(jq -n \
                    --arg id "$current_task_id" \
                    --arg title "$bullet_text" \
                    --arg file "$source_file" \
                    --arg line "$line_number" \
                    --arg priority "$priority_task" \
                    '{id: $id, title: $title, description: "", type: "task", priority: $priority, acceptanceCriteria: [], source: {file: $file, line: ($line | tonumber)}}')
                tasks_json=$(jq --argjson obj "$task_obj" '. += [$obj]' <<<"$tasks_json")
            elif [[ "$in_task" == "true" ]]; then
                # If we're in a task, treat this as acceptance criteria
                acceptance_criteria=$(jq --arg text "$bullet_text" '. += [$text]' <<<"$acceptance_criteria")
            fi

            continue
        fi

        # Match numbered items (1. 2. 3. etc.) as task items
        if [[ "$line" =~ ^[[:space:]]*[0-9]+\.[[:space:]]+ ]]; then
            local item="${line#*. }"
            item="${item#[[:space:]]}"

            # If we're in a task, treat this as acceptance criteria
            if [[ "$in_task" == "true" ]]; then
                acceptance_criteria=$(jq --arg text "$item" '. += [$text]' <<<"$acceptance_criteria")
            fi

            continue
        fi
    done <"$temp_md"

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

    rm -f "$temp_md"
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

# Extract just the epics from parsed PDF
# Input: JSON from parse_pdf_file
# Output: Array of epic objects
extract_epics() {
    local parsed="$1"
    echo "$parsed" | jq '.epics'
}

# Extract just the tasks from parsed PDF
# Input: JSON from parse_pdf_file
# Output: Array of task objects
extract_tasks() {
    local parsed="$1"
    echo "$parsed" | jq '.tasks'
}

# Count total items (epics + tasks)
# Input: JSON from parse_pdf_file
count_items() {
    local parsed="$1"
    local epic_count
    local task_count

    epic_count=$(echo "$parsed" | jq '.epics | length')
    task_count=$(echo "$parsed" | jq '.tasks | length')

    echo "$((epic_count + task_count))"
}

# Format parsed PDF as human-readable output
# Input: JSON from parse_pdf_file
# Output: Formatted text
format_parsed_pdf() {
    local parsed="$1"

    echo "=== Parsed PDF ===" >&2
    echo "" >&2

    # Show epics
    echo "Epics:" >&2
    echo "$parsed" | jq -r '.epics[] | "  [\(.id)] \(.title)"' >&2

    echo "" >&2
    echo "Tasks:" >&2
    echo "$parsed" | jq -r '.tasks[] | "  [\(.id)] \(.title) (parent: \(.parent // "none"))"' >&2

    echo "" >&2
    echo "Acceptance Criteria:" >&2
    echo "$parsed" | jq -r '.tasks[] | select(.acceptanceCriteria | length > 0) | "  Task \(.id):\n    \(.acceptanceCriteria | .[] | "- \(.)")"' >&2
}

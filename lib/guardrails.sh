#!/usr/bin/env bash
#
# guardrails.sh - Institutional Memory / Guardrails System
#
# Provides persistent guardrails that accumulate project-specific lessons
# learned across sessions. Guardrails are curated, human-readable guidance
# that gets injected into task prompts to prevent repeat mistakes.
#
# File Location: .cub/guardrails.md
#
# Usage:
#   guardrails_init               # Create guardrails file if not exists
#   guardrails_exists             # Check if guardrails file exists
#   guardrails_read               # Read guardrails content
#   guardrails_add "lesson"       # Add a lesson
#   guardrails_add_from_failure   # Add lesson from failure context
#   guardrails_size_kb            # Get file size in KB
#   guardrails_count              # Count number of lessons
#   guardrails_clear              # Clear all lessons (with backup)
#

# Include guard
if [[ -n "${_CUB_GUARDRAILS_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_GUARDRAILS_SH_LOADED=1

# Default guardrails file path
_GUARDRAILS_FILE=".cub/guardrails.md"

# Default max size in KB before warning (50KB)
_GUARDRAILS_MAX_SIZE_KB=50

# Get the guardrails file path for a project
# Usage: _guardrails_get_file [project_dir]
_guardrails_get_file() {
    local project_dir="${1:-${PROJECT_DIR:-.}}"
    echo "${project_dir}/${_GUARDRAILS_FILE}"
}

# Check if guardrails file exists
# Usage: guardrails_exists [project_dir]
# Returns: 0 if exists, 1 if not
guardrails_exists() {
    local project_dir="${1:-${PROJECT_DIR:-.}}"
    local file
    file=$(_guardrails_get_file "$project_dir")
    [[ -f "$file" ]]
}

# Initialize guardrails file if it doesn't exist
# Creates the .cub directory if needed
# Usage: guardrails_init [project_dir]
# Returns: 0 on success, 1 on error
guardrails_init() {
    local project_dir="${1:-${PROJECT_DIR:-.}}"
    local file
    file=$(_guardrails_get_file "$project_dir")

    # Ensure .cub directory exists
    local cub_dir="${project_dir}/.cub"
    if [[ ! -d "$cub_dir" ]]; then
        mkdir -p "$cub_dir" || {
            echo "ERROR: Failed to create .cub directory" >&2
            return 1
        }
    fi

    # Create file if it doesn't exist
    if [[ ! -f "$file" ]]; then
        cat > "$file" <<'EOF'
# Guardrails

Institutional memory for this project. These lessons learned are automatically
included in task prompts to prevent repeat mistakes.

---

## Project-Specific

<!-- Add project-specific guidance here -->
<!-- Examples: build commands, required environment setup, naming conventions -->

---

## Learned from Failures

<!-- Lessons automatically captured from task failures will appear below -->

EOF
    fi

    return 0
}

# Read guardrails content
# Usage: guardrails_read [project_dir]
# Returns: Guardrails file content, or empty string if file doesn't exist
guardrails_read() {
    local project_dir="${1:-${PROJECT_DIR:-.}}"
    local file
    file=$(_guardrails_get_file "$project_dir")

    if [[ -f "$file" ]]; then
        cat "$file"
    fi
}

# Add a lesson to guardrails file
# Appends to the "Learned from Failures" section
# Usage: guardrails_add <lesson> [task_id] [project_dir]
# Parameters:
#   lesson - The lesson text to add
#   task_id - Optional task ID to link the lesson to
#   project_dir - Optional project directory
# Returns: 0 on success, 1 on error
guardrails_add() {
    local lesson="$1"
    local task_id="${2:-}"
    local project_dir="${3:-${PROJECT_DIR:-.}}"

    # Validate lesson
    if [[ -z "$lesson" ]]; then
        echo "ERROR: lesson text is required" >&2
        return 1
    fi

    # Ensure file exists
    guardrails_init "$project_dir" || return 1

    local file
    file=$(_guardrails_get_file "$project_dir")

    # Format the lesson entry
    local timestamp
    timestamp=$(date '+%Y-%m-%d')
    local entry=""

    if [[ -n "$task_id" ]]; then
        entry="### ${timestamp} - ${task_id}
${lesson}
"
    else
        entry="### ${timestamp}
${lesson}
"
    fi

    # Append to file
    echo "" >> "$file"
    echo "$entry" >> "$file"

    return 0
}

# Add a lesson from failure context
# Extracts error information and formats it as a lesson
# Usage: guardrails_add_from_failure <task_id> <exit_code> <error_summary> [lesson] [project_dir]
# Parameters:
#   task_id - The task ID that failed
#   exit_code - The exit code from the failure
#   error_summary - Summary of what went wrong
#   lesson - Optional actionable lesson (if not provided, uses error_summary)
#   project_dir - Optional project directory
# Returns: 0 on success, 1 on error
guardrails_add_from_failure() {
    local task_id="$1"
    local exit_code="$2"
    local error_summary="$3"
    local lesson="${4:-}"
    local project_dir="${5:-${PROJECT_DIR:-.}}"

    # Validate required parameters
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    if [[ -z "$exit_code" ]]; then
        echo "ERROR: exit_code is required" >&2
        return 1
    fi

    if [[ -z "$error_summary" ]]; then
        echo "ERROR: error_summary is required" >&2
        return 1
    fi

    # Use error_summary as lesson if none provided
    if [[ -z "$lesson" ]]; then
        lesson="$error_summary"
    fi

    # Format the failure entry
    local entry="**Error:** ${error_summary}
**Exit code:** ${exit_code}
**Lesson:** ${lesson}"

    # Add the entry
    guardrails_add "$entry" "$task_id" "$project_dir"
}

# Get guardrails file size in KB
# Usage: guardrails_size_kb [project_dir]
# Returns: File size in KB (integer), or 0 if file doesn't exist
guardrails_size_kb() {
    local project_dir="${1:-${PROJECT_DIR:-.}}"
    local file
    file=$(_guardrails_get_file "$project_dir")

    if [[ ! -f "$file" ]]; then
        echo "0"
        return 0
    fi

    # Get file size in bytes and convert to KB
    local bytes
    if [[ "$(uname)" == "Darwin" ]]; then
        bytes=$(stat -f %z "$file" 2>/dev/null || echo "0")
    else
        bytes=$(stat -c %s "$file" 2>/dev/null || echo "0")
    fi

    # Convert to KB (rounded up)
    local kb=$(( (bytes + 1023) / 1024 ))
    echo "$kb"
}

# Count number of lessons in guardrails file
# Counts sections that start with "### " (lesson headers)
# Usage: guardrails_count [project_dir]
# Returns: Number of lessons, or 0 if file doesn't exist
guardrails_count() {
    local project_dir="${1:-${PROJECT_DIR:-.}}"
    local file
    file=$(_guardrails_get_file "$project_dir")

    if [[ ! -f "$file" ]]; then
        echo "0"
        return 0
    fi

    # Count lines starting with "### " followed by a date pattern
    local count
    count=$(grep -c "^### [0-9]" "$file" 2>/dev/null || echo "0")
    echo "$count"
}

# Check if guardrails file exceeds max size
# Usage: guardrails_check_size [max_size_kb] [project_dir]
# Parameters:
#   max_size_kb - Maximum size in KB (default: 50)
#   project_dir - Optional project directory
# Returns: 0 if under limit, 1 if over limit
guardrails_check_size() {
    local max_size_kb="${1:-${_GUARDRAILS_MAX_SIZE_KB}}"
    local project_dir="${2:-${PROJECT_DIR:-.}}"

    local current_size
    current_size=$(guardrails_size_kb "$project_dir")

    if [[ "$current_size" -gt "$max_size_kb" ]]; then
        return 1
    fi

    return 0
}

# Clear all lessons from guardrails file
# Creates a backup before clearing
# Usage: guardrails_clear [project_dir]
# Returns: 0 on success, 1 on error
guardrails_clear() {
    local project_dir="${1:-${PROJECT_DIR:-.}}"
    local file
    file=$(_guardrails_get_file "$project_dir")

    if [[ ! -f "$file" ]]; then
        return 0
    fi

    # Create backup
    local backup_file="${file}.backup.$(date '+%Y%m%d-%H%M%S')"
    cp "$file" "$backup_file" || {
        echo "ERROR: Failed to create backup" >&2
        return 1
    }

    # Reinitialize with empty content
    rm "$file"
    guardrails_init "$project_dir"

    return 0
}

# Import guardrails from another file
# Usage: guardrails_import <source_file> [project_dir]
# Parameters:
#   source_file - Path to source guardrails file
#   project_dir - Optional project directory
# Returns: 0 on success, 1 on error
guardrails_import() {
    local source_file="$1"
    local project_dir="${2:-${PROJECT_DIR:-.}}"

    # Validate source file
    if [[ -z "$source_file" ]]; then
        echo "ERROR: source_file is required" >&2
        return 1
    fi

    if [[ ! -f "$source_file" ]]; then
        echo "ERROR: Source file does not exist: $source_file" >&2
        return 1
    fi

    # Ensure destination exists
    guardrails_init "$project_dir" || return 1

    local dest_file
    dest_file=$(_guardrails_get_file "$project_dir")

    # Extract lessons from source (everything after "## Learned from Failures")
    local lessons=""
    local in_lessons=false

    while IFS= read -r line; do
        if [[ "$line" == "## Learned from Failures"* ]]; then
            in_lessons=true
            continue
        fi
        if [[ "$in_lessons" == "true" ]]; then
            lessons+="${line}"$'\n'
        fi
    done < "$source_file"

    # Append lessons to destination if any were found
    if [[ -n "$lessons" && "$lessons" != $'\n' ]]; then
        echo "" >> "$dest_file"
        echo "<!-- Imported from: $source_file on $(date '+%Y-%m-%d') -->" >> "$dest_file"
        echo "$lessons" >> "$dest_file"
    fi

    return 0
}

# Export guardrails to a specified file
# Usage: guardrails_export <dest_file> [project_dir]
# Parameters:
#   dest_file - Path to destination file
#   project_dir - Optional project directory
# Returns: 0 on success, 1 on error
guardrails_export() {
    local dest_file="$1"
    local project_dir="${2:-${PROJECT_DIR:-.}}"

    # Validate destination
    if [[ -z "$dest_file" ]]; then
        echo "ERROR: dest_file is required" >&2
        return 1
    fi

    local source_file
    source_file=$(_guardrails_get_file "$project_dir")

    if [[ ! -f "$source_file" ]]; then
        echo "ERROR: No guardrails file to export" >&2
        return 1
    fi

    # Copy the file
    cp "$source_file" "$dest_file" || {
        echo "ERROR: Failed to export guardrails" >&2
        return 1
    }

    return 0
}

# Get guardrails formatted for prompt injection
# Returns the content suitable for including in a task prompt
# Usage: guardrails_for_prompt [project_dir]
# Returns: Formatted guardrails content, or empty if disabled/empty
guardrails_for_prompt() {
    local project_dir="${1:-${PROJECT_DIR:-.}}"

    if ! guardrails_exists "$project_dir"; then
        return 0
    fi

    local content
    content=$(guardrails_read "$project_dir")

    # Return empty if no content
    if [[ -z "$content" ]]; then
        return 0
    fi

    # Return formatted for prompt
    echo "# Guardrails (Institutional Memory)"
    echo ""
    echo "The following are lessons learned from previous sessions in this project."
    echo "Follow this guidance to avoid repeating past mistakes."
    echo ""
    echo "$content"
}

# Get the file path (for external use)
# Usage: guardrails_get_file [project_dir]
guardrails_get_file() {
    _guardrails_get_file "$@"
}

# Search guardrails for a pattern
# Usage: guardrails_search <pattern> [project_dir]
# Returns: Matching lines
guardrails_search() {
    local pattern="$1"
    local project_dir="${2:-${PROJECT_DIR:-.}}"

    if [[ -z "$pattern" ]]; then
        echo "ERROR: pattern is required" >&2
        return 1
    fi

    local file
    file=$(_guardrails_get_file "$project_dir")

    if [[ ! -f "$file" ]]; then
        return 0
    fi

    grep -i "$pattern" "$file" 2>/dev/null || true
}

# List all lessons as JSON
# Usage: guardrails_list_json [project_dir]
# Returns: JSON array of lessons
guardrails_list_json() {
    local project_dir="${1:-${PROJECT_DIR:-.}}"
    local file
    file=$(_guardrails_get_file "$project_dir")

    if [[ ! -f "$file" ]]; then
        echo "[]"
        return 0
    fi

    # Parse lessons from markdown
    local lessons="[]"
    local current_lesson=""
    local current_date=""
    local current_task=""
    local in_lesson=false

    while IFS= read -r line; do
        # Check for lesson header (### YYYY-MM-DD or ### YYYY-MM-DD - task-id)
        if [[ "$line" =~ ^###\ ([0-9]{4}-[0-9]{2}-[0-9]{2})(\ -\ (.+))?$ ]]; then
            # Save previous lesson if exists
            if [[ -n "$current_lesson" && "$in_lesson" == "true" ]]; then
                local lesson_json
                lesson_json=$(jq -n \
                    --arg date "$current_date" \
                    --arg task "$current_task" \
                    --arg content "$current_lesson" \
                    '{date: $date, task_id: (if $task == "" then null else $task end), content: $content}')
                lessons=$(echo "$lessons" | jq --argjson l "$lesson_json" '. + [$l]')
            fi

            # Start new lesson
            current_date="${BASH_REMATCH[1]}"
            current_task="${BASH_REMATCH[3]:-}"
            current_lesson=""
            in_lesson=true
        elif [[ "$in_lesson" == "true" && -n "$line" ]]; then
            # Append to current lesson
            if [[ -n "$current_lesson" ]]; then
                current_lesson+=$'\n'"$line"
            else
                current_lesson="$line"
            fi
        fi
    done < "$file"

    # Save last lesson if exists
    if [[ -n "$current_lesson" && "$in_lesson" == "true" ]]; then
        local lesson_json
        lesson_json=$(jq -n \
            --arg date "$current_date" \
            --arg task "$current_task" \
            --arg content "$current_lesson" \
            '{date: $date, task_id: (if $task == "" then null else $task end), content: $content}')
        lessons=$(echo "$lessons" | jq --argjson l "$lesson_json" '. + [$l]')
    fi

    echo "$lessons"
}

#!/usr/bin/env bash
#
# cmd_guardrails.sh - guardrails subcommand implementation
#
# Implements the 'cub guardrails' command for managing institutional memory.
#

# Include guard
if [[ -n "${_CUB_CMD_GUARDRAILS_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_GUARDRAILS_SH_LOADED=1

cmd_guardrails_help() {
    cat <<'EOF'
cub guardrails [subcommand] [options]

Manage institutional memory guardrails that persist lessons learned across
sessions to prevent repeating past mistakes.

USAGE:
  cub guardrails show [--format]     Display current guardrails
  cub guardrails add "lesson text"   Add a new lesson
  cub guardrails learn               Interactively learn from recent failures
  cub guardrails --help              Show this help

SUBCOMMANDS:
  show [--format FORMAT]    Display guardrails file contents
                            Formats: text (default), json, markdown

  add "lesson text"         Add a lesson to the Project-Specific section
                            Creates guardrails.md if it doesn't exist
                            Lesson text must be provided as a string argument

  learn                     Interactively learn from recent failures
                            Shows recent task failures, lets you select one,
                            uses AI to extract a lesson, and prompts for
                            confirmation before adding to guardrails.md

OUTPUT:
  show:  Displays the .cub/guardrails.md file with:
         - Project-specific guidance and conventions
         - Lessons learned from previous task failures
         - Linked task IDs and dates for traceability

         If no guardrails file exists, shows informational message.

  add:   Appends the lesson to the Project-Specific section and confirms success

  learn: Interactive workflow to extract lessons from failures

EXAMPLES:
  # Display guardrails
  cub guardrails show

  # Show as JSON (for scripting)
  cub guardrails show --format json

  # Show as markdown (for documentation)
  cub guardrails show --format markdown

  # Add a lesson
  cub guardrails add "Always run tests before committing"

  # Add a lesson with special characters
  cub guardrails add "Use jq for JSON parsing, not sed/awk"

  # Learn from recent failures interactively
  cub guardrails learn

SEE ALSO:
  cub status    Check task progress
  cub run       Execute tasks
  cub --help    Show all commands
EOF
}

cmd_guardrails_show() {
    local format="text"

    # Parse format flag
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --format)
                shift
                if [[ $# -eq 0 ]]; then
                    _log_error_console "Error: --format requires a value"
                    return 1
                fi
                format="$1"
                shift
                ;;
            --help|-h)
                cmd_guardrails_help
                return 0
                ;;
            *)
                _log_error_console "Unknown option: $1"
                return 1
                ;;
        esac
    done

    # Validate format
    case "$format" in
        text|json|markdown)
            : # Valid format
            ;;
        *)
            _log_error_console "Error: Invalid format '$format' (expected: text, json, markdown)"
            return 1
            ;;
    esac

    # Check if guardrails file exists
    if ! guardrails_exists "${PROJECT_DIR}"; then
        log_info "No guardrails file yet - this is where project-specific lessons will accumulate"
        log_info "Location: ${PROJECT_DIR}/.cub/guardrails.md"
        return 0
    fi

    # Read guardrails content
    local content
    content=$(guardrails_read "${PROJECT_DIR}")

    case "$format" in
        text)
            # Display as formatted text
            echo "$content"
            ;;
        markdown)
            # Display as markdown (same as text since file is already markdown)
            echo "$content"
            ;;
        json)
            # Convert to JSON format using guardrails_list_json
            guardrails_list_json "${PROJECT_DIR}"
            ;;
    esac

    return 0
}

cmd_guardrails_add() {
    local lesson="$1"

    # Check for help flag
    if [[ "${lesson}" == "--help" || "${lesson}" == "-h" ]]; then
        cmd_guardrails_help
        return 0
    fi

    # Validate lesson text was provided
    if [[ -z "$lesson" ]]; then
        _log_error_console "Error: lesson text is required"
        _log_error_console "Usage: cub guardrails add \"lesson text\""
        return 1
    fi

    # Add the lesson to guardrails Project-Specific section
    if guardrails_add_to_project "$lesson" "${PROJECT_DIR}"; then
        log_success "Guardrail added successfully"
        log_info "Location: $(guardrails_get_file "${PROJECT_DIR}")"
        # Check and warn about size after adding
        guardrails_warn_size_if_exceeded "" "${PROJECT_DIR}"
        return 0
    else
        _log_error_console "Error: Failed to add guardrail"
        return 1
    fi
}

# Get recent failures from run artifacts
# Returns: Array of failure.json paths (newest first)
_cmd_guardrails_get_recent_failures() {
    local max_results="${1:-10}"
    local runs_dir="${PROJECT_DIR}/.cub/runs"

    if [[ ! -d "$runs_dir" ]]; then
        return 0
    fi

    # Find all failure.json files, sort by modification time (newest first)
    # Use different stat format for macOS vs Linux
    if [[ "$(uname)" == "Darwin" ]]; then
        # macOS
        find "$runs_dir" -type f -name "failure.json" -exec stat -f "%m %N" {} \; 2>/dev/null | \
            sort -rn | \
            head -n "$max_results" | \
            cut -d' ' -f2-
    else
        # Linux
        find "$runs_dir" -type f -name "failure.json" -exec stat -c "%Y %n" {} \; 2>/dev/null | \
            sort -rn | \
            head -n "$max_results" | \
            cut -d' ' -f2-
    fi
}

# Interactive learn from failures command
cmd_guardrails_learn() {
    # Check for help flag
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_guardrails_help
        return 0
    fi

    # Source required libraries
    source "${CUB_DIR}/lib/guardrails.sh"
    source "${CUB_DIR}/lib/logger.sh"

    log_info "Searching for recent task failures..."

    # Get recent failures
    local failures=()
    while IFS= read -r failure_file; do
        if [[ -n "$failure_file" ]]; then
            failures+=("$failure_file")
        fi
    done < <(_cmd_guardrails_get_recent_failures 10)

    # Check if any failures were found
    if [[ ${#failures[@]} -eq 0 ]]; then
        log_info "No recent failures found"
        log_info "Failures are recorded when tasks fail during 'cub run'"
        return 0
    fi

    # Display failures for selection
    echo ""
    echo "Recent failures:"
    echo ""

    local -a failure_data=()
    local i=1
    for failure_file in "${failures[@]}"; do
        # Parse failure data
        local task_id exit_code output timestamp
        task_id=$(jq -r '.task_id' "$failure_file" 2>/dev/null || echo "unknown")
        exit_code=$(jq -r '.exit_code' "$failure_file" 2>/dev/null || echo "?")
        output=$(jq -r '.output' "$failure_file" 2>/dev/null || echo "")
        timestamp=$(jq -r '.timestamp' "$failure_file" 2>/dev/null || echo "unknown")

        # Get task title if available
        local task_dir
        task_dir=$(dirname "$failure_file")
        local task_title=""
        if [[ -f "${task_dir}/task.json" ]]; then
            task_title=$(jq -r '.title // ""' "${task_dir}/task.json" 2>/dev/null || echo "")
        fi

        # Store data for later use
        failure_data+=("${failure_file}|${task_id}|${exit_code}|${output}|${task_title}")

        # Display formatted entry
        echo "  ${i}. Task: ${task_id}${task_title:+ - ${task_title}}"
        echo "     Exit code: ${exit_code}"
        echo "     Time: ${timestamp}"
        if [[ -n "$output" && "$output" != "null" ]]; then
            # Truncate long output
            local display_output="$output"
            if [[ ${#display_output} -gt 100 ]]; then
                display_output="${display_output:0:100}..."
            fi
            echo "     Error: ${display_output}"
        fi
        echo ""

        i=$((i + 1))
    done

    # Prompt for selection
    echo -n "Select a failure to learn from (1-${#failures[@]}, or 'q' to quit): "
    read -r selection

    # Check for quit
    if [[ "$selection" == "q" || "$selection" == "Q" ]]; then
        log_info "Cancelled"
        return 0
    fi

    # Validate selection
    if ! [[ "$selection" =~ ^[0-9]+$ ]] || [[ "$selection" -lt 1 ]] || [[ "$selection" -gt ${#failures[@]} ]]; then
        _log_error_console "Error: Invalid selection"
        return 1
    fi

    # Get selected failure data
    local selected_index=$((selection - 1))
    local selected_data="${failure_data[$selected_index]}"

    IFS='|' read -r failure_file task_id exit_code output task_title <<< "$selected_data"

    # Extract lesson using AI
    log_info "Extracting lesson from failure using AI..."

    local lesson
    lesson=$(guardrails_extract_lesson_ai "$task_id" "$task_title" "$output" "${PROJECT_DIR}")
    local extract_result=$?

    if [[ $extract_result -ne 0 ]]; then
        _log_error_console "Error: Failed to extract lesson"
        return 1
    fi

    # Display extracted lesson
    echo ""
    log_info "Extracted lesson:"
    echo ""
    echo "  ${lesson}"
    echo ""

    # Prompt for confirmation
    echo -n "Add this lesson to guardrails? (y/n): "
    read -r confirmation

    if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
        log_info "Cancelled - lesson not added"
        return 0
    fi

    # Add the lesson to guardrails (this will also trigger size warning)
    if guardrails_add "$lesson" "$task_id" "${PROJECT_DIR}"; then
        log_success "Lesson added to guardrails"
        log_info "Location: $(guardrails_get_file "${PROJECT_DIR}")"
        return 0
    else
        _log_error_console "Error: Failed to add lesson to guardrails"
        return 1
    fi
}

cmd_guardrails() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_guardrails_help
        return 0
    fi

    # Extract subcommand (first non-flag argument)
    local subcommand="${1:-}"

    # If no subcommand provided or it's a flag, default to show
    if [[ -z "$subcommand" || "$subcommand" =~ ^- ]]; then
        if [[ -z "$subcommand" ]]; then
            # No args - show help
            cmd_guardrails_help
            return 0
        fi
        # Process as flags for 'show' (shift them through)
        cmd_guardrails_show "$@"
        return $?
    fi

    case "$subcommand" in
        show)
            # Shift to pass remaining args to show
            shift
            cmd_guardrails_show "$@"
            ;;
        add)
            # Shift to pass lesson text to add
            shift
            cmd_guardrails_add "$@"
            ;;
        learn)
            # Shift to pass remaining args to learn
            shift
            cmd_guardrails_learn "$@"
            ;;
        *)
            _log_error_console "Unknown subcommand: ${subcommand}"
            return 1
            ;;
    esac
}

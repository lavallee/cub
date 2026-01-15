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
  cub guardrails --help              Show this help

SUBCOMMANDS:
  show [--format FORMAT]    Display guardrails file contents
                            Formats: text (default), json, markdown

  add "lesson text"         Add a lesson to the Project-Specific section
                            Creates guardrails.md if it doesn't exist
                            Lesson text must be provided as a string argument

OUTPUT:
  show:  Displays the .cub/guardrails.md file with:
         - Project-specific guidance and conventions
         - Lessons learned from previous task failures
         - Linked task IDs and dates for traceability

         If no guardrails file exists, shows informational message.

  add:   Appends the lesson to the Project-Specific section and confirms success

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
        return 0
    else
        _log_error_console "Error: Failed to add guardrail"
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
        *)
            _log_error_console "Unknown subcommand: ${subcommand}"
            return 1
            ;;
    esac
}

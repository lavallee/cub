#!/usr/bin/env bash
#
# lib/cmd_import.sh - Import command for cub
#
# Imports requirements from various sources and converts to tasks:
# - GitHub issues (via gh CLI)
# - Markdown documents
# - JSON files
#
# Usage:
#   cub import <source> [options]
#   cub import --github owner/repo [--include-closed] [--labels "label1,label2"]
#   cub import requirements.md
#   cub import tasks.json
#   cub import <source> --dry-run
#   cub import <source> --backend beads|json
#

# Source the parsers
if [[ -z "$CUB_LIB_DIR" ]]; then
    CUB_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

# shellcheck source=lib/parsers/markdown.sh
source "$CUB_LIB_DIR/parsers/markdown.sh" || return 1
# shellcheck source=lib/parsers/json.sh
source "$CUB_LIB_DIR/parsers/json.sh" || return 1
# shellcheck source=lib/parsers/github.sh
source "$CUB_LIB_DIR/parsers/github.sh" || return 1

# Main import command handler
cmd_import() {
    local source=""
    local dry_run=false
    local backend=""
    local include_closed=false
    local label_filter=""
    local format=""
    local first_positional=true

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
        --help|-h)
            _print_import_help
            return 0
            ;;
        --dry-run)
            dry_run=true
            shift
            ;;
        --backend)
            backend="$2"
            shift 2
            ;;
        --include-closed)
            include_closed=true
            shift
            ;;
        --labels)
            label_filter="$2"
            shift 2
            ;;
        --github)
            format="github"
            source="$2"
            shift 2
            ;;
        --*)
            echo "Unknown option: $1" >&2
            _print_import_help
            return 1
            ;;
        *)
            # Positional argument (source)
            if [[ "$first_positional" == "true" ]]; then
                source="$1"
                first_positional=false
                shift
            else
                echo "Unknown argument: $1" >&2
                _print_import_help
                return 1
            fi
            ;;
        esac
    done

    # Validate source
    if [[ -z "$source" ]]; then
        echo "Error: No source specified" >&2
        _print_import_help
        return 1
    fi

    # Detect format if not specified
    if [[ -z "$format" ]]; then
        if [[ "$source" =~ ^[^/]+/[^/]+$ ]]; then
            # Looks like owner/repo
            format="github"
        elif [[ -f "$source" ]]; then
            case "$source" in
            *.md)
                format="markdown"
                ;;
            *.json)
                format="json"
                ;;
            *)
                echo "Error: Unknown file format for $source" >&2
                return 1
                ;;
            esac
        else
            echo "Error: File not found: $source" >&2
            return 1
        fi
    fi

    # Validate backend (if specified)
    if [[ -n "$backend" ]] && [[ "$backend" != "beads" ]] && [[ "$backend" != "json" ]]; then
        echo "Error: Invalid backend. Must be 'beads' or 'json'" >&2
        return 1
    fi

    # Parse based on format
    local parsed
    case "$format" in
    github)
        _import_github "$source" "$include_closed" "$label_filter" "$dry_run"
        return $?
        ;;
    markdown)
        _import_markdown "$source" "$dry_run"
        return $?
        ;;
    json)
        _import_json "$source" "$dry_run"
        return $?
        ;;
    *)
        echo "Error: Unknown format: $format" >&2
        return 1
        ;;
    esac
}

# Import GitHub issues
_import_github() {
    local repo="$1"
    local include_closed="$2"
    local label_filter="$3"
    local dry_run="$4"

    echo "Importing GitHub issues from $repo..." >&2

    # Parse GitHub issues
    local parsed
    parsed=$(parse_github_repo "$repo" "$include_closed" "$label_filter")

    if [[ $? -ne 0 ]]; then
        echo "Error: Failed to parse GitHub issues" >&2
        echo "$parsed" | jq '.error' 2>/dev/null
        return 1
    fi

    # Show preview
    format_parsed_github "$parsed" >&2
    echo "" >&2

    if [[ "$dry_run" == "true" ]]; then
        echo "Dry-run mode: No tasks created" >&2
        echo "$parsed"
        return 0
    fi

    # Import to task backend
    _import_to_backend "$parsed"
}

# Import Markdown file
_import_markdown() {
    local source="$1"
    local dry_run="$2"

    echo "Importing from Markdown: $source" >&2

    # Parse markdown
    local parsed
    parsed=$(parse_markdown_file "$source")

    if [[ $? -ne 0 ]]; then
        echo "Error: Failed to parse Markdown" >&2
        echo "$parsed" | jq '.error' 2>/dev/null
        return 1
    fi

    # Show preview
    format_parsed_markdown "$parsed" >&2
    echo "" >&2

    if [[ "$dry_run" == "true" ]]; then
        echo "Dry-run mode: No tasks created" >&2
        echo "$parsed"
        return 0
    fi

    # Import to task backend
    _import_to_backend "$parsed"
}

# Import JSON file
_import_json() {
    local source="$1"
    local dry_run="$2"

    echo "Importing from JSON: $source" >&2

    # Parse JSON
    local parsed
    parsed=$(parse_json_file "$source")

    if [[ $? -ne 0 ]]; then
        echo "Error: Failed to parse JSON" >&2
        echo "$parsed" | jq '.error' 2>/dev/null
        return 1
    fi

    # Show preview
    echo "=== Parsed JSON ===" >&2
    local epic_count
    epic_count=$(echo "$parsed" | jq '.epics | length')
    if [[ "$epic_count" -gt 0 ]]; then
        echo "Epics: $epic_count" >&2
        echo "$parsed" | jq -r '.epics[] | "  [\(.id)] \(.title)"' >&2
        echo "" >&2
    fi

    local task_count
    task_count=$(echo "$parsed" | jq '.tasks | length')
    echo "Tasks: $task_count" >&2
    echo "$parsed" | jq -r '.tasks[] | "  [\(.id)] \(.title)"' >&2
    echo "" >&2

    if [[ "$dry_run" == "true" ]]; then
        echo "Dry-run mode: No tasks created" >&2
        echo "$parsed"
        return 0
    fi

    # Import to task backend
    _import_to_backend "$parsed"
}

# Import parsed data to task backend (beads or JSON)
_import_to_backend() {
    local parsed="$1"

    # Determine which backend to use
    local backend="beads"
    if ! command -v bd &>/dev/null; then
        backend="json"
    fi

    # Count items
    local item_count
    item_count=$(echo "$parsed" | jq '[.epics, .tasks] | flatten | length')

    echo "Creating $item_count tasks in $backend backend..." >&2

    case "$backend" in
    beads)
        _import_to_beads "$parsed"
        ;;
    json)
        _import_to_json "$parsed"
        ;;
    esac

    return $?
}

# Import tasks to beads backend
_import_to_beads() {
    local parsed="$1"

    # Create epics first
    local epics_created=0
    echo "$parsed" | jq -r '.epics[] | @base64' | while IFS= read -r epic_base64; do
        local epic
        epic=$(echo "$epic_base64" | base64 -d)

        local epic_id
        local epic_title
        epic_id=$(echo "$epic" | jq -r '.id')
        epic_title=$(echo "$epic" | jq -r '.title')

        if bd create --title "$epic_title" --type epic >/dev/null 2>&1; then
            ((epics_created++))
            echo "  ✓ Created epic: $epic_title" >&2
        fi
    done

    # Create tasks
    local tasks_created=0
    echo "$parsed" | jq -r '.tasks[] | @base64' | while IFS= read -r task_base64; do
        local task
        task=$(echo "$task_base64" | base64 -d)

        local task_id
        local task_title
        task_id=$(echo "$task" | jq -r '.id')
        task_title=$(echo "$task" | jq -r '.title')

        # Build bd create command
        local bd_args=("--title" "$task_title")

        # Add priority
        local priority
        priority=$(echo "$task" | jq -r '.priority // "P2"')
        bd_args+=("--priority" "$priority")

        # Add type
        bd_args+=("--type" "task")

        # Add labels
        echo "$task" | jq -r '.labels[]?' | while IFS= read -r label; do
            if [[ -n "$label" ]]; then
                bd_args+=("--label" "$label")
            fi
        done

        if bd create "${bd_args[@]}" >/dev/null 2>&1; then
            ((tasks_created++))
            echo "  ✓ Created task: $task_title" >&2
        fi
    done

    echo "Imported: $epics_created epics, $tasks_created tasks" >&2
    return 0
}

# Import tasks to JSON backend (prd.json)
_import_to_json() {
    local parsed="$1"

    local prd_file="prd.json"

    # Check if prd.json exists
    if [[ ! -f "$prd_file" ]]; then
        # Create new prd.json with imported tasks
        echo "$parsed" | jq '{tasks: .tasks}' >"$prd_file"
        echo "Created $prd_file with imported tasks" >&2
        return 0
    fi

    # Merge with existing prd.json
    local merged
    merged=$(jq -n \
        --slurpfile existing "$prd_file" \
        --argjson new "$parsed" \
        '{tasks: ($existing[0].tasks + $new.tasks)}')

    echo "$merged" >"$prd_file"
    echo "Merged imported tasks into $prd_file" >&2
    return 0
}

# Print help message
_print_import_help() {
    cat >&2 <<'EOF'
Usage: cub import <source> [options]

Import requirements from various sources and convert to tasks.

Positional Arguments:
  <source>              File path or repository (auto-detected)
                       Examples: requirements.md, tasks.json, owner/repo

Format Flags:
  --github <repo>       Import GitHub issues (owner/repo format)

Options:
  --dry-run             Preview import without creating tasks
  --backend beads|json  Override backend detection
  --include-closed      Include closed issues (GitHub only)
  --labels <filter>     Filter by comma-separated labels (GitHub only)

Examples:
  cub import requirements.md
  cub import tasks.json
  cub import --github anthropics/claude-code
  cub import --github anthropics/claude-code --labels "bug,priority:high"
  cub import requirements.md --dry-run
  cub import requirements.md --backend beads

Supported Formats:
  - Markdown (.md)
  - JSON (.json)
  - GitHub issues (via gh CLI)

EOF
}

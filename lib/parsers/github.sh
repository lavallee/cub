#!/usr/bin/env bash
#
# lib/parsers/github.sh - GitHub issues parser for cub import
#
# Fetches GitHub issues via gh CLI and converts them to structured task format.
#
# Features:
# - Issue number as reference (e.g., #123)
# - Labels preserved as tags
# - Milestones as epics
# - Body parsed for acceptance criteria
#
# Usage:
#   parse_github_repo "owner/repo"
#   parse_github_issues "$json_data"
#
# Output: JSON with structure:
#   {
#     "epics": [...],
#     "tasks": [...],
#     "dependencies": [...]
#   }
#

# Check if gh CLI is available
_check_gh_available() {
    if ! command -v gh &>/dev/null; then
        echo '{"error":"gh CLI not found. Install from https://cli.github.com/"}' >&2
        return 1
    fi
}

# Parse GitHub issues from a repository
# Usage: parse_github_repo "owner/repo" [--include-closed] [--labels "label1,label2"]
# Output: JSON with epics, tasks, dependencies
parse_github_repo() {
    local repo="$1"
    local include_closed="${2:-false}"
    local label_filter="${3:-}"

    _check_gh_available || return 1

    if [[ -z "$repo" ]] || [[ ! "$repo" =~ ^[^/]+/[^/]+$ ]]; then
        echo '{"error":"Invalid repo format. Use owner/repo"}' >&2
        return 1
    fi

    # Build gh issue list command
    local state="open"
    if [[ "$include_closed" == "true" ]]; then
        state="all"
    fi

    # Fetch issues as JSON
    local issues_json
    issues_json=$(gh issue list --repo "$repo" --state "$state" --json number,title,body,labels,milestone,author --limit 1000 2>/dev/null)

    if [[ $? -ne 0 ]]; then
        echo '{"error":"Failed to fetch issues from GitHub"}' >&2
        return 1
    fi

    # Parse the fetched issues
    parse_github_issues "$issues_json" "$label_filter"
}

# Parse GitHub issues from JSON data
# Usage: parse_github_issues "$json_data" [--labels "label1,label2"]
# Expects JSON array from gh CLI with: number, title, body, labels[], milestone, author
parse_github_issues() {
    local issues_json="$1"
    local label_filter="${2:-}"

    if [[ -z "$issues_json" ]]; then
        echo '{"error":"No issues data provided"}' >&2
        return 1
    fi

    # Initialize output arrays
    local epics_json="[]"
    local tasks_json="[]"
    local dependencies_json="[]"
    local milestone_to_epic_map="{}"

    # Process each issue
    while IFS= read -r issue_line; do
        if [[ -z "$issue_line" ]]; then
            continue
        fi

        # Extract fields from issue
        local issue_number
        local title
        local body
        local labels
        local milestone
        local author

        issue_number=$(jq -r '.number // 0' <<<"$issue_line")
        title=$(jq -r '.title // ""' <<<"$issue_line")
        body=$(jq -r '.body // ""' <<<"$issue_line")
        labels=$(jq -r '.labels[].name' <<<"$issue_line" 2>/dev/null | tr '\n' ',' | sed 's/,$//')
        milestone=$(jq -r '.milestone.title // ""' <<<"$issue_line")
        author=$(jq -r '.author.login // "unknown"' <<<"$issue_line")

        # Skip if no issue number (invalid)
        if [[ "$issue_number" == "0" ]] || [[ -z "$title" ]]; then
            continue
        fi

        # Apply label filter if specified
        if [[ -n "$label_filter" ]]; then
            local has_label=false
            IFS=',' read -ra filter_labels <<<"$label_filter"
            for filter_label in "${filter_labels[@]}"; do
                if [[ " $labels " =~ " $filter_label " ]]; then
                    has_label=true
                    break
                fi
            done
            if [[ "$has_label" != "true" ]]; then
                continue
            fi
        fi

        # Create or get epic from milestone (if present)
        local epic_id=""
        if [[ -n "$milestone" ]]; then
            epic_id="epic-$(echo "$milestone" | tr ' ' '-' | tr '[:upper:]' '[:lower:]')"

            # Check if this epic already exists in our map
            if ! jq -e ".\"$epic_id\"" <<<"$milestone_to_epic_map" >/dev/null 2>&1; then
                # Create new epic
                local epic_obj
                epic_obj=$(jq -n \
                    --arg id "$epic_id" \
                    --arg title "$milestone" \
                    '{id: $id, title: $title, description: "", type: "epic", priority: "P2"}')
                epics_json=$(jq --argjson obj "$epic_obj" '. += [$obj]' <<<"$epics_json")
                milestone_to_epic_map=$(jq --arg id "$epic_id" '. += {($id): true}' <<<"$milestone_to_epic_map")
            fi
        fi

        # Parse acceptance criteria from body
        local acceptance_criteria
        acceptance_criteria=$(_parse_acceptance_criteria "$body")

        # Infer priority from title and body
        local priority
        priority=$(_infer_priority "$title" "$body")

        # Create task object
        local task_id="issue-$issue_number"
        local task_labels=()

        # Add labels as tags
        if [[ -n "$labels" ]]; then
            IFS=',' read -ra task_labels <<<"$labels"
        fi

        # Add 'imported' and 'github' labels
        task_labels+=("imported" "github" "gh-issue-#$issue_number")

        local labels_array
        labels_array=$(printf '%s\n' "${task_labels[@]}" | jq -R . | jq -s .)

        local task_obj
        task_obj=$(jq -n \
            --arg id "$task_id" \
            --arg title "$title" \
            --arg description "GitHub issue #$issue_number\n\nAuthor: $author\n\n$body" \
            --arg epic "$epic_id" \
            --arg priority "$priority" \
            --argjson labels "$labels_array" \
            --argjson acceptance_criteria "$acceptance_criteria" \
            '{id: $id, title: $title, description: $description, type: "task", epic: (if $epic != "" then $epic else null end), priority: $priority, labels: $labels, acceptanceCriteria: $acceptance_criteria, status: "open"}')

        tasks_json=$(jq --argjson obj "$task_obj" '. += [$obj]' <<<"$tasks_json")

    done < <(jq -c '.[]' <<<"$issues_json")

    # Combine into output JSON
    jq -n \
        --argjson epics "$epics_json" \
        --argjson tasks "$tasks_json" \
        --argjson dependencies "$dependencies_json" \
        '{epics: $epics, tasks: $tasks, dependencies: $dependencies}'
}

# Parse acceptance criteria from issue body
# Looks for:
# - Checkbox lists: - [ ] item
# - "Acceptance criteria:" sections
# - "Done when:" sections
# Output: JSON array of criteria strings
_parse_acceptance_criteria() {
    local body="$1"
    local criteria="[]"

    if [[ -z "$body" ]]; then
        echo "$criteria"
        return
    fi

    # Extract checkbox items from body (- [ ] text)
    while IFS= read -r line; do
        if [[ "$line" =~ ^-[[:space:]]*\[[[:space:]]*\][[:space:]]+ ]]; then
            local criterion="${line#*\] }"
            criterion="${criterion#[[:space:]]}"
            if [[ -n "$criterion" ]]; then
                criteria=$(jq --arg text "$criterion" '. += [$text]' <<<"$criteria")
            fi
        fi
    done < <(echo "$body")

    echo "$criteria"
}

# Infer priority from title and body
# Looks for: [P0], [P1], [P2], [P3], [P4]
# Keywords: critical, blocker, must, high, important, low, optional, nice-to-have
# Output: Priority string (P0-P4, default P2)
_infer_priority() {
    local title="$1"
    local body="$2"
    local text="$title
$body"

    # Convert to lowercase for matching
    local text_lower
    text_lower=$(echo "$text" | tr '[:upper:]' '[:lower:]')

    # Check for explicit priority markers
    if [[ "$text" =~ \[P0\] ]]; then
        echo "P0"
        return
    elif [[ "$text" =~ \[P1\] ]]; then
        echo "P1"
        return
    elif [[ "$text" =~ \[P2\] ]]; then
        echo "P2"
        return
    elif [[ "$text" =~ \[P3\] ]]; then
        echo "P3"
        return
    elif [[ "$text" =~ \[P4\] ]]; then
        echo "P4"
        return
    fi

    # Check for keyword patterns
    if [[ "$text_lower" =~ (critical|blocker|must|urgent|high.priority) ]]; then
        echo "P0"
    elif [[ "$text_lower" =~ (high|important|required) ]]; then
        echo "P1"
    elif [[ "$text_lower" =~ (low|optional|nice.to.have|nice-to-have) ]]; then
        echo "P3"
    else
        echo "P2"  # Default priority
    fi
}

# Extract just the epics from parsed GitHub issues
# Input: JSON from parse_github_repo or parse_github_issues
# Output: Array of epic objects
extract_epics() {
    local parsed="$1"
    echo "$parsed" | jq '.epics'
}

# Extract just the tasks from parsed GitHub issues
# Input: JSON from parse_github_repo or parse_github_issues
# Output: Array of task objects
extract_tasks() {
    local parsed="$1"
    echo "$parsed" | jq '.tasks'
}

# Count total items (epics + tasks)
# Input: JSON from parse_github_repo or parse_github_issues
count_items() {
    local parsed="$1"
    local epic_count
    local task_count

    epic_count=$(echo "$parsed" | jq '.epics | length')
    task_count=$(echo "$parsed" | jq '.tasks | length')

    echo "$((epic_count + task_count))"
}

# Format parsed GitHub issues as human-readable output
# Input: JSON from parse_github_repo or parse_github_issues
# Output: Formatted text
format_parsed_github() {
    local parsed="$1"

    echo "=== Parsed GitHub Issues ==="
    echo ""

    # Show epics
    local epic_count
    epic_count=$(echo "$parsed" | jq '.epics | length')
    if [[ "$epic_count" -gt 0 ]]; then
        echo "Milestones (Epics): $epic_count"
        echo "$parsed" | jq -r '.epics[] | "  [\(.id)] \(.title)"'
        echo ""
    fi

    # Show tasks
    local task_count
    task_count=$(echo "$parsed" | jq '.tasks | length')
    echo "Issues (Tasks): $task_count"
    echo "$parsed" | jq -r '.tasks[] | "  [\(.id)] \(.title) [Priority: \(.priority)]"'

    echo ""
    echo "Acceptance Criteria:"
    echo "$parsed" | jq -r '.tasks[] | select(.acceptanceCriteria | length > 0) | "  \(.id):\n    \(.acceptanceCriteria | .[] | "✓ \(.)")"'
}

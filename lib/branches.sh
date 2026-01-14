#!/usr/bin/env bash
#
# branches.sh - Branch-epic binding management
#
# Provides functions for managing the relationship between git branches
# and beads epics. Stores metadata in .beads/branches.yaml.
#
# Usage:
#   branches_bind <epic_id> [branch_name]    # Bind current or named branch to epic
#   branches_get_branch <epic_id>            # Get branch bound to epic
#   branches_get_epic [branch_name]          # Get epic bound to current or named branch
#   branches_list                            # List all bindings as JSON
#   branches_unbind <epic_id>                # Remove binding for epic
#   branches_update_pr <epic_id> <pr_number> # Update PR number for binding
#

# Include guard
if [[ -n "${_CUB_BRANCHES_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_BRANCHES_SH_LOADED=1

# Path to branches metadata file (relative to .beads/)
_BRANCHES_FILE=".beads/branches.yaml"

# Get the branches file path for a project
# Usage: _branches_get_file [project_dir]
_branches_get_file() {
    local project_dir="${1:-.}"
    echo "${project_dir}/${_BRANCHES_FILE}"
}

# Check if branches file exists
# Usage: branches_file_exists [project_dir]
branches_file_exists() {
    local project_dir="${1:-.}"
    local file
    file=$(_branches_get_file "$project_dir")
    [[ -f "$file" ]]
}

# Initialize branches file if it doesn't exist
# Usage: branches_init [project_dir]
# Returns: 0 on success, 1 on error
branches_init() {
    local project_dir="${1:-.}"
    local file
    file=$(_branches_get_file "$project_dir")

    # Ensure .beads directory exists
    local beads_dir="${project_dir}/.beads"
    if [[ ! -d "$beads_dir" ]]; then
        echo "ERROR: .beads directory does not exist in $project_dir" >&2
        return 1
    fi

    # Create file if it doesn't exist
    if [[ ! -f "$file" ]]; then
        cat > "$file" <<'EOF'
# Branch-Epic Bindings
# Managed by cub - do not edit manually
# Format: YAML with branch bindings array

bindings: []
EOF
    fi

    return 0
}

# Parse YAML to JSON (simple parser for our specific format)
# Usage: _branches_yaml_to_json <yaml_content>
# Note: This is a simple parser that handles our specific YAML structure
_branches_yaml_to_json() {
    local yaml_content="$1"

    # Use yq if available, otherwise fall back to simple bash parsing
    if command -v yq >/dev/null 2>&1; then
        echo "$yaml_content" | yq -o json '.' 2>/dev/null
        return $?
    fi

    # Simple bash-based YAML parser for our specific format
    # Expected format:
    # bindings:
    #   - epic_id: cub-vd6
    #     branch_name: cub/mink/20260114-165751
    #     status: active
    #     created_at: 2026-01-14T16:57:52Z
    #     pr_number: null
    #     merged: false

    local in_bindings=false
    local in_item=false
    local items=()
    local current_item=""

    while IFS= read -r line; do
        # Skip comments and empty lines
        if [[ "$line" =~ ^[[:space:]]*# ]]; then
            continue
        fi
        if [[ -z "$line" ]]; then
            continue
        fi

        # Check for bindings array start
        if [[ "$line" == "bindings:"* ]]; then
            in_bindings=true
            # Check for empty array notation
            if [[ "$line" == *"[]"* ]]; then
                echo '{"bindings":[]}'
                return 0
            fi
            continue
        fi

        if [[ "$in_bindings" == "true" ]]; then
            # Check for new item (starts with whitespace then -)
            if [[ "$line" == *"- "* ]] && [[ "$line" =~ ^[[:space:]]+- ]]; then
                # Save previous item if exists
                if [[ -n "$current_item" ]]; then
                    current_item+="}"
                    items+=("$current_item")
                fi
                # Start new item - extract first field
                local field_part="${line#*- }"
                current_item="{"

                # Parse key: value
                local yaml_key yaml_value
                yaml_key="${field_part%%:*}"
                yaml_value="${field_part#*: }"
                yaml_value="${yaml_value#"${yaml_value%%[![:space:]]*}"}"  # trim leading whitespace
                yaml_value="${yaml_value%"${yaml_value##*[![:space:]]}"}"  # trim trailing whitespace

                # Handle different value types
                if [[ "$yaml_value" == "null" ]] || [[ "$yaml_value" == "~" ]]; then
                    current_item+="\"$yaml_key\":null"
                elif [[ "$yaml_value" == "true" ]] || [[ "$yaml_value" == "false" ]]; then
                    current_item+="\"$yaml_key\":$yaml_value"
                elif [[ "$yaml_value" =~ ^[0-9]+$ ]]; then
                    current_item+="\"$yaml_key\":$yaml_value"
                else
                    # String value - escape quotes
                    yaml_value="${yaml_value//\"/\\\"}"
                    current_item+="\"$yaml_key\":\"$yaml_value\""
                fi
                in_item=true
            elif [[ "$in_item" == "true" ]] && [[ "$line" =~ ^[[:space:]]+[a-z_]+: ]]; then
                # Continuation of item (indented field)
                local yaml_key yaml_value
                line="${line#"${line%%[![:space:]]*}"}"  # trim leading whitespace
                yaml_key="${line%%:*}"
                yaml_value="${line#*: }"
                yaml_value="${yaml_value%"${yaml_value##*[![:space:]]}"}"  # trim trailing whitespace

                # Add comma separator
                current_item+=","

                # Handle different value types
                if [[ "$yaml_value" == "null" ]] || [[ "$yaml_value" == "~" ]]; then
                    current_item+="\"$yaml_key\":null"
                elif [[ "$yaml_value" == "true" ]] || [[ "$yaml_value" == "false" ]]; then
                    current_item+="\"$yaml_key\":$yaml_value"
                elif [[ "$yaml_value" =~ ^[0-9]+$ ]]; then
                    current_item+="\"$yaml_key\":$yaml_value"
                else
                    # String value - escape quotes
                    yaml_value="${yaml_value//\"/\\\"}"
                    current_item+="\"$yaml_key\":\"$yaml_value\""
                fi
            fi
        fi
    done <<< "$yaml_content"

    # Save last item
    if [[ -n "$current_item" ]]; then
        current_item+="}"
        items+=("$current_item")
    fi

    # Build JSON output
    local json_array=""
    local is_first=true
    for item in "${items[@]}"; do
        if [[ "$is_first" == "true" ]]; then
            json_array+="$item"
            is_first=false
        else
            json_array+=",$item"
        fi
    done

    echo "{\"bindings\":[$json_array]}"
}

# Convert JSON to YAML for our format
# Usage: _branches_json_to_yaml <json_content>
_branches_json_to_yaml() {
    local json_content="$1"

    # Use yq if available
    if command -v yq >/dev/null 2>&1; then
        echo "$json_content" | yq -P '.' 2>/dev/null
        return $?
    fi

    # Simple bash-based JSON to YAML converter for our format
    local output="# Branch-Epic Bindings
# Managed by cub - do not edit manually
# Format: YAML with branch bindings array

bindings:"

    # Parse bindings array using jq
    local binding_count
    binding_count=$(echo "$json_content" | jq '.bindings | length' 2>/dev/null)

    if [[ -z "$binding_count" ]] || [[ "$binding_count" -eq 0 ]]; then
        output+=" []"
    else
        local i
        for ((i=0; i<binding_count; i++)); do
            local binding
            binding=$(echo "$json_content" | jq -c ".bindings[$i]" 2>/dev/null)

            local b_epic_id b_branch_name b_base_branch b_status b_created_at b_pr_number b_merged
            b_epic_id=$(echo "$binding" | jq -r '.epic_id // ""')
            b_branch_name=$(echo "$binding" | jq -r '.branch_name // ""')
            b_base_branch=$(echo "$binding" | jq -r '.base_branch // "main"')
            b_status=$(echo "$binding" | jq -r '.status // "active"')
            b_created_at=$(echo "$binding" | jq -r '.created_at // ""')
            b_pr_number=$(echo "$binding" | jq -r '.pr_number // "null"')
            b_merged=$(echo "$binding" | jq -r '.merged // false')

            output+="
  - epic_id: ${b_epic_id}
    branch_name: ${b_branch_name}
    base_branch: ${b_base_branch}
    status: ${b_status}
    created_at: ${b_created_at}
    pr_number: ${b_pr_number}
    merged: ${b_merged}"
        done
    fi

    echo "$output"
}

# Read all bindings from branches.yaml as JSON
# Usage: branches_read [project_dir]
# Returns: JSON object with bindings array
branches_read() {
    local project_dir="${1:-.}"
    local file
    file=$(_branches_get_file "$project_dir")

    if [[ ! -f "$file" ]]; then
        echo '{"bindings":[]}'
        return 0
    fi

    local content
    content=$(cat "$file")
    _branches_yaml_to_json "$content"
}

# Write bindings JSON back to branches.yaml
# Usage: branches_write <json_content> [project_dir]
# Returns: 0 on success, 1 on error
branches_write() {
    local json_content="$1"
    local project_dir="${2:-.}"
    local file
    file=$(_branches_get_file "$project_dir")

    # Ensure .beads directory exists
    local beads_dir="${project_dir}/.beads"
    if [[ ! -d "$beads_dir" ]]; then
        echo "ERROR: .beads directory does not exist" >&2
        return 1
    fi

    local yaml_content
    yaml_content=$(_branches_json_to_yaml "$json_content")

    echo "$yaml_content" > "$file"
}

# Bind a branch to an epic
# Usage: branches_bind <epic_id> [branch_name] [base_branch] [project_dir]
# If branch_name is not provided, uses current git branch
# Returns: 0 on success, 1 on error
branches_bind() {
    local epic_id="$1"
    local branch_name="${2:-}"
    local base_branch="${3:-main}"
    local project_dir="${4:-.}"

    if [[ -z "$epic_id" ]]; then
        echo "ERROR: epic_id is required" >&2
        return 1
    fi

    # Get current branch if not provided
    if [[ -z "$branch_name" ]]; then
        branch_name=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
        if [[ -z "$branch_name" ]] || [[ "$branch_name" == "HEAD" ]]; then
            echo "ERROR: Could not determine current branch" >&2
            return 1
        fi
    fi

    # Initialize file if needed
    branches_init "$project_dir" || return 1

    # Read current bindings
    local bindings_json
    bindings_json=$(branches_read "$project_dir")

    # Check if epic already has a binding
    local existing
    existing=$(echo "$bindings_json" | jq -r --arg id "$epic_id" '.bindings[] | select(.epic_id == $id) | .branch_name' 2>/dev/null)

    if [[ -n "$existing" ]]; then
        echo "ERROR: Epic $epic_id is already bound to branch: $existing" >&2
        return 1
    fi

    # Check if branch already has a binding
    local existing_epic
    existing_epic=$(echo "$bindings_json" | jq -r --arg branch "$branch_name" '.bindings[] | select(.branch_name == $branch) | .epic_id' 2>/dev/null)

    if [[ -n "$existing_epic" ]]; then
        echo "ERROR: Branch $branch_name is already bound to epic: $existing_epic" >&2
        return 1
    fi

    # Create new binding
    local created_at
    created_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

    local new_binding
    new_binding=$(jq -n \
        --arg epic_id "$epic_id" \
        --arg branch_name "$branch_name" \
        --arg base_branch "$base_branch" \
        --arg created_at "$created_at" \
        '{
            epic_id: $epic_id,
            branch_name: $branch_name,
            base_branch: $base_branch,
            status: "active",
            created_at: $created_at,
            pr_number: null,
            merged: false
        }')

    # Add binding to array
    local updated_json
    updated_json=$(echo "$bindings_json" | jq --argjson binding "$new_binding" '.bindings += [$binding]')

    # Write back
    branches_write "$updated_json" "$project_dir"
}

# Get the branch bound to an epic
# Usage: branches_get_branch <epic_id> [project_dir]
# Returns: Branch name or empty string
branches_get_branch() {
    local epic_id="$1"
    local project_dir="${2:-.}"

    if [[ -z "$epic_id" ]]; then
        return 1
    fi

    local bindings_json
    bindings_json=$(branches_read "$project_dir")

    echo "$bindings_json" | jq -r --arg id "$epic_id" '.bindings[] | select(.epic_id == $id) | .branch_name // ""' 2>/dev/null
}

# Get the epic bound to a branch
# Usage: branches_get_epic [branch_name] [project_dir]
# If branch_name is not provided, uses current git branch
# Returns: Epic ID or empty string
branches_get_epic() {
    local branch_name="${1:-}"
    local project_dir="${2:-.}"

    # Get current branch if not provided
    if [[ -z "$branch_name" ]]; then
        branch_name=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
        if [[ -z "$branch_name" ]] || [[ "$branch_name" == "HEAD" ]]; then
            return 1
        fi
    fi

    local bindings_json
    bindings_json=$(branches_read "$project_dir")

    echo "$bindings_json" | jq -r --arg branch "$branch_name" '.bindings[] | select(.branch_name == $branch) | .epic_id // ""' 2>/dev/null
}

# Get full binding info for an epic
# Usage: branches_get_binding <epic_id> [project_dir]
# Returns: JSON object with binding details
branches_get_binding() {
    local epic_id="$1"
    local project_dir="${2:-.}"

    if [[ -z "$epic_id" ]]; then
        return 1
    fi

    local bindings_json
    bindings_json=$(branches_read "$project_dir")

    echo "$bindings_json" | jq --arg id "$epic_id" '.bindings[] | select(.epic_id == $id)' 2>/dev/null
}

# List all bindings
# Usage: branches_list [project_dir]
# Returns: JSON array of bindings
branches_list() {
    local project_dir="${1:-.}"

    local bindings_json
    bindings_json=$(branches_read "$project_dir")

    echo "$bindings_json" | jq '.bindings' 2>/dev/null
}

# Unbind an epic from its branch
# Usage: branches_unbind <epic_id> [project_dir]
# Returns: 0 on success, 1 on error
branches_unbind() {
    local epic_id="$1"
    local project_dir="${2:-.}"

    if [[ -z "$epic_id" ]]; then
        echo "ERROR: epic_id is required" >&2
        return 1
    fi

    local bindings_json
    bindings_json=$(branches_read "$project_dir")

    # Check if binding exists
    local existing
    existing=$(echo "$bindings_json" | jq -r --arg id "$epic_id" '.bindings[] | select(.epic_id == $id) | .epic_id' 2>/dev/null)

    if [[ -z "$existing" ]]; then
        echo "WARNING: No binding found for epic $epic_id" >&2
        return 0
    fi

    # Remove binding
    local updated_json
    updated_json=$(echo "$bindings_json" | jq --arg id "$epic_id" '.bindings = [.bindings[] | select(.epic_id != $id)]')

    # Write back
    branches_write "$updated_json" "$project_dir"
}

# Update PR number for a binding
# Usage: branches_update_pr <epic_id> <pr_number> [project_dir]
# Returns: 0 on success, 1 on error
branches_update_pr() {
    local epic_id="$1"
    local pr_number="$2"
    local project_dir="${3:-.}"

    if [[ -z "$epic_id" ]]; then
        echo "ERROR: epic_id is required" >&2
        return 1
    fi

    local bindings_json
    bindings_json=$(branches_read "$project_dir")

    # Check if binding exists
    local existing
    existing=$(echo "$bindings_json" | jq -r --arg id "$epic_id" '.bindings[] | select(.epic_id == $id) | .epic_id' 2>/dev/null)

    if [[ -z "$existing" ]]; then
        echo "ERROR: No binding found for epic $epic_id" >&2
        return 1
    fi

    # Update pr_number
    local updated_json
    if [[ -z "$pr_number" ]] || [[ "$pr_number" == "null" ]]; then
        updated_json=$(echo "$bindings_json" | jq --arg id "$epic_id" '
            .bindings = [.bindings[] | if .epic_id == $id then .pr_number = null else . end]
        ')
    else
        updated_json=$(echo "$bindings_json" | jq --arg id "$epic_id" --argjson pr "$pr_number" '
            .bindings = [.bindings[] | if .epic_id == $id then .pr_number = $pr else . end]
        ')
    fi

    # Write back
    branches_write "$updated_json" "$project_dir"
}

# Update binding status
# Usage: branches_update_status <epic_id> <new_status> [project_dir]
# new_status can be: active, merged, closed
# Returns: 0 on success, 1 on error
branches_update_status() {
    local epic_id="$1"
    local new_status="$2"
    local project_dir="${3:-.}"

    if [[ -z "$epic_id" ]] || [[ -z "$new_status" ]]; then
        echo "ERROR: epic_id and new_status are required" >&2
        return 1
    fi

    local bindings_json
    bindings_json=$(branches_read "$project_dir")

    # Update status (and merged flag if status is "merged")
    local updated_json
    if [[ "$new_status" == "merged" ]]; then
        updated_json=$(echo "$bindings_json" | jq --arg id "$epic_id" --arg st "$new_status" '
            .bindings = [.bindings[] | if .epic_id == $id then .status = $st | .merged = true else . end]
        ')
    else
        updated_json=$(echo "$bindings_json" | jq --arg id "$epic_id" --arg st "$new_status" '
            .bindings = [.bindings[] | if .epic_id == $id then .status = $st else . end]
        ')
    fi

    # Write back
    branches_write "$updated_json" "$project_dir"
}

# Get bindings by status
# Usage: branches_by_status <filter_status> [project_dir]
# Returns: JSON array of bindings with given status
branches_by_status() {
    local filter_status="$1"
    local project_dir="${2:-.}"

    local bindings_json
    bindings_json=$(branches_read "$project_dir")

    echo "$bindings_json" | jq --arg st "$filter_status" '[.bindings[] | select(.status == $st)]' 2>/dev/null
}

# Check if a branch exists in git
# Usage: branches_git_exists <branch_name>
# Returns: 0 if exists, 1 if not
branches_git_exists() {
    local branch_name="$1"
    git rev-parse --verify "$branch_name" >/dev/null 2>&1
}

# Get branches that are merged but not marked as such
# Usage: branches_find_merged [project_dir]
# Returns: JSON array of bindings for branches that are merged
branches_find_merged() {
    local project_dir="${1:-.}"
    local base_branch="${2:-main}"

    local bindings_json
    bindings_json=$(branches_read "$project_dir")

    local merged_list="[]"

    # Iterate over active bindings
    local bindings
    bindings=$(echo "$bindings_json" | jq -c '.bindings[] | select(.status == "active")')

    while IFS= read -r binding; do
        [[ -z "$binding" ]] && continue

        local branch_name
        branch_name=$(echo "$binding" | jq -r '.branch_name')
        local binding_base
        binding_base=$(echo "$binding" | jq -r '.base_branch // "main"')

        # Check if branch is merged into its base
        if git branch --merged "$binding_base" 2>/dev/null | grep -q "^[[:space:]]*${branch_name}$"; then
            merged_list=$(echo "$merged_list" | jq --argjson b "$binding" '. + [$b]')
        fi
    done <<< "$bindings"

    echo "$merged_list"
}

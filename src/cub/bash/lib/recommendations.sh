#!/usr/bin/env bash
#
# recommendations.sh - Recommendations engine for cub doctor
#
# Provides recommendations for improving project setup based on:
# - Build commands in agent.md
# - Hooks for common scenarios
# - Missing optional files
# - Project type-specific improvements
#

# Include guard
if [[ -n "${_CUB_RECOMMENDATIONS_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_RECOMMENDATIONS_SH_LOADED=1

# Source dependencies
if ! type detect_project_type &>/dev/null; then
    source "${SCRIPT_DIR}/project.sh"
fi

# Recommendation severity levels
readonly REC_CRITICAL=0
readonly REC_IMPORTANT=1
readonly REC_NICE_TO_HAVE=2

# Generate color-coded recommendation output
_rec_format() {
    local level="$1"
    local message="$2"

    case "$level" in
        $REC_CRITICAL)
            echo -e "${RED}[!]${NC} CRITICAL: $message"
            ;;
        $REC_IMPORTANT)
            echo -e "${YELLOW}[*]${NC} IMPORTANT: $message"
            ;;
        $REC_NICE_TO_HAVE)
            echo -e "${BLUE}[•]${NC} NICE TO HAVE: $message"
            ;;
    esac
}

# Detect what build commands are used in the project
_detect_build_commands() {
    local project_dir="${1:-.}"
    local -a builds

    # Check for npm/yarn
    if [[ -f "${project_dir}/package.json" ]]; then
        local npm_build
        npm_build=$(jq -r '.scripts.build // empty' "${project_dir}/package.json" 2>/dev/null)
        if [[ -n "$npm_build" ]]; then
            builds+=("npm run build")
        fi
    fi

    # Check for Makefile
    if [[ -f "${project_dir}/Makefile" ]] || [[ -f "${project_dir}/makefile" ]]; then
        if make -n build >/dev/null 2>&1; then
            builds+=("make build")
        fi
    fi

    # Check for Go
    if [[ -f "${project_dir}/go.mod" ]]; then
        builds+=("go build ./...")
    fi

    # Check for Rust
    if [[ -f "${project_dir}/Cargo.toml" ]]; then
        builds+=("cargo build")
    fi

    # Check for Python setuptools/build
    if [[ -f "${project_dir}/setup.py" ]] || [[ -f "${project_dir}/setup.cfg" ]]; then
        builds+=("python setup.py build")
    fi

    # Output results
    if [[ ${#builds[@]} -gt 0 ]]; then
        printf '%s\n' "${builds[@]}"
    fi
}

# Check if agent.md documents build commands
_check_build_commands() {
    local agent_file="$1"
    local project_dir="${2:-.}"
    local -a recommendations

    if [[ ! -f "$agent_file" ]]; then
        return 0
    fi

    # Detect actual build commands
    local actual_builds
    actual_builds=$(_detect_build_commands "$project_dir")

    if [[ -z "$actual_builds" ]]; then
        return 0
    fi

    # Check if agent.md mentions build commands
    local has_build_info=false
    while IFS= read -r build_cmd; do
        if grep -q "$build_cmd" "$agent_file" 2>/dev/null; then
            has_build_info=true
            break
        fi
    done <<< "$actual_builds"

    if [[ "$has_build_info" == "false" ]]; then
        recommendations+=("Add build command documentation to agent.md")
        recommendations+=("Document detected commands: $(echo "$actual_builds" | tr '\n' ', ' | sed 's/,$//')")
    fi

    # Output recommendations
    if [[ ${#recommendations[@]} -gt 0 ]]; then
        printf '%s\n' "${recommendations[@]}"
    fi
}

# Recommend common hooks for project type
_recommend_hooks() {
    local project_type="$1"
    local project_dir="${2:-.}"
    local hooks_config="${project_dir}/.cub.json"
    local -a recommendations

    # Check if hooks are already configured
    local has_hooks=false
    if [[ -f "$hooks_config" ]]; then
        has_hooks=$(jq -e '.hooks' "$hooks_config" >/dev/null 2>&1 && echo "true" || echo "false")
    fi

    # Recommend hooks based on project type
    case "$project_type" in
        node|react|nextjs)
            if [[ "$has_hooks" == "false" ]]; then
                recommendations+=("Add pre-task hook to run 'npm install' to ensure dependencies are current")
                recommendations+=("Add post-task hook to run 'npm test' for validation")
            fi
            ;;
        python)
            if [[ "$has_hooks" == "false" ]]; then
                recommendations+=("Add pre-task hook to run 'pip install -r requirements.txt' or 'poetry install'")
                recommendations+=("Add post-task hook to run 'pytest' for validation")
            fi
            ;;
        go)
            if [[ "$has_hooks" == "false" ]]; then
                recommendations+=("Add pre-task hook to run 'go mod download'")
                recommendations+=("Add post-task hook to run 'go test ./...'")
            fi
            ;;
        rust)
            if [[ "$has_hooks" == "false" ]]; then
                recommendations+=("Add pre-task hook to run 'cargo build' for dependency checks")
                recommendations+=("Add post-task hook to run 'cargo test'")
            fi
            ;;
    esac

    # Always recommend task-start hook for budget tracking
    if [[ "$has_hooks" == "false" ]]; then
        recommendations+=("Configure hooks in .cub.json to enable automatic budget tracking and validation")
    fi

    if [[ ${#recommendations[@]} -gt 0 ]]; then
        printf '%s\n' "${recommendations[@]}"
    fi
}

# Check for missing optional files
_check_optional_files() {
    local project_dir="${1:-.}"
    local -a recommendations

    # Check for missing .editorconfig
    if [[ ! -f "${project_dir}/.editorconfig" ]]; then
        recommendations+=("Add .editorconfig to enforce consistent code style across editors")
    fi

    # Check for missing .github/workflows
    if [[ ! -d "${project_dir}/.github/workflows" ]] && [[ -d "${project_dir}/.github" ]]; then
        recommendations+=("Consider adding GitHub Actions workflows for CI/CD (e.g., .github/workflows/test.yml)")
    fi

    # Check for missing CHANGELOG if git repo
    if git rev-parse --git-dir >/dev/null 2>&1 && [[ ! -f "${project_dir}/CHANGELOG.md" ]]; then
        recommendations+=("Consider maintaining a CHANGELOG.md to document version history")
    fi

    # Check for missing contributing guidelines
    if [[ ! -f "${project_dir}/CONTRIBUTING.md" ]]; then
        recommendations+=("Consider adding CONTRIBUTING.md for contributor guidelines")
    fi

    # Check for missing security policy
    if [[ ! -f "${project_dir}/SECURITY.md" ]]; then
        recommendations+=("Consider adding SECURITY.md for security policy and vulnerability reporting")
    fi

    if [[ ${#recommendations[@]} -gt 0 ]]; then
        printf '%s\n' "${recommendations[@]}"
    fi
}

# Get project-specific improvement suggestions
_recommend_by_project_type() {
    local project_type="$1"
    local project_dir="${2:-.}"
    local -a recommendations

    case "$project_type" in
        node|react|nextjs)
            # Check for package.json scripts
            if [[ -f "${project_dir}/package.json" ]]; then
                local scripts
                scripts=$(jq '.scripts | keys[]' "${project_dir}/package.json" 2>/dev/null)
                if ! echo "$scripts" | grep -q "lint\|format"; then
                    recommendations+=("Add linting tools (eslint, prettier) and document in package.json scripts")
                fi
                if [[ "$project_type" == "nextjs" ]] && ! echo "$scripts" | grep -q "dev"; then
                    recommendations+=("Add 'dev' script to package.json for local development")
                fi
            fi
            ;;
        python)
            # Check for test configuration
            if [[ ! -f "${project_dir}/pytest.ini" ]] && [[ ! -f "${project_dir}/pyproject.toml" ]]; then
                recommendations+=("Add pytest configuration (pytest.ini or pyproject.toml) for testing")
            fi
            # Check for requirements.txt
            if [[ ! -f "${project_dir}/requirements.txt" ]] && [[ ! -f "${project_dir}/setup.py" ]]; then
                recommendations+=("Add requirements.txt or setup.py to document dependencies")
            fi
            ;;
        go)
            # Check for go.mod
            if [[ -f "${project_dir}/go.mod" ]]; then
                if [[ ! -f "${project_dir}/go.sum" ]]; then
                    recommendations+=("Run 'go mod tidy' to generate go.sum lockfile")
                fi
            fi
            # Check for Makefile
            if [[ ! -f "${project_dir}/Makefile" ]]; then
                recommendations+=("Consider adding a Makefile for common build/test tasks")
            fi
            ;;
        rust)
            # Check for Cargo.lock
            if [[ -f "${project_dir}/Cargo.toml" ]]; then
                if [[ ! -f "${project_dir}/Cargo.lock" ]]; then
                    recommendations+=("Run 'cargo build' to generate Cargo.lock for reproducible builds")
                fi
            fi
            ;;
    esac

    if [[ ${#recommendations[@]} -gt 0 ]]; then
        printf '%s\n' "${recommendations[@]}"
    fi
}

# Generate all recommendations for a project
recommendations_generate() {
    local project_dir="${1:-.}"
    local agent_file="${2:-}"
    local -a all_recommendations

    # Detect project type
    local project_type
    project_type=$(detect_project_type "$project_dir")

    # Get build command recommendations
    local build_recs
    build_recs=$(_check_build_commands "$agent_file" "$project_dir")
    if [[ -n "$build_recs" ]]; then
        while IFS= read -r rec; do
            if [[ -n "$rec" ]]; then
                all_recommendations+=("BUILD: $rec")
            fi
        done <<< "$build_recs"
    fi

    # Get hook recommendations
    local hook_recs
    hook_recs=$(_recommend_hooks "$project_type" "$project_dir")
    if [[ -n "$hook_recs" ]]; then
        while IFS= read -r rec; do
            if [[ -n "$rec" ]]; then
                all_recommendations+=("HOOKS: $rec")
            fi
        done <<< "$hook_recs"
    fi

    # Get optional files recommendations
    local optional_recs
    optional_recs=$(_check_optional_files "$project_dir")
    if [[ -n "$optional_recs" ]]; then
        while IFS= read -r rec; do
            if [[ -n "$rec" ]]; then
                all_recommendations+=("FILES: $rec")
            fi
        done <<< "$optional_recs"
    fi

    # Get project type recommendations
    local type_recs
    type_recs=$(_recommend_by_project_type "$project_type" "$project_dir")
    if [[ -n "$type_recs" ]]; then
        while IFS= read -r rec; do
            if [[ -n "$rec" ]]; then
                all_recommendations+=("PROJECT: $rec")
            fi
        done <<< "$type_recs"
    fi

    # Output JSON array of recommendations
    if [[ ${#all_recommendations[@]} -gt 0 ]]; then
        jq -n --arg type "$project_type" --argjson recs "$(jq -R -s -c 'split("\n") | map(select(length > 0))' <<< "$(printf '%s\n' "${all_recommendations[@]}")")" \
            '{project_type: $type, recommendations: $recs}'
    else
        jq -n --arg type "$project_type" '{project_type: $type, recommendations: []}'
    fi
}

# Format recommendations for display in doctor output
recommendations_format_for_display() {
    local recommendations_json="$1"

    if echo "$recommendations_json" | jq -e '.recommendations | length == 0' >/dev/null 2>&1; then
        return 0
    fi

    echo ""
    echo "Recommendations:"
    echo ""

    local current_category=""

    # Extract and display recommendations grouped by category
    echo "$recommendations_json" | jq -r '.recommendations[]' | while IFS= read -r rec; do
        # Parse category and message
        local category="${rec%%:*}"
        local message="${rec#*: }"

        # Show category header if changed
        if [[ "$category" != "$current_category" ]]; then
            current_category="$category"
            case "$category" in
                BUILD)
                    echo "  Build Command Documentation:"
                    ;;
                HOOKS)
                    echo "  Hooks Configuration:"
                    ;;
                FILES)
                    echo "  Optional Files:"
                    ;;
                PROJECT)
                    echo "  Project Type Improvements:"
                    ;;
            esac
        fi

        # Display recommendation as a bullet point
        echo "    • $message"
    done
}


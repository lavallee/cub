#!/usr/bin/env bash
#
# cmd_doctor.sh - doctor subcommand implementation
#

# Include guard
if [[ -n "${_CUB_CMD_DOCTOR_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_DOCTOR_SH_LOADED=1

cmd_doctor_help() {
    cat <<'EOF'
cub doctor [options]

Diagnose and optionally fix common cub issues.

USAGE:
  cub doctor              Run diagnostics
  cub doctor --verbose    Show detailed diagnostic info
  cub doctor --fix        Automatically fix detected issues
  cub doctor --dry-run    Show what --fix would do

CHECKS:
  - Environment: jq, harness availability, beads (if used)
  - Configuration: JSON validity, required fields, deprecated options
  - Project structure: prd.json/.beads, .cub/prompt.md, .cub/agent.md
  - Git state: uncommitted files categorized as:
    * session files (progress.txt, fix_plan.md) - safe to commit
    * source code - needs review before committing
    * cruft (.bak, .tmp, .DS_Store, etc.) - safe to clean
    * config files - needs carefully review
  - Task state: tasks stuck in "in_progress"
  - Recommendations: build commands, hooks, optional files, project improvements

FIX ACTIONS:
  --fix will:
  - Commit session files with "chore: commit session files"
  - Suggest adding cruft patterns to .gitignore
  - Report source/config files that need manual review

EXAMPLES:
  # Run diagnostics
  cub doctor

  # See what would be fixed
  cub doctor --dry-run

  # Auto-fix session files
  cub doctor --fix

SEE ALSO:
  cub init      Initialize project
  cub status    Check task progress
  cub --help    Show all commands
EOF
}

_doctor_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

_doctor_warn() {
    echo -e "${YELLOW}[!!]${NC} $1"
}

_doctor_info() {
    echo -e "${BLUE}[--]${NC} $1"
}

_doctor_fail() {
    echo -e "${RED}[XX]${NC} $1"
}

_doctor_check_bash_version() {
    local major minor
    major=$((BASH_VERSINFO[0]))
    minor=$((BASH_VERSINFO[1]))

    if [[ $major -lt 4 ]]; then
        _doctor_fail "Bash version ${major}.${minor} (requires 4.0+)"
        return 1
    else
        _doctor_ok "Bash v${major}.${minor}"
        return 0
    fi
}

_doctor_get_version() {
    local tool="$1"

    case "$tool" in
        jq)
            jq --version 2>/dev/null | sed 's/jq-//'
            ;;
        git)
            git --version 2>/dev/null | sed 's/^git version //'
            ;;
        bd)
            bd --version 2>/dev/null | head -1 || echo "unknown"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

_doctor_install_hint() {
    local tool="$1"
    local os="$(uname -s)"

    case "$tool" in
        bash)
            case "$os" in
                Darwin)
                    echo "  brew install bash"
                    ;;
                Linux)
                    echo "  apt-get install bash  # or: dnf/yum install bash"
                    ;;
                *)
                    echo "  See https://www.gnu.org/software/bash/"
                    ;;
            esac
            ;;
        jq)
            case "$os" in
                Darwin)
                    echo "  brew install jq"
                    ;;
                Linux)
                    echo "  apt-get install jq  # or: dnf/yum install jq"
                    ;;
                *)
                    echo "  See https://github.com/stedolan/jq"
                    ;;
            esac
            ;;
        git)
            case "$os" in
                Darwin)
                    echo "  brew install git"
                    ;;
                Linux)
                    echo "  apt-get install git  # or: dnf/yum install git"
                    ;;
                *)
                    echo "  See https://git-scm.com"
                    ;;
            esac
            ;;
        claude)
            echo "  Install Claude Code from: https://console.anthropic.com"
            ;;
        codex)
            echo "  Install Codex from: https://github.com/openai/codex"
            ;;
        bd)
            echo "  Install beads from: https://github.com/DavidYKay/beads"
            ;;
        *)
            echo "  See project documentation"
            ;;
    esac
}

_doctor_check_env() {
    local issues=0
    echo ""
    echo "System Requirements:"

    # Check Bash version (4.0+)
    if ! _doctor_check_bash_version; then
        _doctor_fail "Install bash 4.0 or newer:"
        _doctor_install_hint "bash"
        ((issues++))
    fi

    # Check git
    if command -v git &>/dev/null; then
        local git_version
        git_version=$(_doctor_get_version "git")
        _doctor_ok "git v${git_version}"
    else
        _doctor_fail "git not installed (required)"
        echo "  Install with:"
        _doctor_install_hint "git"
        ((issues++))
    fi

    # Check jq
    if command -v jq &>/dev/null; then
        local jq_version
        jq_version=$(_doctor_get_version "jq")
        _doctor_ok "jq v${jq_version}"
    else
        _doctor_fail "jq not installed (required)"
        echo "  Install with:"
        _doctor_install_hint "jq"
        ((issues++))
    fi

    # Check for at least one harness
    echo ""
    echo "AI Harnesses:"

    local harness_found=false
    local missing_harnesses=()

    # Check Claude
    if command -v claude &>/dev/null; then
        local claude_version
        claude_version=$(claude --version 2>&1 || echo "unknown")
        _doctor_ok "claude - v${claude_version}"
        harness_found=true
    else
        missing_harnesses+=("claude")
    fi

    # Check Codex
    if command -v codex &>/dev/null; then
        local codex_version
        codex_version=$(codex --version 2>&1 || echo "unknown")
        _doctor_ok "codex - v${codex_version}"
        harness_found=true
    else
        missing_harnesses+=("codex")
    fi

    # Check Gemini
    if command -v gemini &>/dev/null; then
        local gemini_version
        gemini_version=$(gemini --version 2>&1 || echo "unknown")
        _doctor_ok "gemini - v${gemini_version}"
        harness_found=true
    else
        missing_harnesses+=("gemini")
    fi

    # Check OpenCode
    if command -v opencode &>/dev/null; then
        local opencode_version
        opencode_version=$(opencode --version 2>&1 || echo "unknown")
        _doctor_ok "opencode - v${opencode_version}"
        harness_found=true
    else
        missing_harnesses+=("opencode")
    fi

    # Report missing harnesses
    if [[ "$harness_found" == "false" ]]; then
        _doctor_fail "No AI harness found (need claude, codex, gemini, or opencode)"
        ((issues++))
    fi

    # Show installation hints for missing harnesses
    if [[ ${#missing_harnesses[@]} -gt 0 ]]; then
        echo ""
        if [[ "$harness_found" == "false" ]]; then
            echo "  Install one of the missing harnesses:"
        else
            echo "  Optional harnesses not installed:"
        fi
        for harness in "${missing_harnesses[@]}"; do
            echo ""
            echo "  $harness:"
            _doctor_install_hint "$harness" | sed 's/^/    /'
        done
    fi

    # Check beads (optional)
    echo ""
    echo "Optional Tools:"

    if command -v bd &>/dev/null; then
        local bd_version
        bd_version=$(_doctor_get_version "bd")
        _doctor_ok "beads (bd) - ${bd_version}"
    else
        _doctor_info "beads (bd) not installed (optional, required for beads backend)"
        echo "  Install with:"
        _doctor_install_hint "bd"
    fi

    return $issues
}

_doctor_validate_json() {
    local file="$1"

    # Check if file is valid JSON
    if ! jq empty "$file" 2>/dev/null; then
        return 1
    fi
    return 0
}

_doctor_check_required_fields() {
    local file="$1"
    local required_fields="$2"  # JSON array of field names

    local missing_fields=()

    # Check each required field
    while IFS= read -r field; do
        # Quote the field name to handle dots and special characters
        # Use has() to check if key exists at top level
        if ! jq -e "has(\"$field\")" "$file" >/dev/null 2>&1; then
            missing_fields+=("$field")
        fi
    done < <(echo "$required_fields" | jq -r '.[]')

    if [[ ${#missing_fields[@]} -gt 0 ]]; then
        printf '%s\n' "${missing_fields[@]}"
        return 1
    fi

    return 0
}

_doctor_check_deprecated_options() {
    local file="$1"
    local deprecated_map="$2"  # JSON object mapping old names to info

    local found_deprecated=()

    # Check for deprecated options
    while IFS= read -r field; do
        # Quote the field name to handle dots and special characters
        # Use has() to check if key exists
        if jq -e "has(\"$field\")" "$file" >/dev/null 2>&1; then
            found_deprecated+=("$field")
        fi
    done < <(echo "$deprecated_map" | jq -r 'keys[]')

    if [[ ${#found_deprecated[@]} -gt 0 ]]; then
        printf '%s\n' "${found_deprecated[@]}"
        return 1
    fi

    return 0
}

_doctor_check_config() {
    local verbose="${1:-false}"
    local issues=0
    echo ""
    echo "Configuration Files:"

    local global_config
    global_config="$(cub_config_dir)/config.json"

    local project_config="${PROJECT_DIR}/.cub.json"

    # Define deprecated options (these are example deprecated keys)
    local deprecated_options=$(cat <<'EOF'
{
  "harness.priority": "Use 'harness.default' instead",
  "budget.tokens": "Use 'budget.max_tokens_per_task' instead",
  "state.clean": "Use 'state.require_clean' instead"
}
EOF
)

    # Check global config
    if [[ -f "$global_config" ]]; then
        if _doctor_validate_json "$global_config"; then
            _doctor_ok "Global config valid JSON (${global_config})"
        else
            _doctor_fail "Global config has invalid JSON (${global_config})"
            ((issues++))
        fi

        # Check for deprecated options in global config
        local deprecated_found
        deprecated_found=$(_doctor_check_deprecated_options "$global_config" "$deprecated_options")
        if [[ -n "$deprecated_found" ]]; then
            _doctor_warn "Global config has deprecated options:"
            ((issues++))
            if [[ "$verbose" == "true" ]]; then
                while IFS= read -r option; do
                    local msg
                    msg=$(echo "$deprecated_options" | jq -r ".[\"$option\"]")
                    echo "    $option - $msg"
                done <<< "$deprecated_found"
            fi
        fi
    else
        _doctor_info "No global config found (${global_config})"
    fi

    # Check project config
    if [[ -f "$project_config" ]]; then
        if _doctor_validate_json "$project_config"; then
            _doctor_ok "Project config valid JSON (${project_config})"
        else
            _doctor_fail "Project config has invalid JSON (${project_config})"
            ((issues++))
        fi

        # Check for deprecated options in project config
        local deprecated_found
        deprecated_found=$(_doctor_check_deprecated_options "$project_config" "$deprecated_options")
        if [[ -n "$deprecated_found" ]]; then
            _doctor_warn "Project config has deprecated options:"
            ((issues++))
            if [[ "$verbose" == "true" ]]; then
                while IFS= read -r option; do
                    local msg
                    msg=$(echo "$deprecated_options" | jq -r ".[\"$option\"]")
                    echo "    $option - $msg"
                done <<< "$deprecated_found"
            fi
        fi
    else
        _doctor_info "No project config found (${project_config})"
    fi

    return $issues
}

_doctor_check_symlinks() {
    local issues=0

    # Check root-level symlinks for new layout projects
    local layout
    layout=$(detect_layout "${PROJECT_DIR}")

    if [[ "$layout" == "new" ]]; then
        # For new layout, symlinks should point to .cub/
        local symlinks=(
            "CLAUDE.md:.cub/agent.md"
            "AGENTS.md:.cub/agent.md"
            "AGENT.md:.cub/agent.md"
            "PROMPT.md:.cub/prompt.md"
        )

        for symlink_pair in "${symlinks[@]}"; do
            local symlink_name="${symlink_pair%:*}"
            local target="${symlink_pair#*:}"
            local symlink_path="${PROJECT_DIR}/${symlink_name}"

            if [[ -L "$symlink_path" ]]; then
                # It's a symlink, check if it points to the right target
                local actual_target
                actual_target=$(readlink "$symlink_path" 2>/dev/null || echo "")

                if [[ "$actual_target" == "$target" ]]; then
                    _doctor_ok "Symlink ${symlink_name} → ${target}"
                else
                    _doctor_warn "Symlink ${symlink_name} points to ${actual_target} (expected ${target})"
                    ((issues++))
                fi
            elif [[ -f "$symlink_path" ]]; then
                # It's a regular file, not a symlink
                _doctor_warn "${symlink_name} is a regular file, should be a symlink to ${target}"
                ((issues++))
            else
                # Symlink doesn't exist
                _doctor_info "Symlink ${symlink_name} not found (optional for new layout)"
            fi
        done
    fi

    return $issues
}

_doctor_check_gitignore() {
    local issues=0
    local gitignore="${PROJECT_DIR}/.gitignore"

    if [[ ! -f "$gitignore" ]]; then
        _doctor_warn ".gitignore not found"
        ((issues++))
        return $issues
    fi

    # Check for important patterns in .gitignore
    local required_patterns=(
        ".cub/runs"
        ".bv/"
    )

    local missing_patterns=()
    for pattern in "${required_patterns[@]}"; do
        if ! grep -q "^${pattern}" "$gitignore"; then
            missing_patterns+=("$pattern")
        fi
    done

    if [[ ${#missing_patterns[@]} -gt 0 ]]; then
        _doctor_warn ".gitignore missing important patterns"
        ((issues++))
        echo ""
        echo "  Missing patterns in .gitignore:"
        for pattern in "${missing_patterns[@]}"; do
            echo "    $pattern"
        done
    else
        _doctor_ok ".gitignore configured with required patterns"
    fi

    return $issues
}

_doctor_check_project() {
    local issues=0
    echo ""
    echo "Project Structure:"

    # Check for task backend
    if [[ -d "${PROJECT_DIR}/.beads" ]]; then
        local task_count
        task_count=$(bd list --json 2>/dev/null | jq 'length' 2>/dev/null || echo "?")
        _doctor_ok ".beads/ directory found (${task_count} tasks)"
    elif [[ -f "${PROJECT_DIR}/prd.json" ]]; then
        local task_count
        task_count=$(jq '.tasks | length' "${PROJECT_DIR}/prd.json" 2>/dev/null || echo "?")
        _doctor_ok "prd.json found (${task_count} tasks)"
    else
        _doctor_warn "No task backend found (need prd.json or .beads/)"
        ((issues++))
    fi

    # Detect layout and check files
    local layout
    layout=$(detect_layout "${PROJECT_DIR}")
    local prompt_file
    prompt_file=$(get_prompt_file "${PROJECT_DIR}")
    local agent_file
    agent_file=$(get_agent_file "${PROJECT_DIR}")

    # Check prompt.md
    if [[ -f "$prompt_file" ]]; then
        _doctor_ok "prompt.md found (${layout} layout)"
    else
        _doctor_warn "prompt.md not found at ${prompt_file} (run 'cub init')"
        ((issues++))
    fi

    # Check agent.md
    if [[ -f "$agent_file" ]]; then
        _doctor_ok "agent.md found (${layout} layout)"
    else
        _doctor_warn "agent.md not found at ${agent_file} (run 'cub init')"
        ((issues++))
    fi

    # Check .cub/ directory
    if [[ -d "${PROJECT_DIR}/.cub" ]]; then
        _doctor_ok ".cub/ directory exists"
    else
        _doctor_info ".cub/ directory not found (will be created on first run)"
    fi

    # Check symlinks
    _doctor_check_symlinks || issues=$((issues + $?))

    # Check .gitignore
    _doctor_check_gitignore || issues=$((issues + $?))

    return $issues
}

_doctor_check_git() {
    local verbose="${1:-false}"
    local issues=0
    echo ""
    echo "Git State:"

    # Check if in git repo
    if ! git_in_repo; then
        _doctor_info "Not a git repository"
        return 0
    fi

    _doctor_ok "Git repository detected"

    # Check for uncommitted changes
    local changes_json
    changes_json=$(git_categorize_changes)

    if [[ "$changes_json" == *'"error"'* ]]; then
        _doctor_fail "Error categorizing changes"
        return 1
    fi

    # Extract counts
    local session_count source_count cruft_count config_count unknown_count
    session_count=$(echo "$changes_json" | jq '.session | length')
    source_count=$(echo "$changes_json" | jq '.source | length')
    cruft_count=$(echo "$changes_json" | jq '.cruft | length')
    config_count=$(echo "$changes_json" | jq '.config | length')
    unknown_count=$(echo "$changes_json" | jq '.unknown | length')

    local total_count=$((session_count + source_count + cruft_count + config_count + unknown_count))

    # Check for cub artifacts (.beads/ and .cub/) separately
    local cub_artifacts
    cub_artifacts=$(git status --porcelain -u 2>/dev/null | grep -E '^.. \.(beads|cub)/' || true)
    local cub_artifact_count=0
    if [[ -n "$cub_artifacts" ]]; then
        cub_artifact_count=$(echo "$cub_artifacts" | wc -l | tr -d ' ')
    fi

    if [[ $total_count -eq 0 && $cub_artifact_count -eq 0 ]]; then
        _doctor_ok "Working directory clean"
        return 0
    fi

    # Report cub artifacts if present
    if [[ $cub_artifact_count -gt 0 ]]; then
        _doctor_warn "Cub artifacts need committing (${cub_artifact_count} files)"
        ((issues++))
        echo ""
        echo "  Cub artifacts (safe to commit with --fix):"
        # Use here-string to avoid subshell from pipe
        while IFS= read -r line; do
            echo "    $line"
        done <<< "$cub_artifacts"
        # Store for fix phase (exported so it survives function calls)
        export _DOCTOR_CUB_ARTIFACTS="$cub_artifacts"
    fi

    if [[ $total_count -eq 0 ]]; then
        # Only cub artifacts, no other changes
        return $issues
    fi

    # Report session files
    if [[ $session_count -gt 0 ]]; then
        _doctor_warn "Session files modified (${session_count} files)"
        ((issues++))
        if [[ "$verbose" == "true" ]]; then
            echo ""
            echo "  Session files (safe to commit with --fix):"
            echo "$changes_json" | jq -r '.session[] | "    " + .'
        fi
    fi

    # Report source code files
    if [[ $source_count -gt 0 ]]; then
        _doctor_warn "Source code files modified (${source_count} files)"
        ((issues++))
        if [[ "$verbose" == "true" ]]; then
            echo ""
            echo "  Source files (review before committing):"
            echo "$changes_json" | jq -r '.source[] | "    " + .'
        fi
    fi

    # Report cruft files
    if [[ $cruft_count -gt 0 ]]; then
        _doctor_warn "Cruft files present (${cruft_count} files)"
        ((issues++))
        if [[ "$verbose" == "true" ]]; then
            echo ""
            echo "  Cruft files (safe to remove):"
            echo "$changes_json" | jq -r '.cruft[] | "    " + .'
        fi
    fi

    # Report config files
    if [[ $config_count -gt 0 ]]; then
        _doctor_warn "Config files modified (${config_count} files)"
        ((issues++))
        if [[ "$verbose" == "true" ]]; then
            echo ""
            echo "  Config files (review carefully):"
            echo "$changes_json" | jq -r '.config[] | "    " + .'
        fi
    fi

    # Report unknown files
    if [[ $unknown_count -gt 0 ]]; then
        _doctor_warn "Unknown file changes (${unknown_count} files)"
        ((issues++))
        if [[ "$verbose" == "true" ]]; then
            echo ""
            echo "  Unknown files (review carefully):"
            echo "$changes_json" | jq -r '.unknown[] | "    " + .'
        fi
    fi

    return $issues
}

_doctor_check_tasks() {
    local issues=0
    echo ""
    echo "Task State:"

    local prd="${PROJECT_DIR}/prd.json"
    local backend
    backend=$(get_backend "${PROJECT_DIR}")

    # Check for tasks stuck in progress
    local in_progress
    in_progress=$(get_in_progress_tasks "$prd")

    if [[ -z "$in_progress" || "$in_progress" == "[]" ]]; then
        _doctor_ok "No tasks stuck in progress"
    else
        local count
        count=$(echo "$in_progress" | jq 'length')
        _doctor_warn "Found ${count} tasks in progress"
        ((issues++))
        echo ""
        echo "  In-progress tasks:"
        echo "$in_progress" | jq -r '.[] | "    " + .id + " (" + (.title // "no title") + ")"'
        echo ""
        echo "  You may want to reset these tasks to open"
    fi

    return $issues
}

_doctor_fix() {
    local dry_run="${1:-false}"
    local issues=0

    echo ""
    echo "Fix Mode:"

    if ! git_in_repo; then
        _doctor_info "Not a git repository, skipping auto-fix"
        return 0
    fi

    # Commit session files if present
    local changes_json
    changes_json=$(git_categorize_changes)
    local session_count
    session_count=$(echo "$changes_json" | jq '.session | length')

    if [[ $session_count -gt 0 ]]; then
        if [[ "$dry_run" == "true" ]]; then
            _doctor_info "Would commit ${session_count} session files"
        else
            log_info "Committing session files..."
            if git_commit_session_files "doctor"; then
                _doctor_ok "Committed session files"
            else
                _doctor_warn "Failed to commit session files"
                ((issues++))
            fi
        fi
    else
        _doctor_ok "No session files to commit"
    fi

    # Commit cub artifacts if present
    if [[ -n "${_DOCTOR_CUB_ARTIFACTS:-}" ]]; then
        if [[ "$dry_run" == "true" ]]; then
            _doctor_info "Would commit cub artifacts"
        else
            log_info "Committing cub artifacts..."
            if git_commit_cub_artifacts "doctor"; then
                _doctor_ok "Committed cub artifacts"
            else
                _doctor_warn "Failed to commit cub artifacts"
                ((issues++))
            fi
        fi
    fi

    # Report source/config files that need manual review
    local source_count config_count unknown_count
    source_count=$(echo "$changes_json" | jq '.source | length')
    config_count=$(echo "$changes_json" | jq '.config | length')
    unknown_count=$(echo "$changes_json" | jq '.unknown | length')

    if [[ $source_count -gt 0 || $config_count -gt 0 || $unknown_count -gt 0 ]]; then
        _doctor_warn "Manual review needed for ${source_count} source, ${config_count} config, ${unknown_count} unknown files"
        ((issues++))
    fi

    return $issues
}

_doctor_check_recommendations() {
    local verbose="${1:-false}"
    echo ""
    echo "Recommendations:"

    # Source recommendations library
    source "${CUB_DIR}/lib/recommendations.sh"

    local agent_file
    agent_file=$(get_agent_file "${PROJECT_DIR}")

    # Generate recommendations
    local recommendations_json
    recommendations_json=$(recommendations_generate "${PROJECT_DIR}" "$agent_file")

    # Check if we have any recommendations
    local recommendation_count
    recommendation_count=$(echo "$recommendations_json" | jq '.recommendations | length')

    if [[ $recommendation_count -eq 0 ]]; then
        _doctor_ok "No recommendations at this time"
        return 0
    fi

    # Display recommendations by category
    local current_category=""
    echo "$recommendations_json" | jq -r '.recommendations[]' | while IFS= read -r rec; do
        if [[ -z "$rec" ]]; then
            continue
        fi

        # Parse category and message
        local category="${rec%%:*}"
        local message="${rec#*: }"

        # Show category header if changed
        case "$category" in
            BUILD)
                if [[ "$current_category" != "BUILD" ]]; then
                    echo ""
                    echo "  Build Commands:"
                    current_category="BUILD"
                fi
                echo "    • $message"
                ;;
            HOOKS)
                if [[ "$current_category" != "HOOKS" ]]; then
                    echo ""
                    echo "  Hooks Configuration:"
                    current_category="HOOKS"
                fi
                echo "    • $message"
                ;;
            FILES)
                if [[ "$current_category" != "FILES" ]]; then
                    echo ""
                    echo "  Optional Files:"
                    current_category="FILES"
                fi
                echo "    • $message"
                ;;
            PROJECT)
                if [[ "$current_category" != "PROJECT" ]]; then
                    echo ""
                    echo "  Project Improvements:"
                    current_category="PROJECT"
                fi
                echo "    • $message"
                ;;
        esac
    done

    return 0
}

cmd_doctor() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_doctor_help
        return 0
    fi

    local verbose="false"
    local fix="false"
    local dry_run="false"

    # Parse flags
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --verbose)
                verbose="true"
                shift
                ;;
            --fix)
                fix="true"
                shift
                ;;
            --dry-run)
                dry_run="true"
                shift
                ;;
            *)
                _log_error_console "Unknown flag: $1"
                _log_error_console "Usage: cub doctor [--verbose] [--fix] [--dry-run]"
                return 1
                ;;
        esac
    done

    # Run checks
    local total_issues=0
    _doctor_check_env || total_issues=$((total_issues + $?))
    _doctor_check_config "$verbose" || total_issues=$((total_issues + $?))
    _doctor_check_project || total_issues=$((total_issues + $?))
    _doctor_check_git "$verbose" || total_issues=$((total_issues + $?))
    _doctor_check_tasks || total_issues=$((total_issues + $?))
    _doctor_check_recommendations "$verbose" || total_issues=$((total_issues + $?))

    # Run fixes if requested
    if [[ "$fix" == "true" || "$dry_run" == "true" ]]; then
        _doctor_fix "$dry_run" || total_issues=$((total_issues + $?))
    fi

    # Summary
    echo ""
    if [[ $total_issues -eq 0 ]]; then
        _doctor_ok "No issues found"
    else
        _doctor_warn "Found ${total_issues} issue(s)"
        if [[ "$fix" != "true" ]]; then
            echo ""
            echo "Run 'cub doctor --fix' to auto-fix some issues"
            echo "Run 'cub doctor --dry-run' to preview fixes"
        fi
    fi

    return 0
}

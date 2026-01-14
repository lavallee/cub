#!/usr/bin/env bash
#
# cmd_run.sh - run loop and prompt generation
#

# Include guard
if [[ -n "${_CUB_CMD_RUN_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_RUN_SH_LOADED=1

cmd_run_help() {
    cat <<'EOF'
cub run [<options>]

Run the autonomous coding loop to complete tasks.

USAGE:
  cub run              Run continuous loop (default behavior)
  cub run --once       Run exactly one iteration then exit
  cub run --ready      Show ready (unblocked) tasks without running
  cub run --plan       Run planning mode to analyze codebase
  cub run --review-plans  Validate plan completeness, dependencies, and feasibility

EXECUTION OPTIONS:
  --once, -1            Run single iteration then exit
  --ready, -r           List tasks ready to work on
  --plan, -p            Generate fix_plan.md with code analysis
  --review-plans        Full validation suite (completeness, feasibility, dependencies)
  --review-plans --json Output review results as JSON instead of markdown
  --push                Push completed work to remote (experimental)

FILTERING:
  --epic <id>           Only work on tasks in this epic
  --label <name>        Only work on tasks with this label

MODEL & HARNESS:
  --model <name>        Claude model: opus, sonnet, haiku
  --harness <name>      AI harness: claude, codex, gemini, opencode

RELIABILITY:
  --require-clean       Force clean git state before starting
  --no-require-clean    Disable clean state check

BUDGET & LIMITS:
  --budget <tokens>     Token budget limit (e.g., 1000000)
  --name <name>         Session name for tracking

DEBUG:
  --debug, -d           Show detailed execution logs
  --stream              Stream harness output in real-time

EXAMPLES:
  # Run continuous loop
  cub run

  # Run once with budget limit
  cub run --once --budget 1000000

  # View ready tasks without running
  cub run --ready

  # Work on specific epic only
  cub run --epic backend-v2

  # Use Sonnet with live output
  cub run --model sonnet --stream

  # Run with detailed debugging
  cub run --once --debug

SEE ALSO:
  cub --help       Show all commands
  cub status       Check current progress
  cub artifacts    Access task output files
EOF
}

cmd_run() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_run_help
        return 0
    fi

    # Parse run-specific flags
    local args=()
    local run_once=false
    local run_plan=false
    local run_ready=false
    local run_review_plans=false
    local review_plans_json=false

    # Local copies of flag variables (can be overridden per-run)
    local cmd_epic="${EPIC}"
    local cmd_label="${LABEL}"
    local cmd_model="${MODEL}"
    local cmd_budget="${BUDGET}"
    local cmd_require_clean="${REQUIRE_CLEAN}"
    local cmd_session_name="${SESSION_NAME}"
    local cmd_push=false

    for arg in "$@"; do
        case "$arg" in
            --once|-1)
                run_once=true
                ;;
            --plan|-p)
                run_plan=true
                ;;
            --ready|-r)
                run_ready=true
                ;;
            --review-plans)
                run_review_plans=true
                ;;
            --json)
                review_plans_json=true
                ;;
            --push)
                cmd_push=true
                ;;
            --require-clean)
                cmd_require_clean="true"
                export CUB_REQUIRE_CLEAN="true"
                log_info "Clean state enforcement enabled via CLI flag"
                ;;
            --no-require-clean)
                cmd_require_clean="false"
                export CUB_REQUIRE_CLEAN="false"
                log_info "Clean state enforcement disabled via CLI flag"
                ;;
            --model=*)
                cmd_model="${arg#--model=}"
                export CUB_MODEL="$cmd_model"
                ;;
            --model)
                _next_is_model=true
                ;;
            --epic=*)
                cmd_epic="${arg#--epic=}"
                export CUB_EPIC="$cmd_epic"
                ;;
            --epic)
                _next_is_epic=true
                ;;
            --label=*)
                cmd_label="${arg#--label=}"
                export CUB_LABEL="$cmd_label"
                ;;
            --label)
                _next_is_label=true
                ;;
            --budget=*)
                cmd_budget="${arg#--budget=}"
                export CUB_BUDGET="$cmd_budget"
                ;;
            --budget)
                _next_is_budget=true
                ;;
            --name=*)
                cmd_session_name="${arg#--name=}"
                export CUB_SESSION_NAME="$cmd_session_name"
                ;;
            --name)
                _next_is_name=true
                ;;
            *)
                # Handle deferred flag values
                if [[ "${_next_is_model:-}" == "true" ]]; then
                    cmd_model="$arg"
                    export CUB_MODEL="$cmd_model"
                    _next_is_model=false
                elif [[ "${_next_is_epic:-}" == "true" ]]; then
                    cmd_epic="$arg"
                    export CUB_EPIC="$cmd_epic"
                    _next_is_epic=false
                elif [[ "${_next_is_label:-}" == "true" ]]; then
                    cmd_label="$arg"
                    export CUB_LABEL="$cmd_label"
                    _next_is_label=false
                elif [[ "${_next_is_budget:-}" == "true" ]]; then
                    cmd_budget="$arg"
                    export CUB_BUDGET="$cmd_budget"
                    _next_is_budget=false
                elif [[ "${_next_is_name:-}" == "true" ]]; then
                    cmd_session_name="$arg"
                    export CUB_SESSION_NAME="$cmd_session_name"
                    _next_is_name=false
                else
                    args+=("$arg")
                fi
                ;;
        esac
    done

    # Clean up flag parsing state
    unset _next_is_model
    unset _next_is_epic
    unset _next_is_label
    unset _next_is_budget
    unset _next_is_name

    # Update global variables if they were set via cmd_run flags
    EPIC="$cmd_epic"
    LABEL="$cmd_label"
    MODEL="$cmd_model"
    BUDGET="$cmd_budget"
    REQUIRE_CLEAN="$cmd_require_clean"
    SESSION_NAME="$cmd_session_name"
    PUSH="$cmd_push"

    # Initialize budget if provided via CLI, environment, or config
    # Get budget from: CLI flag > environment > config file
    local budget_limit="${BUDGET:-$(config_get_or "budget.limit" "")}"
    if [[ -n "$budget_limit" ]]; then
        if budget_init "$budget_limit"; then
            log_info "Budget initialized: ${budget_limit} tokens"
        else
            log_warn "Failed to initialize budget with value: ${budget_limit}"
        fi
    fi

    # Load iteration limits from config
    local max_task_iterations
    max_task_iterations=$(config_get_or "guardrails.max_task_iterations" "3")
    if budget_set_max_task_iterations "$max_task_iterations"; then
        log_debug "Max task iterations: ${max_task_iterations}"
    else
        log_warn "Failed to set max task iterations"
    fi

    local max_run_iterations
    max_run_iterations=$(config_get_or "guardrails.max_run_iterations" "50")
    if budget_set_max_run_iterations "$max_run_iterations"; then
        log_debug "Max run iterations: ${max_run_iterations}"
    else
        log_warn "Failed to set max run iterations"
    fi

    # Check if project is initialized, prompt to init if not
    prompt_init_if_needed

    validate_project

    # Execute based on mode
    if [[ "$run_ready" == "true" ]]; then
        show_ready
    elif [[ "$run_review_plans" == "true" ]]; then
        if [[ "$review_plans_json" == "true" ]]; then
            run_review_plans --json
        else
            run_review_plans
        fi
    elif [[ "$run_plan" == "true" ]]; then
        run_planning
    elif [[ "$run_once" == "true" ]]; then
        run_iteration
    else
        run_loop
    fi
}

generate_system_prompt() {
    local prompt_file
    prompt_file=$(get_prompt_file "${PROJECT_DIR}")
    cat "$prompt_file"
}

generate_task_prompt() {
    local task_json="$1"

    # Extract task details
    local task_id
    task_id=$(echo "$task_json" | jq -r '.id')
    local task_title
    task_title=$(echo "$task_json" | jq -r '.title')
    local task_type
    task_type=$(echo "$task_json" | jq -r '.type')
    local task_desc
    task_desc=$(echo "$task_json" | jq -r '.description')
    local task_criteria
    task_criteria=$(echo "$task_json" | jq -r '.acceptanceCriteria // [] | join("\n- ")')

    # Parse acceptance criteria from description (markdown checkboxes)
    local desc_criteria=""
    desc_criteria=$(parse_acceptance_criteria "$task_desc" 2>/dev/null || true)

    # Check for failure context (for retry mode)
    local failure_context=""
    failure_context=$(failure_get_context "$task_id" 2>/dev/null)

    # Generate focused task prompt (minimal - just the task)
    cat <<EOF
## CURRENT TASK

Task ID: ${task_id}
Type: ${task_type}
Title: ${task_title}

Description:
${task_desc}
EOF

    # Include acceptance criteria section
    # Prioritize explicit acceptanceCriteria array, but also include parsed checkboxes
    if [[ -n "$task_criteria" && "$task_criteria" != "-" ]]; then
        cat <<EOF

Acceptance Criteria:
- ${task_criteria}
EOF
    elif [[ -n "$desc_criteria" ]]; then
        cat <<EOF

Acceptance Criteria (from description checkboxes):
EOF
        echo "$desc_criteria" | while IFS= read -r criterion; do
            echo "- $criterion"
        done
    fi

    # Add failure context if this is a retry
    if [[ -n "$failure_context" ]]; then
        cat <<EOF

## RETRY CONTEXT

${failure_context}
EOF
    fi

    # Add completion instructions (backend-aware)
    local backend
    backend=$(get_backend)
    if [[ "$backend" == "beads" ]]; then
        cat <<EOF

When complete:
1. Run feedback loops (typecheck, test, lint)
2. Mark task complete: bd close ${task_id}
3. Commit: ${task_type}(${task_id}): ${task_title}
4. Append learnings to progress.txt

Note: This project uses the beads task backend. Use 'bd' commands for task management:
- bd close ${task_id}  - Mark this task complete
- bd show ${task_id}   - Check task status
- bd list              - See all tasks
EOF
    else
        cat <<EOF

When complete:
1. Run feedback loops (typecheck, test, lint)
2. Update prd.json: set status to "closed" for ${task_id}
3. Commit: ${task_type}(${task_id}): ${task_title}
4. Append learnings to progress.txt
EOF
    fi
}

run_iteration() {
    local prd="${PROJECT_DIR}/prd.json"
    log_debug "Starting iteration"

    # Check run iteration limit before starting task
    if ! budget_check_run_iterations; then
        local current
        current=$(budget_get_run_iterations)
        local max
        max=$(budget_get_max_run_iterations)
        log_warn "Run iteration limit exceeded (${current}/${max})"
        log_info "Stopping run due to iteration limit"
        return 1
    fi

    # Initialize session if not already initialized
    if ! session_is_initialized; then
        log_debug "Initializing session..."
        if [[ -n "$SESSION_NAME" ]]; then
            session_init --name "$SESSION_NAME"
        else
            session_init
        fi

        if [[ $? -ne 0 ]]; then
            log_warn "Failed to initialize session"
        else
            local session_name
            session_name=$(session_get_name)
            local session_id
            session_id=$(session_get_id)
            log_debug "Session: ${session_name} (${session_id})"
        fi
    fi

    # Initialize logger if not already initialized
    if [[ -z "$(logger_get_file)" ]]; then
        local project_name
        project_name=$(basename "$PROJECT_DIR")
        local session_id
        session_id=$(session_get_id)

        if logger_init "$project_name" "$session_id"; then
            log_debug "Logger initialized: $(logger_get_file)"
        else
            log_warn "Failed to initialize logger"
        fi
    fi

    # Initialize artifacts for this run if not already initialized
    if session_is_initialized; then
        local run_dir
        run_dir=$(artifacts_get_run_dir 2>/dev/null) || true
        if [[ -n "$run_dir" ]] && [[ ! -f "${run_dir}/run.json" ]]; then
            log_debug "Initializing artifacts..."
            if artifacts_init_run; then
                local artifacts_path
                artifacts_path=$(artifacts_get_run_dir)
                log_debug "Artifacts initialized: ${artifacts_path}"
            else
                log_warn "Failed to initialize artifacts"
            fi
        fi
    fi

    # Initialize git run branch if in a git repository (only if not already initialized)
    if git_in_repo; then
        local current_branch
        current_branch=$(git_get_run_branch 2>/dev/null) || true
        if [[ -z "$current_branch" ]]; then
            log_debug "Initializing git run branch..."
            local session_name
            session_name=$(session_get_name)
            if git_init_run_branch "$session_name"; then
                local branch_name
                branch_name=$(git_get_run_branch)
                log_info "Git branch: ${branch_name}"
            else
                log_warn "Failed to initialize git run branch"
            fi
        fi
    else
        log_debug "Not in a git repository, skipping git operations"
    fi

    # Check for in-progress tasks first (resume interrupted work)
    # Respects --epic and --label filters
    local current_task
    log_debug "Checking for in-progress tasks..."
    current_task=$(get_in_progress_task "$prd" "$EPIC" "$LABEL")
    log_debug "In-progress query result: ${current_task:0:100}..."

    if [[ -n "$current_task" && "$current_task" != "null" ]]; then
        local task_id
        task_id=$(echo "$current_task" | jq -r '.id')
        local task_title
        task_title=$(echo "$current_task" | jq -r '.title')
        local task_type
        task_type=$(echo "$current_task" | jq -r '.type')

        # Verify the in-progress task is not blocked
        if is_task_ready "$prd" "$task_id"; then
            log_warn "Resuming in-progress task: ${task_id}"
            log_info "  ${task_type}: ${task_title}"
            log_debug "Task JSON: $current_task"
        else
            log_warn "In-progress task ${task_id} is blocked, resetting to open"
            update_task_status "$prd" "$task_id" "open"
            current_task=""
        fi
    fi

    # Find next ready task if no valid in-progress task
    if [[ -z "$current_task" || "$current_task" == "null" ]]; then
        # Find next ready task
        log_debug "No in-progress tasks, finding ready tasks..."
        log_debug "Current _TASK_BACKEND: ${_TASK_BACKEND}"
        local ready_tasks
        ready_tasks=$(get_ready_tasks "$prd" "$EPIC" "$LABEL")
        log_debug "Ready tasks result: ${ready_tasks:0:200}..."

        if [[ -z "$ready_tasks" || "$ready_tasks" == "[]" ]]; then
            echo "[cub] NO READY TASKS: ready_tasks is empty or [], checking remaining..." >&2
            # Check if we're done
            local open_count
            open_count=$(get_remaining_count "$prd")
            echo "[cub] OPEN COUNT: open_count='$open_count'" >&2
            log_debug "Open task count: ${open_count}"

            # Handle error case (-1 or empty means backend query failed)
            if [[ -z "$open_count" || "$open_count" == "-1" ]]; then
                log_warn "Failed to get task count, retrying next iteration"
                return 1
            elif [[ "$open_count" -eq 0 ]]; then
                echo "[cub] EXIT REASON: open_count is 0 in run_iteration" >&2
                log_success "All tasks complete!"
                return 0
            else
                _log_error_console "No ready tasks but ${open_count} tasks not closed. Check dependencies."
                return 1
            fi
        fi

        # Pick highest priority ready task
        current_task=$(echo "$ready_tasks" | jq 'first')
        local task_id
        task_id=$(echo "$current_task" | jq -r '.id')
        local task_title
        task_title=$(echo "$current_task" | jq -r '.title')
        local task_type
        task_type=$(echo "$current_task" | jq -r '.type')
        local task_priority
        task_priority=$(echo "$current_task" | jq -r '.priority')

        log_info "Selected task: ${task_id} [${task_priority}]"
        log_info "  ${task_type}: ${task_title}"
        log_debug "Task JSON: $current_task"

        # Mark as in_progress (with assignee for beads backend)
        log_debug "Claiming task..."
        local session_name
        session_name=$(session_get_name)
        claim_task "$prd" "$task_id" "$session_name"
        log_debug "Task claimed"
    fi

    # Check for model: or complexity: labels and set CUB_MODEL
    # Works for claude and codex harnesses
    local harness
    harness=$(harness_get)
    if [[ "$harness" == "claude" || "$harness" == "codex" ]]; then
        local task_model
        # First check for explicit model: label
        task_model=$(echo "$current_task" | jq -r '.labels // [] | .[] | select(startswith("model:")) | split(":")[1]' 2>/dev/null | head -1)

        # If no model label, check for complexity: label and map to model
        if [[ -z "$task_model" ]]; then
            local complexity
            complexity=$(echo "$current_task" | jq -r '.labels // [] | .[] | select(startswith("complexity:")) | split(":")[1]' 2>/dev/null | head -1)
            if [[ -n "$complexity" ]]; then
                if [[ "$harness" == "claude" ]]; then
                    # Claude: low->haiku, medium->sonnet, high->opus
                    case "$complexity" in
                        low|simple) task_model="haiku" ;;
                        high|complex) task_model="opus" ;;
                        *) task_model="sonnet" ;;
                    esac
                elif [[ "$harness" == "codex" ]]; then
                    # Codex: low->gpt-4o-mini, medium->default, high->o3
                    case "$complexity" in
                        low|simple) task_model="gpt-4o-mini" ;;
                        high|complex) task_model="o3" ;;
                        *) task_model="" ;; # Use default
                    esac
                fi
                [[ -n "$task_model" ]] && log_info "  Model from complexity (${complexity}): ${task_model}"
            fi
        else
            log_info "  Model from label: ${task_model}"
        fi

        if [[ -n "$task_model" ]]; then
            export CUB_MODEL="$task_model"
        fi
    fi

    # Generate prompts
    log_debug "Generating prompts..."
    local system_prompt
    system_prompt=$(generate_system_prompt)
    local task_prompt
    task_prompt=$(generate_task_prompt "$current_task")

    local sys_bytes
    sys_bytes=$(echo "$system_prompt" | wc -c)
    local task_bytes
    task_bytes=$(echo "$task_prompt" | wc -c)
    log_debug "System prompt: ${sys_bytes} bytes (via --append-system-prompt)"
    log_debug "Task prompt: ${task_bytes} bytes (via stdin)"

    # Show prompts in debug mode
    if [[ "$DEBUG" == "true" ]]; then
        echo ""
        log_debug "=== SYSTEM PROMPT ==="
        echo -e "${DIM}$system_prompt${NC}" >&2
        log_debug "=== TASK PROMPT ==="
        echo -e "${DIM}$task_prompt${NC}" >&2
        log_debug "===================="
        echo ""
    fi

    log_info "Running ${harness}..."
    echo ""

    if [[ "$DEBUG" == "true" ]]; then
        # Pre-flight check
        log_debug "Pre-flight: ${harness} version"
        local version_output
        version_output=$(harness_version 2>&1) && log_debug "Version: ${version_output}" || log_debug "WARNING: version check failed"
        log_debug "Binary: $(which ${harness})"
    fi

    # Extract task details for logging
    local task_id
    task_id=$(echo "$current_task" | jq -r '.id')
    local task_title
    task_title=$(echo "$current_task" | jq -r '.title')
    local task_priority
    task_priority=$(echo "$current_task" | jq -r '.priority // "normal"')

    # Check task iteration limit before attempting task
    if ! budget_check_task_iterations "$task_id"; then
        local current
        current=$(budget_get_task_iterations "$task_id")
        local max
        max=$(budget_get_max_task_iterations)
        log_warn "Task ${task_id} iteration limit exceeded (${current}/${max})"
        log_info "Marking task as failed and moving on"
        update_task_status "$prd" "$task_id" "failed"
        return 1
    fi

    # Start task artifacts
    if session_is_initialized; then
        log_debug "Starting task artifacts for ${task_id}..."
        if artifacts_start_task "$task_id" "$task_title" "$task_priority"; then
            local artifacts_path
            artifacts_path=$(artifacts_get_path "$task_id")
            log_debug "Task artifacts: ${artifacts_path}"
        else
            log_warn "Failed to start task artifacts"
        fi
    fi

    # Log acceptance criteria for this task
    if [[ "$DEBUG" == "true" ]]; then
        verify_acceptance_criteria "$task_id" "$prd" 2>/dev/null | while IFS= read -r line; do
            log_debug "$line"
        done
    fi

    # Increment task iteration counter
    budget_increment_task_iterations "$task_id"
    local task_iteration
    task_iteration=$(budget_get_task_iterations "$task_id")
    local max_task
    max_task=$(budget_get_max_task_iterations)
    local run_iteration
    run_iteration=$(budget_get_run_iterations)
    local max_run
    max_run=$(budget_get_max_run_iterations)
    log_info "Task ${task_id} iteration ${task_iteration}/${max_task} (run ${run_iteration}/${max_run})"

    # Log task start
    log_task_start "$task_id" "$task_title" "$harness"

    # Run pre-task hooks
    log_debug "Running pre-task hooks..."
    hooks_set_task_context "$task_id" "$task_title"
    hooks_run "pre-task"
    log_debug "Pre-task hooks complete"

    # Run harness with the prompt via abstraction layer
    local start_time
    start_time=$(date +%s)
    local exit_code=0
    log_debug "Execution start: $(date)"

    if [[ "$DEBUG" == "true" ]]; then
        # Save prompts to temp files for manual testing
        local tmp_sys
        tmp_sys=$(mktemp)
        local tmp_task
        tmp_task=$(mktemp)
        echo "$system_prompt" > "$tmp_sys"
        echo "$task_prompt" > "$tmp_task"
        log_debug "System prompt: ${tmp_sys}"
        log_debug "Task prompt: ${tmp_task}"
        log_debug ">>> Prompts saved for debugging"
        log_debug ""
        log_debug "--- HARNESS START (${harness}) ---"
    fi

    # Set up harness output logging to artifacts
    local harness_log_file="${TMPDIR:-/tmp}/cub_harness_log_$$"
    export CUB_HARNESS_LOG="$harness_log_file"

    # Invoke harness via abstraction layer
    if [[ "$STREAM" == "true" ]]; then
        log_info "Streaming ${harness} output..."
        harness_invoke_streaming "$system_prompt" "$task_prompt" "$DEBUG"
        exit_code=$?
    else
        harness_invoke "$system_prompt" "$task_prompt" "$DEBUG"
        exit_code=$?
    fi

    # Capture harness output to artifacts
    if session_is_initialized && [[ -f "$harness_log_file" ]]; then
        log_debug "Capturing harness output to artifacts..."
        if artifacts_capture_harness_output "$task_id" "$harness_log_file" "$task_iteration"; then
            log_debug "Harness output captured"
        else
            log_warn "Failed to capture harness output"
        fi
        rm -f "$harness_log_file"
    fi
    unset CUB_HARNESS_LOG

    if [[ "$DEBUG" == "true" ]]; then
        log_debug "--- HARNESS END (${harness}) ---"

        # Cleanup on success, keep on failure
        if [[ $exit_code -eq 0 ]]; then
            rm -f "$tmp_sys" "$tmp_task"
        else
            log_debug "Keeping prompt files for debugging"
            log_debug "  System: ${tmp_sys}"
            log_debug "  Task: ${tmp_task}"
        fi
    fi

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_debug "Execution end: $(date)"
    log_debug "Duration: ${duration} seconds"
    log_debug "Exit code: ${exit_code}"

    # Extract token usage from harness
    local tokens_used=0
    tokens_used=$(harness_get_total_tokens)
    log_debug "Tokens used: ${tokens_used}"

    # Record token usage in budget if budget is initialized
    local budget_remaining=""
    local budget_total=""
    if [[ -f "${TMPDIR:-/tmp}/cub_budget_limit_$$" ]]; then
        log_debug "Recording ${tokens_used} tokens to budget"
        budget_record "$tokens_used"
        budget_remaining=$(budget_remaining)
        budget_total=$(budget_get_limit)
        log_debug "Budget: ${budget_remaining} remaining of ${budget_total}"

        # Check if warning threshold has been crossed
        local warn_at
        warn_at=$(config_get_or "budget.warn_at" "80")
        if budget_check_warning "$warn_at"; then
            : # No warning triggered
        else
            # Warning was just triggered - log it once
            if [[ "$budget_total" -gt 0 ]]; then
                local used
                used=$(budget_get_used)
                local percentage=$((used * 100 / budget_total))
                log_warn "Budget warning: approaching limit (${percentage}% used, ${budget_remaining} tokens remaining)"
            fi
        fi
    fi

    # Log task end with budget information
    if [[ -n "$budget_remaining" && -n "$budget_total" ]]; then
        log_task_end "$task_id" "$exit_code" "$duration" "$tokens_used" "$budget_remaining" "$budget_total"
    else
        log_task_end "$task_id" "$exit_code" "$duration" "$tokens_used"
    fi

    if [[ $exit_code -ne 0 ]]; then
        log_warn "Claude Code exited with code ${exit_code}"
        log_debug "Non-zero exit may indicate: timeout, error, or user interrupt"
        # Log error to structured logger
        log_error "Harness exited with non-zero code" "{\"task_id\": \"$task_id\", \"exit_code\": $exit_code, \"harness\": \"$harness\"}"

        # Run on-error hooks
        log_debug "Running on-error hooks..."
        hooks_set_task_context "$task_id" "$task_title" "$exit_code"
        hooks_run "on-error"
        log_debug "On-error hooks complete"
    else
        log_debug "Claude Code completed successfully"

        # Auto-commit session files (progress.txt, fix_plan.md) if modified
        # This handles cases where the agent modifies these files but forgets to commit
        if git_in_repo; then
            log_debug "Checking for uncommitted session files..."
            if git_commit_session_files "$task_id"; then
                log_debug "Session files committed (if any)"
            else
                log_warn "Failed to commit session files"
            fi

            # Auto-commit remaining changes if configured (default: true)
            # This handles cases where the agent completes work but forgets to commit
            local auto_commit
            auto_commit=$(config_get_or "clean_state.auto_commit" "true")
            if [[ "$auto_commit" == "true" ]]; then
                log_debug "Checking for uncommitted changes to auto-commit..."
                if git_commit_remaining_changes "$task_id" "$task_title"; then
                    log_debug "Remaining changes committed (if any)"
                else
                    log_warn "Failed to auto-commit remaining changes"
                fi
            fi
        fi

        # Verify clean state after successful harness run
        log_debug "Checking repository state..."
        if ! state_ensure_clean "$REQUIRE_CLEAN"; then
            log_warn "State check failed: uncommitted changes detected"
            exit_code=1
        else
            log_debug "Repository state is clean"
        fi

        # Run tests if configured
        if [[ $exit_code -eq 0 ]]; then
            log_debug "Running tests if configured..."
            if ! state_run_tests; then
                log_warn "Test run failed"
                exit_code=1
            else
                log_debug "Tests passed or not required"
            fi
        fi

        # Auto-close task if configured and all checks passed
        # This is a safety net for when the agent forgets to close the task
        if [[ $exit_code -eq 0 ]]; then
            local auto_close
            auto_close=$(config_get_or "task.auto_close" "true")
            if [[ "$auto_close" == "true" ]]; then
                log_debug "Checking if task needs auto-closing..."
                if ! verify_task_closed "$prd" "$task_id" 2>/dev/null; then
                    log_info "Auto-closing task $task_id (agent did not close it)..."
                    if auto_close_task "$prd" "$task_id"; then
                        log_success "Task $task_id auto-closed successfully"
                        # Give beads a moment to stabilize after closing
                        sleep 1
                    else
                        log_warn "Failed to auto-close task $task_id"
                    fi
                else
                    log_debug "Task $task_id already closed by agent"
                fi
            fi
        fi
    fi

    # Handle task failure if exit_code is non-zero
    if [[ $exit_code -ne 0 ]]; then
        log_debug "Task failed with exit code ${exit_code}, invoking failure handler..."

        # Get failure mode from config
        local failure_mode
        failure_mode=$(failure_get_mode)
        log_debug "Failure mode: ${failure_mode}"

        # Collect harness output for failure context (if available)
        local harness_output=""
        # Note: harness output is not captured in current implementation
        # Future enhancement: capture last N lines of harness output

        # Call appropriate failure handler based on mode
        local failure_result=0
        case "$failure_mode" in
            stop)
                failure_handle_stop "$task_id" "$exit_code" "$harness_output"
                failure_result=$?
                ;;
            move-on)
                failure_handle_move_on "$task_id" "$exit_code" "$harness_output"
                failure_result=$?
                ;;
            retry)
                failure_handle_retry "$task_id" "$exit_code" "$harness_output"
                failure_result=$?
                ;;
            triage)
                log_warn "Triage mode not yet implemented, falling back to move-on"
                failure_handle_move_on "$task_id" "$exit_code" "$harness_output"
                failure_result=$?
                ;;
            *)
                log_warn "Unknown failure mode '${failure_mode}', falling back to move-on"
                failure_handle_move_on "$task_id" "$exit_code" "$harness_output"
                failure_result=$?
                ;;
        esac

        log_debug "Failure handler returned: ${failure_result}"

        # Check failure handler result
        # Return codes: 0=continue, 2=halt, 3=retry
        if [[ $failure_result -eq 2 ]]; then
            # Stop mode - halt the run
            log_info "Failure handler requested run halt"
            # Run post-task hooks before halting
            log_debug "Running post-task hooks..."
            hooks_set_task_context "$task_id" "$task_title" "$exit_code"
            hooks_run "post-task"
            log_debug "Post-task hooks complete"
            # Return special code to signal halt to main loop
            return 2
        elif [[ $failure_result -eq 3 ]]; then
            # Retry mode - retry the task
            log_info "Failure handler requested task retry"
            # Run post-task hooks
            log_debug "Running post-task hooks..."
            hooks_set_task_context "$task_id" "$task_title" "$exit_code"
            hooks_run "post-task"
            log_debug "Post-task hooks complete"
            # Return special code to signal retry to main loop
            return 3
        fi
        # Otherwise fall through to normal post-task flow (move-on)
    fi

    # Run post-task hooks (always run, regardless of success/failure)
    log_debug "Running post-task hooks..."
    hooks_set_task_context "$task_id" "$task_title" "$exit_code"
    hooks_run "post-task"
    log_debug "Post-task hooks complete"

    # Capture artifacts after task completion
    if session_is_initialized; then
        log_debug "Capturing task artifacts..."

        # Capture git diff
        if artifacts_capture_diff "$task_id"; then
            log_debug "Captured git diff to changes.patch"
        else
            log_warn "Failed to capture git diff"
        fi

        # Finalize task with status and summary
        local task_status
        if [[ $exit_code -eq 0 ]]; then
            task_status="completed"
        else
            task_status="failed"
        fi

        # Get iteration counts for summary
        local task_iter
        task_iter=$(budget_get_task_iterations "$task_id")
        local max_task_iter
        max_task_iter=$(budget_get_max_task_iterations)
        local run_iter
        run_iter=$(budget_get_run_iterations)
        local max_run_iter
        max_run_iter=$(budget_get_max_run_iterations)

        local summary_text="Task execution completed with exit code ${exit_code}. Duration: ${duration}s. Tokens used: ${tokens_used}. Task iteration: ${task_iter}/${max_task_iter}. Run iteration: ${run_iter}/${max_run_iter}."
        if artifacts_finalize_task "$task_id" "$task_status" "$exit_code" "$summary_text"; then
            local artifacts_path
            artifacts_path=$(artifacts_get_path "$task_id")
            log_info "Artifacts saved: ${artifacts_path}"
        else
            log_warn "Failed to finalize task artifacts"
        fi
    fi

    # Commit changes if task was successful and we're in a git repository
    if [[ $exit_code -eq 0 ]] && git_in_repo; then
        log_debug "Committing task changes..."
        if git_commit_task "$task_id" "$task_title" "$summary_text"; then
            log_info "Changes committed to git"

            # Push to remote if --push flag was set
            if [[ "$PUSH" == "true" ]]; then
                log_debug "Pushing branch to remote..."
                if git_push_branch; then
                    log_info "Branch pushed to remote"
                else
                    log_warn "Failed to push branch to remote"
                fi
            else
                log_debug "Skipping push (--push flag not set)"
            fi
        else
            log_warn "Failed to commit changes (this is not an error if there were no changes)"
        fi
    fi

    # Increment run iteration counter after completing task
    budget_increment_run_iterations
    local run_iteration
    run_iteration=$(budget_get_run_iterations)
    local max_run
    max_run=$(budget_get_max_run_iterations)
    log_debug "Run iteration ${run_iteration}/${max_run} complete"

    # Commit cub artifacts (.beads/ and .cub/) if there are changes
    # These are committed separately after the harness's work is complete
    if git_in_repo; then
        log_debug "Committing cub artifacts if needed..."
        git_commit_cub_artifacts "$task_id"
    fi

    # Debug: verify beads state at end of iteration
    if [[ "${DEBUG:-}" == "true" ]]; then
        echo "[cub] END OF ITERATION: checking beads state..." >&2
        local post_remaining
        post_remaining=$(get_remaining_count "$prd")
        local post_ready
        post_ready=$(get_ready_tasks "$prd" "$EPIC" "$LABEL" | jq 'length' 2>/dev/null || echo "error")
        echo "[cub] POST-TASK STATE: remaining=$post_remaining ready_count=$post_ready" >&2
    fi

    return $exit_code
}

run_planning() {
    local prd="${PROJECT_DIR}/prd.json"
    log_debug "Starting planning mode"

    log_info "Running in planning mode..."

    local plan_prompt
    plan_prompt=$(cat <<'EOF'
Study @specs/* for specifications.
Study @prd.json for the current task backlog.
Study the existing source code.

Your task is to analyze the codebase and update @fix_plan.md:

1. Use subagents to study existing source code and compare against specifications
2. Search for TODO comments, placeholder implementations, and missing functionality
3. Create/update fix_plan.md with a prioritized bullet list of items to implement
4. For each item, note:
   - What needs to be done
   - Which files are affected
   - Dependencies on other items
5. If you discover missing specifications, document them

Think hard. Be thorough. Use many parallel subagents for research.
EOF
)

    if [[ "$DEBUG" == "true" ]]; then
        log_debug "Plan prompt: $(echo "$plan_prompt" | wc -l) lines"
        log_debug "=== PLAN PROMPT ==="
        echo -e "${DIM}$plan_prompt${NC}" >&2
        log_debug "==================="
    fi

    local start_time
    start_time=$(date +%s)
    log_debug "Execution start: $(date)"

    echo "$plan_prompt" | claude -p --dangerously-skip-permissions

    local exit_code=$?
    local end_time
    end_time=$(date +%s)
    log_debug "Execution end: $(date), duration: $((end_time - start_time))s, exit: ${exit_code}"
}

# Generate human-readable summary of review results by dimension
# Outputs markdown with verdict, issues by dimension, and suggestions
generate_review_summary() {
    local verdict="$1"
    local completeness_summary="$2"
    local feasibility_summary="$3"
    local dependency_summary="$4"
    local architecture_summary="$5"

    local summary=""

    # Verdict header with status symbol
    case "$verdict" in
        PASS)
            summary+="✓ **VERDICT: PASS**"$'\n'
            summary+=$'\n'
            summary+="All validations passed. Plan is ready for execution."$'\n'
            ;;
        CONCERNS)
            summary+="⚠ **VERDICT: CONCERNS**"$'\n'
            summary+=$'\n'
            summary+="Plan has issues to review. See details below."$'\n'
            ;;
        BLOCK)
            summary+="✗ **VERDICT: BLOCK**"$'\n'
            summary+=$'\n'
            summary+="Critical issues found. Plan cannot be executed."$'\n'
            ;;
    esac

    summary+=$'\n'
    summary+="---"$'\n'
    summary+=$'\n'

    # Issues by dimension
    summary+="## Issues by Dimension"$'\n'
    summary+=$'\n'

    # Completeness
    if [[ -z "$completeness_summary" || "$completeness_summary" == "✓ All tasks are complete" ]]; then
        summary+="### ✓ Completeness"$'\n'
        summary+="All tasks have title, description, and acceptance criteria."$'\n'
    else
        summary+="### ⚠ Completeness"$'\n'
        summary+="$completeness_summary"$'\n'
    fi
    summary+=$'\n'

    # Feasibility
    if [[ -z "$feasibility_summary" || "$feasibility_summary" == "✓ All tasks are feasible" ]]; then
        summary+="### ✓ Feasibility"$'\n'
        summary+="All dependencies are resolved and required files exist."$'\n'
    else
        summary+="### ⚠ Feasibility"$'\n'
        summary+="$feasibility_summary"$'\n'
    fi
    summary+=$'\n'

    # Dependencies
    if [[ -z "$dependency_summary" || "$dependency_summary" == "✓ All dependencies are valid" ]]; then
        summary+="### ✓ Dependencies"$'\n'
        summary+="All dependencies exist, no circular dependencies, correct order."$'\n'
    else
        summary+="### ⚠ Dependencies"$'\n'
        summary+="$dependency_summary"$'\n'
    fi
    summary+=$'\n'

    # Architecture
    if [[ -z "$architecture_summary" || "$architecture_summary" == "✓ All tasks are architecturally aligned" ]]; then
        summary+="### ✓ Architecture"$'\n'
        summary+="Architecture patterns align with codebase."$'\n'
    else
        summary+="### ⚠ Architecture"$'\n'
        summary+="$architecture_summary"$'\n'
    fi
    summary+=$'\n'

    echo -e "$summary"
}

# Generate console-friendly verdict summary with checkmarks/warnings
generate_verdict_summary() {
    local verdict="$1"
    local has_completeness_issues="$2"
    local has_feasibility_issues="$3"
    local has_dependency_issues="$4"
    local has_architecture_issues="$5"

    local summary=""
    summary+="════════════════════════════════════════════════════════════════"$'\n'

    # Verdict line with appropriate symbol
    case "$verdict" in
        PASS)
            summary+="✓ VERDICT: PASS"$'\n'
            summary+=$'\n'
            summary+="Your plan is ready for execution. All validations passed:"$'\n'
            summary+="  ✓ Completeness check"$'\n'
            summary+="  ✓ Feasibility check"$'\n'
            summary+="  ✓ Dependency validation"$'\n'
            summary+="  ✓ Architecture alignment"$'\n'
            ;;
        CONCERNS)
            summary+="⚠ VERDICT: CONCERNS"$'\n'
            summary+=$'\n'
            summary+="Your plan has issues to review:"$'\n'
            [[ "$has_completeness_issues" == "true" ]] && summary+="  ⚠ Completeness issues found"$'\n'
            [[ "$has_feasibility_issues" == "true" ]] && summary+="  ⚠ Feasibility issues found"$'\n'
            [[ "$has_dependency_issues" == "true" ]] && summary+="  ⚠ Dependency issues found"$'\n'
            [[ "$has_architecture_issues" == "true" ]] && summary+="  ⚠ Architecture issues found"$'\n'
            summary+=$'\n'
            summary+="Review the details above before proceeding."$'\n'
            ;;
        BLOCK)
            summary+="✗ VERDICT: BLOCK"$'\n'
            summary+=$'\n'
            summary+="Critical issues found. Plan cannot be executed yet."$'\n'
            [[ "$has_completeness_issues" == "true" ]] && summary+="  ✗ Completeness issues"$'\n'
            [[ "$has_feasibility_issues" == "true" ]] && summary+="  ✗ Feasibility issues"$'\n'
            [[ "$has_dependency_issues" == "true" ]] && summary+="  ✗ Dependency issues"$'\n'
            [[ "$has_architecture_issues" == "true" ]] && summary+="  ✗ Architecture issues"$'\n'
            summary+=$'\n'
            summary+="Fix the issues above and try again."$'\n'
            ;;
    esac

    summary+="════════════════════════════════════════════════════════════════"$'\n'

    echo -e "$summary"
}

# Generate JSON output for plan review
generate_review_json() {
    local verdict="$1"
    local completeness_summary="$2"
    local feasibility_summary="$3"
    local dependency_summary="$4"
    local architecture_summary="$5"
    local has_completeness_issues="$6"
    local has_feasibility_issues="$7"
    local has_dependency_issues="$8"
    local has_architecture_issues="$9"
    local prd="${10}"

    # Determine if plan is ready to implement (ready if PASS, not ready if CONCERNS or BLOCK)
    local ready_to_implement="false"
    if [[ "$verdict" == "PASS" ]]; then
        ready_to_implement="true"
    fi

    # Build dimension objects with status and issues
    # Completeness dimension
    local completeness_status="pass"
    if [[ "$has_completeness_issues" == "true" ]]; then
        completeness_status="concerns"
    fi

    # Feasibility dimension
    local feasibility_status="pass"
    if [[ "$has_feasibility_issues" == "true" ]]; then
        feasibility_status="concerns"
    fi

    # Dependency dimension
    local dependency_status="pass"
    if [[ "$has_dependency_issues" == "true" ]]; then
        dependency_status="concerns"
    fi

    # Architecture dimension
    local architecture_status="pass"
    if [[ "$has_architecture_issues" == "true" ]]; then
        architecture_status="concerns"
    fi

    # Get task count for task_id
    local task_count=0
    if [[ -f "$prd" ]]; then
        task_count=$(jq 'if type == "object" then .tasks | length else length end' "$prd" 2>/dev/null || echo "0")
    fi
    local task_id="plan-review-${task_count}-tasks"

    # Generate JSON output
    jq -n \
        --arg task_id "$task_id" \
        --arg verdict "$(echo "$verdict" | tr '[:upper:]' '[:lower:]')" \
        --arg completeness_status "$completeness_status" \
        --arg feasibility_status "$feasibility_status" \
        --arg dependency_status "$dependency_status" \
        --arg architecture_status "$architecture_status" \
        --arg ready_to_implement "$ready_to_implement" \
        --arg completeness_issues "$completeness_summary" \
        --arg feasibility_issues "$feasibility_summary" \
        --arg dependency_issues "$dependency_summary" \
        --arg architecture_issues "$architecture_summary" \
        '{
            task_id: $task_id,
            verdict: $verdict,
            dimensions: {
                completeness: {
                    status: $completeness_status,
                    issues: (if $completeness_status == "pass" then [] else [$completeness_issues] | map(select(length > 0)) end),
                    suggestions: ["Ensure all tasks have title (≥10 chars), description, and acceptance criteria"]
                },
                feasibility: {
                    status: $feasibility_status,
                    issues: (if $feasibility_status == "pass" then [] else [$feasibility_issues] | map(select(length > 0)) end),
                    suggestions: ["Verify all dependencies are closed", "Ensure referenced files exist"]
                },
                dependencies: {
                    status: $dependency_status,
                    issues: (if $dependency_status == "pass" then [] else [$dependency_issues] | map(select(length > 0)) end),
                    suggestions: ["Check for circular dependencies", "Verify task order is correct"]
                },
                architecture: {
                    status: $architecture_status,
                    issues: (if $architecture_status == "pass" then [] else [$architecture_issues] | map(select(length > 0)) end),
                    suggestions: ["Review patterns alignment with codebase", "Ensure consistent structure"]
                }
            },
            ready_to_implement: ($ready_to_implement == "true"),
            reviewed_at: (now | todate)
        }'
}

run_review_plans() {
    local json_output=false
    if [[ "${1:-}" == "--json" ]]; then
        json_output=true
    fi

    local prd="${PROJECT_DIR}/prd.json"
    local review_report="${PROJECT_DIR}/plan_review.md"

    if [[ "$json_output" == "false" ]]; then
        log_debug "Starting plan review mode"
        log_info "Running plan validation suite..."

        # Initialize report file
        {
            echo "# Plan Review Report"
            echo ""
            echo "Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
            echo ""
        } > "$review_report"
    fi

    # Run all validation suites
    local has_concerns=false
    local has_blocks=false
    local has_completeness_issues=false
    local has_feasibility_issues=false
    local has_dependency_issues=false
    local has_architecture_issues=false

    # 1. COMPLETENESS VALIDATION
    if [[ "$json_output" == "false" ]]; then
        log_info "Checking completeness..."
        echo "## Completeness Validation" >> "$review_report"
        echo "" >> "$review_report"
    fi

    local completeness_summary
    local completeness_status="pass"
    local completeness_issue_count=0
    completeness_summary=$(get_completeness_summary "$prd" 2>/dev/null || echo "")

    if [[ -z "$completeness_summary" || "$completeness_summary" == "✓ All tasks are complete" ]]; then
        if [[ "$json_output" == "false" ]]; then
            echo "✓ **PASS**: All tasks have title, description, and acceptance criteria" >> "$review_report"
            log_info "✓ Completeness check passed"
        fi
    else
        if [[ "$json_output" == "false" ]]; then
            echo "⚠ **CONCERNS**: Some tasks are incomplete:" >> "$review_report"
            echo "" >> "$review_report"
            echo "$completeness_summary" >> "$review_report"
            log_warn "⚠ Completeness check found issues"
        fi
        completeness_status="concerns"
        completeness_issue_count=$(echo "$completeness_summary" | grep -c "^- " || echo "0")
        has_concerns=true
        has_completeness_issues=true
    fi
    if [[ "$json_output" == "false" ]]; then
        echo "" >> "$review_report"
    fi

    # 2. FEASIBILITY VALIDATION
    if [[ "$json_output" == "false" ]]; then
        log_info "Checking feasibility..."
        echo "## Feasibility Validation" >> "$review_report"
        echo "" >> "$review_report"
    fi

    local feasibility_summary
    local feasibility_status="pass"
    local feasibility_issue_count=0
    feasibility_summary=$(get_feasibility_summary "$prd" 2>/dev/null || echo "")

    if [[ -z "$feasibility_summary" || "$feasibility_summary" == "✓ All tasks are feasible" ]]; then
        if [[ "$json_output" == "false" ]]; then
            echo "✓ **PASS**: All dependencies are resolved and files exist" >> "$review_report"
            log_info "✓ Feasibility check passed"
        fi
    else
        if [[ "$json_output" == "false" ]]; then
            echo "⚠ **CONCERNS**: Some tasks are not feasible:" >> "$review_report"
            echo "" >> "$review_report"
            echo "$feasibility_summary" >> "$review_report"
            log_warn "⚠ Feasibility check found issues"
        fi
        feasibility_status="concerns"
        feasibility_issue_count=$(echo "$feasibility_summary" | grep -c "^- " || echo "0")
        has_concerns=true
        has_feasibility_issues=true
    fi
    if [[ "$json_output" == "false" ]]; then
        echo "" >> "$review_report"
    fi

    # 3. DEPENDENCY VALIDATION
    if [[ "$json_output" == "false" ]]; then
        log_info "Checking dependencies..."
        echo "## Dependency Validation" >> "$review_report"
        echo "" >> "$review_report"
    fi

    local dependency_summary
    local dependency_status="pass"
    local dependency_issue_count=0
    dependency_summary=$(get_dependency_summary "$prd" 2>/dev/null || echo "")

    if [[ -z "$dependency_summary" || "$dependency_summary" == "✓ All dependencies are valid" ]]; then
        if [[ "$json_output" == "false" ]]; then
            echo "✓ **PASS**: All dependencies exist, no cycles, correct order" >> "$review_report"
            log_info "✓ Dependency check passed"
        fi
    else
        if [[ "$json_output" == "false" ]]; then
            echo "⚠ **CONCERNS**: Some dependencies are invalid:" >> "$review_report"
            echo "" >> "$review_report"
            echo "$dependency_summary" >> "$review_report"
            log_warn "⚠ Dependency check found issues"
        fi
        dependency_status="concerns"
        dependency_issue_count=$(echo "$dependency_summary" | grep -c "^- " || echo "0")
        has_concerns=true
        has_dependency_issues=true
    fi
    if [[ "$json_output" == "false" ]]; then
        echo "" >> "$review_report"
    fi

    # 4. ARCHITECTURE VALIDATION
    if [[ "$json_output" == "false" ]]; then
        log_info "Checking architecture alignment..."
        echo "## Architecture Alignment" >> "$review_report"
        echo "" >> "$review_report"
    fi

    local architecture_summary
    local architecture_status="pass"
    local architecture_issue_count=0
    architecture_summary=$(get_architecture_summary "$prd" 2>/dev/null || echo "")

    if [[ -z "$architecture_summary" || "$architecture_summary" == "✓ All tasks are architecturally aligned" ]]; then
        if [[ "$json_output" == "false" ]]; then
            echo "✓ **PASS**: Architecture patterns align with codebase" >> "$review_report"
            log_info "✓ Architecture check passed"
        fi
    else
        if [[ "$json_output" == "false" ]]; then
            echo "⚠ **CONCERNS**: Architecture alignment issues found:" >> "$review_report"
            echo "" >> "$review_report"
            echo "$architecture_summary" >> "$review_report"
            log_warn "⚠ Architecture check found issues"
        fi
        architecture_status="concerns"
        architecture_issue_count=$(echo "$architecture_summary" | grep -c "^- " || echo "0")
        has_concerns=true
        has_architecture_issues=true
    fi
    if [[ "$json_output" == "false" ]]; then
        echo "" >> "$review_report"
    fi

    # Generate verdict
    echo "## Summary by Dimension" >> "$review_report"
    echo "" >> "$review_report"

    # Check for block_on_concerns config
    local block_on_concerns
    block_on_concerns=$(config_get_or "review.block_on_concerns" "false")

    local verdict="PASS"
    if [[ "$has_blocks" == "true" ]]; then
        verdict="BLOCK"
    elif [[ "$has_concerns" == "true" ]]; then
        # If block_on_concerns is enabled, upgrade CONCERNS to BLOCK
        if [[ "$block_on_concerns" == "true" ]]; then
            verdict="BLOCK"
        else
            verdict="CONCERNS"
        fi
    fi

    if [[ "$json_output" == "true" ]]; then
        # Output JSON format
        local json_output_str
        json_output_str=$(generate_review_json \
            "$verdict" \
            "$completeness_summary" \
            "$feasibility_summary" \
            "$dependency_summary" \
            "$architecture_summary" \
            "$has_completeness_issues" \
            "$has_feasibility_issues" \
            "$has_dependency_issues" \
            "$has_architecture_issues" \
            "$prd")

        echo "$json_output_str"
    else
        # Generate detailed markdown summary
        local summary_markdown
        summary_markdown=$(generate_review_summary \
            "$verdict" \
            "$completeness_summary" \
            "$feasibility_summary" \
            "$dependency_summary" \
            "$architecture_summary")

        echo "$summary_markdown" >> "$review_report"

        # Add verdict explanation section
        echo "" >> "$review_report"
        echo "## Verdict Explanation" >> "$review_report"
        echo "" >> "$review_report"

        case "$verdict" in
            PASS)
                echo "Plan is ready for execution. All validations passed without issues." >> "$review_report"
                echo "All tasks are complete, feasible, have valid dependencies, and follow" >> "$review_report"
                echo "established architectural patterns. Proceed with confidence." >> "$review_report"
                log_info "✓ VERDICT: PASS - Plan is ready for execution"
                ;;
            CONCERNS)
                echo "Plan has issues to review but is executable. Issues found in one or more" >> "$review_report"
                echo "dimensions. Review the summary above carefully. Consider fixing issues" >> "$review_report"
                echo "before execution to improve code quality, but you may proceed if needed." >> "$review_report"
                log_warn "⚠ VERDICT: CONCERNS - Review issues before execution"
                ;;
            BLOCK)
                echo "Plan cannot be executed. Critical issues must be resolved first." >> "$review_report"
                if [[ "$block_on_concerns" == "true" && "$has_blocks" != "true" ]]; then
                    echo "Issues are blocking because block_on_concerns is enabled." >> "$review_report"
                    echo "Either fix the concerns or disable block_on_concerns in config." >> "$review_report"
                    log_error "✗ VERDICT: BLOCK - Blocking on concerns (block_on_concerns=true)"
                else
                    echo "Fix the issues in the summary above and try again." >> "$review_report"
                    log_error "✗ VERDICT: BLOCK - Critical issues must be resolved"
                fi
                ;;
        esac
        echo "" >> "$review_report"
        echo "---" >> "$review_report"
        echo "Review generated at: $(date)" >> "$review_report"

        # Log verdict result
        log_info "Plan review completed: ${verdict}"
        log_info "Review report: ${review_report}"

        # Display human-readable verdict summary in console
        local console_summary
        console_summary=$(generate_verdict_summary \
            "$verdict" \
            "$has_completeness_issues" \
            "$has_feasibility_issues" \
            "$has_dependency_issues" \
            "$has_architecture_issues")

        echo ""
        echo "$console_summary"
        echo ""
        echo "Full review report: ${review_report}"
        echo ""
    fi

    # Log plan review event for analytics and accuracy tracking
    local task_count=0
    if [[ -f "$prd" ]]; then
        task_count=$(jq '[.tasks[]] | length' "$prd" 2>/dev/null || echo "0")
    fi

    local dimensions_json
    dimensions_json=$(jq -cn \
        --arg completeness_status "$completeness_status" \
        --argjson completeness_issues "$completeness_issue_count" \
        --arg feasibility_status "$feasibility_status" \
        --argjson feasibility_issues "$feasibility_issue_count" \
        --arg dependency_status "$dependency_status" \
        --argjson dependency_issues "$dependency_issue_count" \
        --arg architecture_status "$architecture_status" \
        --argjson architecture_issues "$architecture_issue_count" \
        '{
            completeness: {status: $completeness_status, issues: $completeness_issues},
            feasibility: {status: $feasibility_status, issues: $feasibility_issues},
            dependencies: {status: $dependency_status, issues: $dependency_issues},
            architecture: {status: $architecture_status, issues: $architecture_issues}
        }')

    log_plan_review_event "$verdict" "$task_count" "$dimensions_json" "$has_concerns"

    return 0
}

run_loop() {
    local max_iterations="${CUB_MAX_ITERATIONS:-$(config_get_or "loop.max_iterations" "100")}"
    local iteration=0

    # Initialize session with optional name override
    if [[ -n "$SESSION_NAME" ]]; then
        session_init --name "$SESSION_NAME"
    else
        session_init
    fi

    if [[ $? -ne 0 ]]; then
        log_warn "Failed to initialize session"
    else
        local session_name
        session_name=$(session_get_name)
        local session_id
        session_id=$(session_get_id)
        log_info "Session: ${session_name} (${session_id})"
    fi

    # Initialize logger with project name and session ID
    local project_name
    project_name=$(basename "$PROJECT_DIR")
    local session_id
    session_id=$(session_get_id)

    if logger_init "$project_name" "$session_id"; then
        log_debug "Logger initialized: $(logger_get_file)"
    else
        log_warn "Failed to initialize logger"
    fi

    # Initialize artifacts for this run
    if artifacts_init_run; then
        local artifacts_path
        artifacts_path=$(artifacts_get_run_dir)
        log_debug "Artifacts initialized: ${artifacts_path}"
    else
        log_warn "Failed to initialize artifacts"
    fi

    # Initialize git run branch if in a git repository
    if git_in_repo; then
        log_debug "Initializing git run branch..."
        local session_name
        session_name=$(session_get_name)
        if git_init_run_branch "$session_name"; then
            local branch_name
            branch_name=$(git_get_run_branch)
            log_info "Git branch: ${branch_name}"
        else
            log_warn "Failed to initialize git run branch"
        fi
    else
        log_debug "Not in a git repository, skipping git operations"
    fi

    log_info "Starting cub loop (max ${max_iterations} iterations)"
    log_debug "Max iterations: ${max_iterations}"
    log_debug "Loop starting at: $(date)"
    echo ""

    # Run pre-loop hooks
    log_debug "Running pre-loop hooks..."
    hooks_set_session_context "$session_id" "$(harness_get)"
    hooks_run "pre-loop"
    log_debug "Pre-loop hooks complete"

    while [[ $iteration -lt $max_iterations ]]; do
        iteration=$((iteration + 1))
        log_info "=== Iteration ${iteration} ==="
        log_debug "--- Iteration ${iteration} start: $(date) ---"

        # Check if all tasks complete
        local prd="${PROJECT_DIR}/prd.json"
        log_debug "Querying remaining tasks..."
        local remaining
        remaining=$(get_remaining_count "$prd")

        # Always log this to stderr so it's visible even with streaming
        echo "[cub] REMAINING CHECK: remaining='$remaining' (empty='$([ -z "$remaining" ] && echo yes || echo no)')" >&2
        log_debug "Remaining tasks: ${remaining}"

        # Handle error case (-1 or empty string means backend query failed)
        if [[ -z "$remaining" || "$remaining" == "-1" ]]; then
            log_warn "Failed to get remaining task count, assuming tasks remain"
            remaining=1  # Continue loop on error
        elif [[ "$remaining" -eq 0 ]]; then
            echo "[cub] EXIT REASON: remaining count is 0, exiting loop" >&2
            log_success "All tasks complete! Exiting loop."
            show_status
            # Run post-loop hooks
            log_debug "Running post-loop hooks..."
            hooks_run "post-loop"
            log_debug "Post-loop hooks complete"
            return 0
        fi

        # Run single iteration
        log_debug "Calling run_iteration..."
        run_iteration
        local iteration_result=$?

        if [[ $iteration_result -eq 2 ]]; then
            # Failure handler requested halt
            log_warn "Failure handler requested run halt"
            show_status
            # Run post-loop hooks
            log_debug "Running post-loop hooks..."
            hooks_run "post-loop"
            log_debug "Post-loop hooks complete"
            return 2
        elif [[ $iteration_result -eq 3 ]]; then
            # Failure handler requested retry
            log_info "Failure handler requested retry - will retry task in next iteration"
            # Don't increment iteration counter for retry
            iteration=$((iteration - 1))
        elif [[ $iteration_result -ne 0 ]]; then
            # Other non-zero exit (normal failure with move-on)
            log_warn "Iteration failed, continuing..."
            log_debug "run_iteration returned ${iteration_result}"
        fi

        echo ""
        log_info "Iteration ${iteration} complete. ${remaining} tasks remaining."
        log_debug "--- Iteration ${iteration} end: $(date) ---"
        echo ""

        # Check budget after iteration if budget is initialized
        if [[ -f "${TMPDIR:-/tmp}/cub_budget_limit_$$" ]]; then
            if ! budget_check; then
                local used
                used=$(budget_get_used)
                local limit
                limit=$(budget_get_limit)
                echo ""
                log_success "Budget exceeded (used ${used} of ${limit} tokens)"
                log_info "Stopping gracefully due to budget limit"
                show_status
                # Run post-loop hooks
                log_debug "Running post-loop hooks..."
                hooks_run "post-loop"
                log_debug "Post-loop hooks complete"
                return 0
            fi
        fi

        # Brief pause between iterations to allow for interruption
        log_debug "Sleeping 2 seconds before next iteration..."
        sleep 2
    done

    log_warn "Reached max iterations (${max_iterations})"
    log_debug "Loop terminated at: $(date)"
    show_status
    # Run post-loop hooks
    log_debug "Running post-loop hooks..."
    hooks_run "post-loop"
    log_debug "Post-loop hooks complete"
    return 1
}

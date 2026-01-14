#!/usr/bin/env bash
#
# cmd_prep.sh - Vision-to-Tasks Prep
#
# Unified prep pipeline from vision document to executable tasks:
#   cub prep VISION.md        - Run full prep pipeline
#   cub triage [VISION.md]    - Stage 1: Requirements refinement
#   cub architect [session]   - Stage 2: Technical design
#   cub plan [session]        - Stage 3: Task decomposition
#   cub bootstrap [session]   - Stage 4: Initialize beads
#   cub sessions              - List/manage sessions
#
# Sessions are stored in .cub/sessions/{session-id}/
# Each session produces artifacts: triage.md, architect.md, plan.jsonl, plan.md
#

# Session directory root
PIPELINE_SESSIONS_DIR="${PROJECT_DIR}/.cub/sessions"

# ============================================================================
# Session Management Functions
# ============================================================================

# Generate a new session ID: {project}-{YYYYMMDD-HHMMSS}
# Args: [project_name] - Optional, defaults to directory name
pipeline_new_session_id() {
    local project_name="${1:-}"

    if [[ -z "$project_name" ]]; then
        # Use directory name as project name (lowercase, alphanumeric only)
        project_name=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]//g')
        # Limit to 12 characters
        project_name="${project_name:0:12}"
    fi

    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)

    echo "${project_name}-${timestamp}"
}

# Get the most recent session ID
# Returns: session ID or empty if none
pipeline_most_recent_session() {
    if [[ -d "$PIPELINE_SESSIONS_DIR" ]]; then
        ls -t "$PIPELINE_SESSIONS_DIR" 2>/dev/null | head -1
    fi
}

# Check if a session exists
# Args: session_id
pipeline_session_exists() {
    local session_id="$1"
    [[ -d "${PIPELINE_SESSIONS_DIR}/${session_id}" ]]
}

# Get session directory path
# Args: session_id
pipeline_session_dir() {
    local session_id="$1"
    echo "${PIPELINE_SESSIONS_DIR}/${session_id}"
}

# Create a new session directory
# Args: session_id
pipeline_create_session() {
    local session_id="$1"
    local session_dir="${PIPELINE_SESSIONS_DIR}/${session_id}"

    mkdir -p "$session_dir"

    # Create session metadata
    cat > "${session_dir}/session.json" <<EOF
{
  "id": "${session_id}",
  "created": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "status": "created",
  "stages": {
    "triage": null,
    "architect": null,
    "plan": null,
    "bootstrap": null
  }
}
EOF

    echo "$session_dir"
}

# Update session status
# Args: session_id stage status
pipeline_update_session() {
    local session_id="$1"
    local stage="$2"
    local status="$3"
    local session_dir="${PIPELINE_SESSIONS_DIR}/${session_id}"
    local session_file="${session_dir}/session.json"

    if [[ -f "$session_file" ]]; then
        local tmp_file="${session_file}.tmp"
        jq --arg stage "$stage" --arg status "$status" \
            '.stages[$stage] = $status | .updated = (now | strftime("%Y-%m-%dT%H:%M:%SZ"))' \
            "$session_file" > "$tmp_file" && mv "$tmp_file" "$session_file"
    fi
}

# List all sessions
pipeline_list_sessions() {
    if [[ ! -d "$PIPELINE_SESSIONS_DIR" ]]; then
        return 0
    fi

    local sessions
    sessions=$(ls -t "$PIPELINE_SESSIONS_DIR" 2>/dev/null)

    if [[ -z "$sessions" ]]; then
        return 0
    fi

    echo "$sessions"
}

# Get session info
# Args: session_id
pipeline_session_info() {
    local session_id="$1"
    local session_dir="${PIPELINE_SESSIONS_DIR}/${session_id}"
    local session_file="${session_dir}/session.json"

    if [[ -f "$session_file" ]]; then
        cat "$session_file"
    else
        echo "{}"
    fi
}

# ============================================================================
# Pipeline Stage Checkers
# ============================================================================

# Check if triage is complete for session
pipeline_has_triage() {
    local session_id="$1"
    [[ -f "${PIPELINE_SESSIONS_DIR}/${session_id}/triage.md" ]]
}

# Check if architect is complete for session
pipeline_has_architect() {
    local session_id="$1"
    [[ -f "${PIPELINE_SESSIONS_DIR}/${session_id}/architect.md" ]]
}

# Check if plan is complete for session
pipeline_has_plan() {
    local session_id="$1"
    [[ -f "${PIPELINE_SESSIONS_DIR}/${session_id}/plan.jsonl" ]]
}

# ============================================================================
# Vision Document Finder
# ============================================================================

# Find vision document in priority order
# Args: [explicit_path]
# Returns: path to vision document or empty
pipeline_find_vision() {
    local explicit_path="${1:-}"

    # Priority 1: Explicit path
    if [[ -n "$explicit_path" && -f "$explicit_path" ]]; then
        echo "$explicit_path"
        return 0
    fi

    # Priority 2: VISION.md in project root
    if [[ -f "${PROJECT_DIR}/VISION.md" ]]; then
        echo "${PROJECT_DIR}/VISION.md"
        return 0
    fi

    # Priority 3: docs/PRD.md
    if [[ -f "${PROJECT_DIR}/docs/PRD.md" ]]; then
        echo "${PROJECT_DIR}/docs/PRD.md"
        return 0
    fi

    # Priority 4: README.md (fallback)
    if [[ -f "${PROJECT_DIR}/README.md" ]]; then
        echo "${PROJECT_DIR}/README.md"
        return 0
    fi

    # No vision document found
    return 1
}

# ============================================================================
# Triage Stage (cmd_triage)
# ============================================================================

cmd_triage() {
    local session_id=""
    local resume_session=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --session)
                resume_session="$2"
                shift 2
                ;;
            --session=*)
                resume_session="${1#--session=}"
                shift
                ;;
            --help|-h)
                _triage_help
                return 0
                ;;
            -*)
                _log_error_console "Unknown option: $1"
                _triage_help
                return 1
                ;;
            *)
                # Ignore positional args (vision path handled by skill)
                shift
                ;;
        esac
    done

    # Check that triage skill is installed
    if [[ ! -f ".claude/commands/cub:triage.md" ]]; then
        _log_error_console "Triage skill not installed."
        _log_error_console "Run 'cub init' to install Claude Code skills."
        return 1
    fi

    # Resume existing session or create new
    if [[ -n "$resume_session" ]]; then
        if ! pipeline_session_exists "$resume_session"; then
            _log_error_console "Session not found: $resume_session"
            return 1
        fi
        session_id="$resume_session"
        log_info "Resuming session: ${session_id}"
    else
        session_id=$(pipeline_new_session_id)
        pipeline_create_session "$session_id"
        log_info "Starting new triage session: ${session_id}"
    fi

    local session_dir
    session_dir=$(pipeline_session_dir "$session_id")
    local output_file="${session_dir}/triage.md"

    # Invoke the triage skill with output path
    log_info "Starting triage interview..."
    log_info "Session: ${session_id}"
    echo ""

    # Run claude with the /triage skill
    claude "/cub:triage ${output_file}"

    # Check if output was created
    if [[ -f "$output_file" ]]; then
        pipeline_update_session "$session_id" "triage" "complete"
        echo ""
        log_success "Triage complete!"
        log_info "Output: ${output_file}"
        log_info "Next step: cub architect --session ${session_id}"
    else
        echo ""
        log_warn "Triage session ended but output file not created."
        log_info "Session: ${session_id}"
        log_info "Expected output: ${output_file}"
        log_info "Resume with: cub triage --session ${session_id}"
    fi

    return 0
}

_triage_help() {
    cat <<EOF
Usage: cub triage [OPTIONS]

Stage 1: Requirements Refinement

Launches an interactive Claude session to conduct a product triage interview,
clarify requirements, identify gaps, and produce a refined requirements document.

Options:
  --session ID       Resume an existing session
  -h, --help         Show this help message

Examples:
  cub triage                      # Start new triage session
  cub triage --session myproj-... # Resume existing session

Output:
  .cub/sessions/{session-id}/triage.md

Next Step:
  cub architect --session {session-id}
EOF
}

# ============================================================================
# Architect Stage (cmd_architect)
# ============================================================================

cmd_architect() {
    local session_id=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --session)
                session_id="$2"
                shift 2
                ;;
            --session=*)
                session_id="${1#--session=}"
                shift
                ;;
            --help|-h)
                _architect_help
                return 0
                ;;
            -*)
                _log_error_console "Unknown option: $1"
                _architect_help
                return 1
                ;;
            *)
                session_id="$1"
                shift
                ;;
        esac
    done

    # Check that architect skill is installed
    if [[ ! -f ".claude/commands/cub:architect.md" ]]; then
        _log_error_console "Architect skill not installed."
        _log_error_console "Run 'cub init' to install Claude Code skills."
        return 1
    fi

    # Get session ID
    if [[ -z "$session_id" ]]; then
        session_id=$(pipeline_most_recent_session)
        if [[ -z "$session_id" ]]; then
            _log_error_console "No session specified and no recent session found."
            _log_error_console "Run 'cub triage' first to create a session."
            return 1
        fi
        log_info "Using most recent session: ${session_id}"
    fi

    # Verify session exists
    if ! pipeline_session_exists "$session_id"; then
        _log_error_console "Session not found: ${session_id}"
        return 1
    fi

    # Verify triage is complete
    if ! pipeline_has_triage "$session_id"; then
        _log_error_console "Triage not complete for session: ${session_id}"
        _log_error_console "Run 'cub triage --session ${session_id}' first."
        return 1
    fi

    local session_dir
    session_dir=$(pipeline_session_dir "$session_id")
    local output_file="${session_dir}/architect.md"

    # Invoke the architect skill with output path
    log_info "Starting architecture design session..."
    log_info "Session: ${session_id}"
    echo ""

    # Run claude with the /architect skill
    claude "/cub:architect ${output_file}"

    # Check if output was created
    if [[ -f "$output_file" ]]; then
        pipeline_update_session "$session_id" "architect" "complete"
        echo ""
        log_success "Architecture design complete!"
        log_info "Output: ${output_file}"
        log_info "Next step: cub plan --session ${session_id}"
    else
        echo ""
        log_warn "Architect session ended but output file not created."
        log_info "Session: ${session_id}"
        log_info "Expected output: ${output_file}"
        log_info "Resume with: cub architect --session ${session_id}"
    fi

    return 0
}

_architect_help() {
    cat <<EOF
Usage: cub architect [OPTIONS] [SESSION_ID]

Stage 2: Technical Design

Launches an interactive Claude session to design a technical architecture
based on the triage output.

Arguments:
  SESSION_ID         Session ID from triage (default: most recent)

Options:
  --session ID       Specify session ID
  -h, --help         Show this help message

Examples:
  cub architect                        # Use most recent session
  cub architect --session myproj-...   # Specific session

Output:
  .cub/sessions/{session-id}/architect.md

Next Step:
  cub plan --session {session-id}
EOF
}

# ============================================================================
# Plan Stage (cmd_plan)
# ============================================================================

cmd_plan() {
    local session_id=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --session)
                session_id="$2"
                shift 2
                ;;
            --session=*)
                session_id="${1#--session=}"
                shift
                ;;
            --help|-h)
                _plan_help
                return 0
                ;;
            -*)
                _log_error_console "Unknown option: $1"
                _plan_help
                return 1
                ;;
            *)
                session_id="$1"
                shift
                ;;
        esac
    done

    # Check that plan skill is installed
    if [[ ! -f ".claude/commands/cub:plan.md" ]]; then
        _log_error_console "Plan skill not installed."
        _log_error_console "Run 'cub init' to install Claude Code skills."
        return 1
    fi

    # Get session ID
    if [[ -z "$session_id" ]]; then
        session_id=$(pipeline_most_recent_session)
        if [[ -z "$session_id" ]]; then
            _log_error_console "No session specified and no recent session found."
            return 1
        fi
        log_info "Using most recent session: ${session_id}"
    fi

    # Verify session exists
    if ! pipeline_session_exists "$session_id"; then
        _log_error_console "Session not found: ${session_id}"
        return 1
    fi

    # Verify architect is complete
    if ! pipeline_has_architect "$session_id"; then
        _log_error_console "Architecture not complete for session: ${session_id}"
        _log_error_console "Run 'cub architect --session ${session_id}' first."
        return 1
    fi

    local session_dir
    session_dir=$(pipeline_session_dir "$session_id")
    local jsonl_file="${session_dir}/plan.jsonl"
    local md_file="${session_dir}/plan.md"

    # Invoke the plan skill with session dir
    log_info "Starting plan generation session..."
    log_info "Session: ${session_id}"
    echo ""

    # Run claude with the /plan skill
    claude "/cub:plan ${session_dir}"

    # Check if output was created
    if [[ -f "$jsonl_file" ]]; then
        pipeline_update_session "$session_id" "plan" "complete"
        echo ""

        # Count tasks
        local epic_count task_count
        epic_count=$(grep -c '"issue_type":"epic"' "$jsonl_file" 2>/dev/null || echo "0")
        task_count=$(grep -c '"issue_type":"task"' "$jsonl_file" 2>/dev/null || echo "0")

        log_success "Plan generated: ${epic_count} epics, ${task_count} tasks"
        log_info "JSONL: ${jsonl_file}"
        [[ -f "$md_file" ]] && log_info "Summary: ${md_file}"
        log_info "Next step: cub bootstrap --session ${session_id}"
    else
        echo ""
        log_warn "Plan session ended but JSONL file not created."
        log_info "Session: ${session_id}"
        log_info "Expected output: ${jsonl_file}"
        log_info "Resume with: cub plan --session ${session_id}"
    fi

    return 0
}

_plan_help() {
    cat <<EOF
Usage: cub plan [OPTIONS] [SESSION_ID]

Stage 3: Task Decomposition

Launches an interactive Claude session to break architecture into
executable, AI-agent-friendly tasks.

Arguments:
  SESSION_ID         Session ID from architect (default: most recent)

Options:
  --session ID       Specify session ID
  -h, --help         Show this help message

Examples:
  cub plan                             # Use most recent session
  cub plan --session myproj-...        # Specific session

Output:
  .cub/sessions/{session-id}/plan.jsonl     (Beads-compatible)
  .cub/sessions/{session-id}/plan.md        (Human-readable)

Next Step:
  cub bootstrap --session {session-id}
EOF
}

# ============================================================================
# Bootstrap Stage (cmd_bootstrap)
# ============================================================================

cmd_bootstrap() {
    local session_id=""
    local prefix=""
    local skip_prompt="false"
    local dry_run="false"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --prefix)
                prefix="$2"
                shift 2
                ;;
            --prefix=*)
                prefix="${1#--prefix=}"
                shift
                ;;
            --skip-prompt)
                skip_prompt="true"
                shift
                ;;
            --dry-run)
                dry_run="true"
                shift
                ;;
            --help|-h)
                _bootstrap_help
                return 0
                ;;
            -*)
                _log_error_console "Unknown option: $1"
                _bootstrap_help
                return 1
                ;;
            *)
                session_id="$1"
                shift
                ;;
        esac
    done

    # Get session ID
    if [[ -z "$session_id" ]]; then
        session_id=$(pipeline_most_recent_session)
        if [[ -z "$session_id" ]]; then
            _log_error_console "No session specified and no recent session found."
            return 1
        fi
        log_info "Using most recent session: ${session_id}"
    fi

    # Verify session exists
    if ! pipeline_session_exists "$session_id"; then
        _log_error_console "Session not found: ${session_id}"
        return 1
    fi

    # Verify plan is complete
    if ! pipeline_has_plan "$session_id"; then
        _log_error_console "Plan not complete for session: ${session_id}"
        _log_error_console "Run 'cub plan ${session_id}' first."
        return 1
    fi

    local session_dir
    session_dir=$(pipeline_session_dir "$session_id")
    local plan_file="${session_dir}/plan.jsonl"

    log_info "Bootstrapping from session: ${session_id}"

    # Pre-flight checks
    log_info "Running pre-flight checks..."

    # Check 1: Git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        _log_error_console "Not a git repository. Initialize with 'git init' first."
        return 1
    fi
    log_debug "  ✓ Git repository found"

    # Check 2: Clean working directory
    local git_status
    git_status=$(git status --porcelain)
    if [[ -n "$git_status" ]]; then
        log_warn "Uncommitted changes detected:"
        echo "$git_status" | head -10
        log_warn "Consider committing or stashing before bootstrap."
    else
        log_debug "  ✓ Working directory clean"
    fi

    # Check 3: Required tools
    if ! command -v bd &> /dev/null; then
        _log_error_console "Beads CLI (bd) not found."
        _log_error_console "Install from: https://github.com/steveyegge/beads"
        return 1
    fi
    log_debug "  ✓ Beads CLI found"

    if ! command -v jq &> /dev/null; then
        _log_error_console "jq not found. Install with: brew install jq"
        return 1
    fi
    log_debug "  ✓ jq found"

    # Check 4: Existing beads state
    local beads_exists="false"
    if [[ -d "${PROJECT_DIR}/.beads" ]]; then
        beads_exists="true"
        local issue_count
        issue_count=$(bd list --count 2>/dev/null || echo "0")
        log_warn "Beads already initialized with ${issue_count} issues."
        log_warn "Import will add to existing issues."
    fi

    if [[ "$dry_run" == "true" ]]; then
        log_info "Dry run - would perform these actions:"
        log_info "  1. Initialize beads (if needed)"
        log_info "  2. Import ${plan_file}"
        log_info "  3. Sync beads state"
        [[ "$skip_prompt" != "true" ]] && log_info "  4. Generate PROMPT.md and AGENT.md"
        log_info "  5. Create git commit"
        return 0
    fi

    # Initialize beads if needed
    if [[ "$beads_exists" != "true" ]]; then
        log_info "Initializing beads..."
        if [[ -n "$prefix" ]]; then
            bd init --prefix "$prefix"
        else
            bd init
        fi
    fi

    # Import plan
    log_info "Importing plan from ${plan_file}..."
    if ! bd import -i "$plan_file"; then
        _log_error_console "Import failed"
        return 1
    fi

    # Sync state
    log_info "Syncing beads state..."
    bd sync

    # Validate import
    local epic_count task_count ready_count
    epic_count=$(bd list --type epic --count 2>/dev/null || echo "0")
    task_count=$(bd list --type task --count 2>/dev/null || echo "0")
    ready_count=$(bd ready --count 2>/dev/null || echo "0")

    log_success "Import complete:"
    log_info "  Epics: ${epic_count}"
    log_info "  Tasks: ${task_count}"
    log_info "  Ready: ${ready_count}"

    # Generate PROMPT.md and AGENT.md (if not skipped)
    if [[ "$skip_prompt" != "true" ]]; then
        log_info "Generating prompt.md and agent.md..."
        _generate_prompt_md "$session_dir"
        _generate_agent_md "$session_dir"
    fi

    # Update session status
    pipeline_update_session "$session_id" "bootstrap" "complete"

    # Create git commit
    log_info "Creating bootstrap commit..."
    git add .beads/
    [[ -f "${PROJECT_DIR}/.cub/prompt.md" ]] && git add .cub/prompt.md
    [[ -f "${PROJECT_DIR}/.cub/agent.md" ]] && git add .cub/agent.md

    git commit -m "chore: bootstrap beads from cub prep

Session: ${session_id}
Imported: ${epic_count} epics, ${task_count} tasks

Generated by: cub bootstrap" || true

    # Summary
    echo ""
    log_success "Bootstrap complete!"
    echo ""
    log_info "Next steps:"
    log_info "  1. Review tasks: bd ready"
    log_info "  2. Start work: cub run"

    return 0
}

_generate_prompt_md() {
    local session_dir="$1"
    local triage_file="${session_dir}/triage.md"
    local architect_file="${session_dir}/architect.md"
    local output_file
    output_file=$(get_prompt_file "${PROJECT_DIR}")

    # Extract key sections from triage and architect
    cat > "$output_file" <<EOF
# Project Prompt

This file provides context for AI coding agents working on this project.

## Overview

$(grep -A5 "## Executive Summary" "$triage_file" 2>/dev/null | tail -n+2 || echo "See triage.md for details.")

## Problem Statement

$(grep -A5 "## Problem Statement" "$triage_file" 2>/dev/null | tail -n+2 || echo "See triage.md for details.")

## Technical Approach

$(grep -A10 "## Technical Summary" "$architect_file" 2>/dev/null | tail -n+2 || echo "See architect.md for details.")

## Architecture

$(grep -A20 "## System Architecture" "$architect_file" 2>/dev/null | tail -n+2 || echo "See architect.md for details.")

## Requirements

### P0 (Must Have)
$(grep -A10 "### P0" "$triage_file" 2>/dev/null | tail -n+2 | head -5 || echo "See triage.md")

## Constraints

$(grep -A5 "## Constraints" "$triage_file" 2>/dev/null | tail -n+2 || echo "None specified.")

---

Generated by cub prep. Session artifacts in .cub/sessions/
EOF

    log_debug "  Created prompt.md"
}

_generate_agent_md() {
    local session_dir="$1"
    local output_file
    output_file=$(get_agent_file "${PROJECT_DIR}")

    # Check if agent.md already exists
    if [[ -f "$output_file" ]]; then
        log_debug "  agent.md already exists, skipping"
        return 0
    fi

    # Generate basic agent.md template
    cat > "$output_file" <<EOF
# Agent Instructions

This file contains instructions for AI agents working on this project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of the project -->

## Tech Stack

- **Language**:
- **Framework**:
- **Database**:

## Development Setup

\`\`\`bash
# Setup commands
\`\`\`

## Running the Project

\`\`\`bash
# Run commands
\`\`\`

## Feedback Loops

Run these before committing:

\`\`\`bash
# Tests
# Type checking
# Linting
\`\`\`

## Common Commands

\`\`\`bash
# Frequently used commands
\`\`\`

---

Generated by cub prep. Customize based on your project.
EOF

    log_debug "  Created agent.md"
}

_bootstrap_help() {
    cat <<EOF
Usage: cub bootstrap [OPTIONS] [SESSION_ID]

Stage 4: Transition to Execution

Initialize beads and import the generated plan.

Arguments:
  SESSION_ID         Session ID from plan (default: most recent)

Options:
  --prefix PREFIX    Beads prefix for issue IDs
  --skip-prompt      Don't generate PROMPT.md and AGENT.md
  --dry-run          Preview actions without executing
  -h, --help         Show this help message

Examples:
  cub bootstrap                        # Bootstrap most recent session
  cub bootstrap --dry-run              # Preview bootstrap actions
  cub bootstrap --prefix myproj        # Use custom prefix

Actions:
  1. Run pre-flight checks (git, tools)
  2. Initialize beads (if needed)
  3. Import plan.jsonl
  4. Generate PROMPT.md and AGENT.md
  5. Create git commit

Next Step:
  cub run    # Start autonomous execution
EOF
}

# ============================================================================
# Unified Prep Command (cmd_prep)
# ============================================================================

cmd_prep() {
    local prefix=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --prefix)
                prefix="$2"
                shift 2
                ;;
            --prefix=*)
                prefix="${1#--prefix=}"
                shift
                ;;
            --help|-h)
                _prep_help
                return 0
                ;;
            -*)
                _log_error_console "Unknown option: $1"
                _prep_help
                return 1
                ;;
            *)
                # Ignore positional args (vision path is found by skill)
                shift
                ;;
        esac
    done

    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "         CUB VISION-TO-TASKS PREP"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Stage 1: Triage
    log_info "[1/4] TRIAGE - Requirements Refinement"
    echo ""

    if ! cmd_triage; then
        _log_error_console "Triage failed. Prep stopped."
        return 1
    fi

    local session_id
    session_id=$(pipeline_most_recent_session)

    echo ""
    log_success "✓ Triage complete"
    echo ""

    # Stage 2: Architect
    log_info "[2/4] ARCHITECT - Technical Design"
    echo ""

    if ! cmd_architect --session "$session_id"; then
        _log_error_console "Architecture failed. Prep stopped."
        return 1
    fi

    echo ""
    log_success "✓ Architecture complete"
    echo ""

    # Stage 3: Plan
    log_info "[3/4] PLAN - Task Decomposition"
    echo ""

    if ! cmd_plan --session "$session_id"; then
        _log_error_console "Planning failed. Prep stopped."
        return 1
    fi

    echo ""
    log_success "✓ Plan generated"
    echo ""

    # Stage 4: Bootstrap
    log_info "[4/4] BOOTSTRAP - Initialize Beads"
    echo ""

    local bootstrap_args=("$session_id")
    [[ -n "$prefix" ]] && bootstrap_args=("--prefix" "$prefix" "${bootstrap_args[@]}")

    if ! cmd_bootstrap "${bootstrap_args[@]}"; then
        _log_error_console "Bootstrap failed. Pipeline stopped."
        return 1
    fi

    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_success "         PIPELINE COMPLETE"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    log_info "Session: ${session_id}"
    log_info "Artifacts: .cub/sessions/${session_id}/"
    echo ""
    log_info "Ready to start: cub run"
    echo ""

    return 0
}

_prep_help() {
    cat <<EOF
Usage: cub prep [OPTIONS]

Run the complete Vision-to-Tasks prep pipeline.

Each stage launches an interactive Claude session using skills installed
in .claude/commands/. Questions are asked one at a time.

Stages:
  1. Triage    - Interactive requirements refinement (/cub:triage)
  2. Architect - Interactive technical design (/cub:architect)
  3. Plan      - Interactive task decomposition (/cub:plan)
  4. Bootstrap - Initialize beads and import tasks (shell)

Options:
  --prefix PREFIX    Task ID prefix for beads import
  -h, --help         Show this help message

Examples:
  cub prep                        # Run full prep workflow
  cub prep --prefix myproj        # Use custom task ID prefix

Output:
  .cub/sessions/{session-id}/
    ├── triage.md            # Refined requirements
    ├── architect.md         # Technical design
    ├── plan.jsonl           # Beads-compatible tasks
    └── plan.md              # Human-readable plan

Next:
  cub run              # Start autonomous execution
EOF
}

# ============================================================================
# Sessions Management (cmd_sessions)
# ============================================================================

cmd_sessions() {
    local subcommand="${1:-list}"
    shift || true

    case "$subcommand" in
        list|ls)
            _sessions_list "$@"
            ;;
        show)
            _sessions_show "$@"
            ;;
        delete|rm)
            _sessions_delete "$@"
            ;;
        --help|-h|help)
            _sessions_help
            ;;
        *)
            _log_error_console "Unknown sessions subcommand: ${subcommand}"
            _sessions_help
            return 1
            ;;
    esac
}

_sessions_list() {
    local sessions
    sessions=$(pipeline_list_sessions)

    if [[ -z "$sessions" ]]; then
        log_info "No sessions found."
        log_info "Run 'cub triage' to create a session."
        return 0
    fi

    echo ""
    log_info "Pipeline Sessions"
    echo ""
    printf "%-30s %-10s %-10s %-10s %-10s\n" "SESSION ID" "TRIAGE" "ARCHITECT" "PLAN" "BOOTSTRAP"
    printf "%-30s %-10s %-10s %-10s %-10s\n" "----------" "------" "---------" "----" "---------"

    for session in $sessions; do
        local triage_status="-"
        local architect_status="-"
        local plan_status="-"
        local bootstrap_status="-"

        pipeline_has_triage "$session" && triage_status="✓"
        pipeline_has_architect "$session" && architect_status="✓"
        pipeline_has_plan "$session" && plan_status="✓"

        local session_dir
        session_dir=$(pipeline_session_dir "$session")
        local session_file="${session_dir}/session.json"
        if [[ -f "$session_file" ]]; then
            local bs_status
            bs_status=$(jq -r '.stages.bootstrap // "-"' "$session_file" 2>/dev/null)
            [[ "$bs_status" == "complete" ]] && bootstrap_status="✓"
        fi

        printf "%-30s %-10s %-10s %-10s %-10s\n" "$session" "$triage_status" "$architect_status" "$plan_status" "$bootstrap_status"
    done
    echo ""
}

_sessions_show() {
    local session_id="${1:-}"

    if [[ -z "$session_id" ]]; then
        session_id=$(pipeline_most_recent_session)
        if [[ -z "$session_id" ]]; then
            _log_error_console "No session specified and no sessions found."
            return 1
        fi
    fi

    if ! pipeline_session_exists "$session_id"; then
        _log_error_console "Session not found: ${session_id}"
        return 1
    fi

    local session_dir
    session_dir=$(pipeline_session_dir "$session_id")

    echo ""
    log_info "Session: ${session_id}"
    echo ""
    log_info "Directory: ${session_dir}"
    echo ""
    log_info "Artifacts:"

    [[ -f "${session_dir}/triage.md" ]] && echo "  ✓ triage.md"
    [[ -f "${session_dir}/architect.md" ]] && echo "  ✓ architect.md"
    [[ -f "${session_dir}/plan.jsonl" ]] && echo "  ✓ plan.jsonl"
    [[ -f "${session_dir}/plan.md" ]] && echo "  ✓ plan.md"
    [[ -f "${session_dir}/session.json" ]] && echo "  ✓ session.json"

    echo ""

    if [[ -f "${session_dir}/session.json" ]]; then
        log_info "Session Info:"
        jq '.' "${session_dir}/session.json"
    fi
}

_sessions_delete() {
    local session_id="${1:-}"

    if [[ -z "$session_id" ]]; then
        _log_error_console "Session ID required for delete."
        return 1
    fi

    if ! pipeline_session_exists "$session_id"; then
        _log_error_console "Session not found: ${session_id}"
        return 1
    fi

    local session_dir
    session_dir=$(pipeline_session_dir "$session_id")

    log_warn "Deleting session: ${session_id}"
    rm -rf "$session_dir"
    log_success "Session deleted."
}

_sessions_help() {
    cat <<EOF
Usage: cub sessions [COMMAND] [OPTIONS]

Manage prep sessions.

Commands:
  list, ls           List all sessions (default)
  show [SESSION]     Show session details
  delete, rm SESSION Delete a session

Examples:
  cub sessions                      # List all sessions
  cub sessions show                 # Show most recent session
  cub sessions show myproj-...      # Show specific session
  cub sessions delete myproj-...    # Delete session
EOF
}

# ============================================================================
# Validate Command (cmd_validate)
# ============================================================================

cmd_validate() {
    local fix="false"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --fix)
                fix="true"
                shift
                ;;
            --help|-h)
                _validate_help
                return 0
                ;;
            *)
                _log_error_console "Unknown option: $1"
                return 1
                ;;
        esac
    done

    log_info "Validating beads state..."

    local issues_found=0

    # Check beads exists
    if [[ ! -d "${PROJECT_DIR}/.beads" ]]; then
        _log_error_console "No .beads directory found. Run 'cub bootstrap' first."
        return 1
    fi

    # Check for orphaned tasks (no parent)
    log_info "Checking for orphaned tasks..."
    local orphans
    orphans=$(bd list --type task 2>/dev/null | while read -r line; do
        local task_id
        task_id=$(echo "$line" | awk '{print $2}')
        if ! bd show "$task_id" 2>/dev/null | grep -q "parent-child"; then
            echo "$task_id"
        fi
    done)

    if [[ -n "$orphans" ]]; then
        log_warn "Found orphaned tasks (no parent):"
        echo "$orphans"
        ((issues_found++))
    fi

    # Check for circular dependencies
    log_info "Checking for circular dependencies..."
    if bd dep cycles 2>/dev/null | grep -q "cycle"; then
        log_warn "Circular dependencies detected!"
        bd dep cycles
        ((issues_found++))
    fi

    # Check for missing labels
    log_info "Checking for missing labels..."
    # Use process substitution to avoid subshell (preserves issues_found increments)
    while read -r line; do
        local task_id
        task_id=$(echo "$line" | awk '{print $2}')
        local labels
        labels=$(bd show "$task_id" 2>/dev/null | grep "Labels:" || echo "")

        if ! echo "$labels" | grep -q "model:"; then
            log_warn "Task $task_id missing model label"
            ((issues_found++))
        fi
        if ! echo "$labels" | grep -q "phase-"; then
            log_warn "Task $task_id missing phase label"
            ((issues_found++))
        fi
    done < <(bd list --type task 2>/dev/null)

    if [[ $issues_found -eq 0 ]]; then
        log_success "Validation complete. No issues found."
    else
        log_warn "Validation complete. ${issues_found} issue(s) found."
        if [[ "$fix" == "true" ]]; then
            log_info "Auto-fix not yet implemented for these issues."
        else
            log_info "Run 'cub validate --fix' to attempt auto-fixes."
        fi
    fi

    return 0
}

_validate_help() {
    cat <<EOF
Usage: cub validate [OPTIONS]

Validate beads state and task relationships.

Options:
  --fix              Attempt to auto-fix issues
  -h, --help         Show this help message

Checks:
  - Orphaned tasks (no parent epic)
  - Circular dependencies
  - Missing required labels (model, phase)
  - Invalid task references
EOF
}

# ============================================================================
# Migrate-Layout Command (cmd_migrate_layout)
# Migrate projects from legacy layout (root-level files) to new layout (.cub/)
# ============================================================================

cmd_migrate_layout() {
    local dry_run=false

    # Parse flags
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                dry_run=true
                shift
                ;;
            --help|-h|help)
                _migrate_layout_help
                return 0
                ;;
            *)
                _log_error_console "Unknown option: $1"
                _migrate_layout_help
                return 1
                ;;
        esac
    done

    _migrate_layout_impl "$dry_run"
}

_migrate_layout_impl() {
    local dry_run="$1"
    local cub_dir="${PROJECT_DIR}/.cub"
    local action="Migrating"

    # Check if project is already in new layout
    if [[ -f "${cub_dir}/prompt.md" ]]; then
        log_info "Project is already in new layout (.cub/)"
        return 0
    fi

    # Check if any legacy files exist
    local has_legacy=false
    if [[ -f "${PROJECT_DIR}/PROMPT.md" ]] || \
       [[ -f "${PROJECT_DIR}/AGENT.md" ]] || \
       [[ -f "${PROJECT_DIR}/CLAUDE.md" ]] || \
       [[ -f "${PROJECT_DIR}/progress.txt" ]] || \
       [[ -f "${PROJECT_DIR}/@progress.txt" ]] || \
       [[ -f "${PROJECT_DIR}/fix_plan.md" ]] || \
       [[ -f "${PROJECT_DIR}/prd.json" ]] || \
       [[ -f "${PROJECT_DIR}/.cub.json" ]]; then
        has_legacy=true
    fi

    if [[ "$has_legacy" != "true" ]]; then
        log_info "No legacy layout files found to migrate"
        return 0
    fi

    if [[ "$dry_run" == "true" ]]; then
        action="Would migrate"
    fi

    log_info "${action} legacy layout to new layout (.cub/)..."

    # Create .cub directory if it doesn't exist
    if [[ "$dry_run" != "true" ]]; then
        mkdir -p "$cub_dir"
    fi

    # Migrate PROMPT.md
    if [[ -f "${PROJECT_DIR}/PROMPT.md" ]]; then
        log_info "  ${action} PROMPT.md → .cub/prompt.md"
        if [[ "$dry_run" != "true" ]]; then
            # If PROMPT.md is a symlink, get the target and use the actual file
            if [[ -L "${PROJECT_DIR}/PROMPT.md" ]]; then
                local target
                target=$(readlink "${PROJECT_DIR}/PROMPT.md")
                if [[ -f "${PROJECT_DIR}/${target}" ]]; then
                    cp "${PROJECT_DIR}/${target}" "${cub_dir}/prompt.md"
                fi
            else
                cp "${PROJECT_DIR}/PROMPT.md" "${cub_dir}/prompt.md"
            fi
        fi
    fi

    # Migrate AGENT.md or CLAUDE.md
    if [[ -f "${PROJECT_DIR}/AGENT.md" ]]; then
        log_info "  ${action} AGENT.md → .cub/agent.md"
        if [[ "$dry_run" != "true" ]]; then
            if [[ -L "${PROJECT_DIR}/AGENT.md" ]]; then
                local target
                target=$(readlink "${PROJECT_DIR}/AGENT.md")
                if [[ -f "${PROJECT_DIR}/${target}" ]]; then
                    cp "${PROJECT_DIR}/${target}" "${cub_dir}/agent.md"
                fi
            else
                cp "${PROJECT_DIR}/AGENT.md" "${cub_dir}/agent.md"
            fi
        fi
    elif [[ -f "${PROJECT_DIR}/CLAUDE.md" ]]; then
        log_info "  ${action} CLAUDE.md → .cub/agent.md"
        if [[ "$dry_run" != "true" ]]; then
            if [[ -L "${PROJECT_DIR}/CLAUDE.md" ]]; then
                local target
                target=$(readlink "${PROJECT_DIR}/CLAUDE.md")
                if [[ -f "${PROJECT_DIR}/${target}" ]]; then
                    cp "${PROJECT_DIR}/${target}" "${cub_dir}/agent.md"
                fi
            else
                cp "${PROJECT_DIR}/CLAUDE.md" "${cub_dir}/agent.md"
            fi
        fi
    fi

    # Migrate progress.txt (to .cub/progress.txt)
    if [[ -f "${PROJECT_DIR}/progress.txt" ]]; then
        log_info "  ${action} progress.txt → .cub/progress.txt"
        if [[ "$dry_run" != "true" ]]; then
            cp "${PROJECT_DIR}/progress.txt" "${cub_dir}/progress.txt"
        fi
    fi

    # Migrate @progress.txt (to .cub/progress.txt if progress.txt doesn't exist)
    if [[ -f "${PROJECT_DIR}/@progress.txt" ]] && [[ ! -f "${PROJECT_DIR}/progress.txt" ]]; then
        log_info "  ${action} @progress.txt → .cub/progress.txt"
        if [[ "$dry_run" != "true" ]]; then
            cp "${PROJECT_DIR}/@progress.txt" "${cub_dir}/progress.txt"
        fi
    fi

    # Migrate fix_plan.md
    if [[ -f "${PROJECT_DIR}/fix_plan.md" ]]; then
        log_info "  ${action} fix_plan.md → .cub/fix_plan.md"
        if [[ "$dry_run" != "true" ]]; then
            cp "${PROJECT_DIR}/fix_plan.md" "${cub_dir}/fix_plan.md"
        fi
    fi

    # Migrate prd.json
    if [[ -f "${PROJECT_DIR}/prd.json" ]]; then
        log_info "  ${action} prd.json → .cub/prd.json"
        if [[ "$dry_run" != "true" ]]; then
            cp "${PROJECT_DIR}/prd.json" "${cub_dir}/prd.json"
        fi
    fi

    # Migrate .cub.json (project config)
    if [[ -f "${PROJECT_DIR}/.cub.json" ]]; then
        log_info "  ${action} .cub.json → .cub/.cub.json"
        if [[ "$dry_run" != "true" ]]; then
            cp "${PROJECT_DIR}/.cub.json" "${cub_dir}/.cub.json"
        fi
    fi

    if [[ "$dry_run" == "true" ]]; then
        log_info "DRY RUN: No changes made. Run without --dry-run to complete migration."
        return 0
    fi

    # Create symlinks for backwards compatibility (optional but helpful)
    if [[ -f "${cub_dir}/prompt.md" ]] && [[ ! -L "${PROJECT_DIR}/PROMPT.md" ]] && [[ ! -f "${PROJECT_DIR}/PROMPT.md" ]]; then
        log_info "Creating backwards-compatibility symlinks..."
        ln -s ".cub/prompt.md" "${PROJECT_DIR}/PROMPT.md"
    fi

    if [[ -f "${cub_dir}/agent.md" ]]; then
        if [[ ! -L "${PROJECT_DIR}/AGENT.md" ]] && [[ ! -f "${PROJECT_DIR}/AGENT.md" ]]; then
            ln -s ".cub/agent.md" "${PROJECT_DIR}/AGENT.md"
        fi
        if [[ ! -L "${PROJECT_DIR}/CLAUDE.md" ]] && [[ ! -f "${PROJECT_DIR}/CLAUDE.md" ]]; then
            ln -s ".cub/agent.md" "${PROJECT_DIR}/CLAUDE.md"
        fi
    fi

    log_success "Migration complete!"
    log_info "Files moved from root to .cub/ directory"
    log_info "Backwards-compatibility symlinks created"
    log_info "Project now uses new layout organization"

    return 0
}

_migrate_layout_help() {
    cat <<EOF
Usage: cub migrate-layout [OPTIONS]

Migrate project from legacy layout (root-level files) to new layout (.cub/ subdirectory).

This command moves the following files to .cub/:
  - PROMPT.md → .cub/prompt.md
  - AGENT.md/CLAUDE.md → .cub/agent.md
  - progress.txt/@progress.txt → .cub/progress.txt
  - fix_plan.md → .cub/fix_plan.md
  - prd.json → .cub/prd.json
  - .cub.json → .cub/.cub.json

Options:
  --dry-run              Show what would be migrated without making changes
  --help, -h             Show this help message

Examples:
  cub migrate-layout                     # Perform migration
  cub migrate-layout --dry-run           # Preview changes
EOF
}

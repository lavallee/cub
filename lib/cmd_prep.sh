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
    local vision_path=""
    local depth="standard"
    local session_id=""
    local resume_session=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --depth)
                depth="$2"
                shift 2
                ;;
            --depth=*)
                depth="${1#--depth=}"
                shift
                ;;
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
                vision_path="$1"
                shift
                ;;
        esac
    done

    # Validate depth
    case "$depth" in
        light|standard|deep) ;;
        *)
            _log_error_console "Invalid depth: $depth (must be light, standard, or deep)"
            return 1
            ;;
    esac

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

    # Find vision document
    local vision_doc
    if ! vision_doc=$(pipeline_find_vision "$vision_path"); then
        log_warn "No vision document found. Please provide a path or create VISION.md"
        vision_doc=""
    fi

    # Check for existing codebase
    local is_existing_project="false"
    if [[ -f "${PROJECT_DIR}/package.json" ]] || \
       [[ -f "${PROJECT_DIR}/Cargo.toml" ]] || \
       [[ -f "${PROJECT_DIR}/go.mod" ]] || \
       [[ -f "${PROJECT_DIR}/requirements.txt" ]] || \
       [[ -d "${PROJECT_DIR}/src" ]] || \
       [[ -d "${PROJECT_DIR}/lib" ]]; then
        is_existing_project="true"
    fi

    # Build the triage prompt
    local prompt
    prompt=$(_build_triage_prompt "$vision_doc" "$depth" "$session_id" "$is_existing_project")

    # Run triage with Claude
    log_info "Running triage interview (depth: ${depth})..."

    local output_file="${session_dir}/triage.md"

    # Pipe prompt to Claude and capture output
    if echo "$prompt" | claude --print > "${session_dir}/.triage_response.txt" 2>&1; then
        # The prompt instructs Claude to write the file directly
        if [[ -f "$output_file" ]]; then
            pipeline_update_session "$session_id" "triage" "complete"
            log_success "Triage complete!"
            log_info "Output: ${output_file}"
            log_info "Next step: cub architect ${session_id}"
        else
            log_warn "Triage session completed but output file not created."
            log_info "Response saved to: ${session_dir}/.triage_response.txt"
        fi
    else
        _log_error_console "Triage failed"
        return 1
    fi

    return 0
}

_build_triage_prompt() {
    local vision_doc="$1"
    local depth="$2"
    local session_id="$3"
    local is_existing_project="$4"

    local vision_content=""
    if [[ -n "$vision_doc" && -f "$vision_doc" ]]; then
        vision_content=$(cat "$vision_doc")
    fi

    cat <<EOF
You are the **Triage Agent**. Your role is to ensure product clarity before technical work begins.

Your job is to review the product vision, identify gaps, challenge assumptions, and produce a refined requirements document.

## Session Information

- **Session ID:** ${session_id}
- **Session Directory:** .cub/sessions/${session_id}/
- **Output File:** .cub/sessions/${session_id}/triage.md
- **Triage Depth:** ${depth}
- **Existing Project:** ${is_existing_project}

## Vision Document

${vision_content:-No vision document provided. Please ask the user to describe their idea.}

## Instructions

1. **Review the vision** - Understand what the user wants to build
2. **Conduct interview** - Ask clarifying questions based on the triage depth:
   - Light (5 min): Basic coherence check
   - Standard (15 min): Full product review with gap analysis
   - Deep (30 min): Include market analysis and feasibility
3. **Synthesize requirements** - Organize into P0/P1/P2 priorities
4. **Document risks** - Identify what could go wrong
5. **Write output** - Create triage.md in the session directory

## Interview Questions

Ask these questions, waiting for response after each:

1. **Triage Depth**: How thorough should this review be? (Light/Standard/Deep)
2. **Core Problem**: In one sentence, what problem does this solve? Who has it?
3. **Success Criteria**: How will you know this project succeeded?
4. **Constraints**: Hard constraints? (timeline, budget, tech, regulations)

## Output Template

Write the output to: .cub/sessions/${session_id}/triage.md

Use this structure:

\`\`\`markdown
# Triage Report: {Project Name}

**Session:** ${session_id}
**Date:** $(date +%Y-%m-%d)
**Triage Depth:** ${depth}
**Status:** Approved

---

## Executive Summary
{2-3 sentence summary}

## Problem Statement
{Clear articulation of the problem}

## Requirements

### P0 - Must Have
- {requirement}

### P1 - Should Have
- {requirement}

### P2 - Nice to Have
- {requirement}

## Constraints
- {constraint}

## Assumptions
- {assumption}

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| {risk} | {H/M/L} | {strategy} |

---

**Next Step:** Run \`cub architect ${session_id}\` to proceed to technical design.
\`\`\`

Begin the triage interview now.
EOF
}

_triage_help() {
    cat <<EOF
Usage: cub triage [OPTIONS] [VISION.md]

Stage 1: Requirements Refinement

Conduct a product triage interview to clarify requirements, identify gaps,
and produce a refined requirements document.

Arguments:
  VISION.md          Path to vision/PRD document (optional)

Options:
  --depth LEVEL      Triage depth: light, standard (default), or deep
  --session ID       Resume an existing session
  -h, --help         Show this help message

Examples:
  cub triage                      # Interactive triage, find vision doc
  cub triage VISION.md            # Triage from specific document
  cub triage --depth deep         # Deep triage with market analysis
  cub triage --session myproj-... # Resume existing session

Output:
  .cub/sessions/{session-id}/triage.md

Next Step:
  cub architect {session-id}
EOF
}

# ============================================================================
# Architect Stage (cmd_architect)
# ============================================================================

cmd_architect() {
    local session_id=""
    local mindset=""
    local scale=""
    local review="false"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --mindset)
                mindset="$2"
                shift 2
                ;;
            --mindset=*)
                mindset="${1#--mindset=}"
                shift
                ;;
            --scale)
                scale="$2"
                shift 2
                ;;
            --scale=*)
                scale="${1#--scale=}"
                shift
                ;;
            --review)
                review="true"
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

    # Read triage output
    local triage_content
    triage_content=$(cat "${session_dir}/triage.md")

    # Build architect prompt
    local prompt
    prompt=$(_build_architect_prompt "$session_id" "$triage_content" "$mindset" "$scale")

    # Run architect with Claude
    log_info "Running architecture design..."

    local output_file="${session_dir}/architect.md"

    if echo "$prompt" | claude --print > "${session_dir}/.architect_response.txt" 2>&1; then
        if [[ -f "$output_file" ]]; then
            pipeline_update_session "$session_id" "architect" "complete"
            log_success "Architecture design complete!"
            log_info "Output: ${output_file}"

            # If --review flag is set, validate the architect output
            if [[ "$review" == "true" ]]; then
                _architect_review "$session_id" "$session_dir"
                if [[ $? -ne 0 ]]; then
                    log_warn "Architecture review found issues. Review: ${session_dir}/architect_review.md"
                fi
            fi

            log_info "Next step: cub plan ${session_id}"
        else
            log_warn "Architect session completed but output file not created."
            log_info "Response saved to: ${session_dir}/.architect_response.txt"
        fi
    else
        _log_error_console "Architecture design failed"
        return 1
    fi

    return 0
}

_build_architect_prompt() {
    local session_id="$1"
    local triage_content="$2"
    local mindset="$3"
    local scale="$4"

    cat <<EOF
You are the **Architect Agent**. Your role is to translate product requirements into a technical design.

## Session Information

- **Session ID:** ${session_id}
- **Session Directory:** .cub/sessions/${session_id}/
- **Output File:** .cub/sessions/${session_id}/architect.md

## Triage Output

${triage_content}

## Instructions

1. **Analyze context** - Is this a new project or extending existing code?
2. **Conduct interview** - Ask about mindset and scale if not provided
3. **Design architecture** - Create a pragmatic technical design
4. **Identify risks** - Document what could be hard or uncertain
5. **Write output** - Create architect.md in the session directory

## Interview Questions

Ask these questions, waiting for response after each:

1. **Technical Mindset**: What context for this project?
   - Prototype: Speed first, shortcuts OK
   - MVP: Balance speed and quality
   - Production: Quality first, maintainable
   - Enterprise: Maximum rigor, security, compliance
   ${mindset:+\n   (User specified: ${mindset})}

2. **Scale Expectations**: What usage anticipated?
   - Personal: Just you (1 user)
   - Team: 10-100 users
   - Product: 1,000+ users
   - Internet-scale: Millions of users
   ${scale:+\n   (User specified: ${scale})}

3. **Tech Stack**: Preferences or constraints?
4. **Integrations**: External systems to connect?

## Output Template

Write the output to: .cub/sessions/${session_id}/architect.md

Use this structure:

\`\`\`markdown
# Architecture Design: {Project Name}

**Session:** ${session_id}
**Date:** $(date +%Y-%m-%d)
**Mindset:** {prototype|mvp|production|enterprise}
**Scale:** {personal|team|product|internet}
**Status:** Approved

---

## Technical Summary
{2-3 paragraph overview}

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | {choice} | {why} |
| Framework | {choice} | {why} |
| Database | {choice} | {why} |

## System Architecture

\`\`\`
{ASCII diagram}
\`\`\`

## Components

### {Component Name}
- **Purpose:** {what it does}
- **Responsibilities:** {list}
- **Interface:** {how others interact}

## Data Model

### {Entity Name}
{fields and types}

## Implementation Phases

### Phase 1: {Name}
**Goal:** {what this achieves}
- {task}

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| {risk} | {H/M/L} | {H/M/L} | {strategy} |

---

**Next Step:** Run \`cub plan ${session_id}\` to generate implementation tasks.
\`\`\`

Begin the architecture design now.
EOF
}

_architect_review() {
    local session_id="$1"
    local session_dir="$2"
    local architect_file="${session_dir}/architect.md"
    local review_file="${session_dir}/architect_review.md"

    log_info "Reviewing architecture design..."

    # Initialize review report
    {
        echo "# Architecture Review"
        echo ""
        echo "Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        echo ""
    } > "$review_file"

    local has_concerns=false

    # ========================================================================
    # PHASE 1: BASIC CHECKS (HAIKU - Fast, Cost-Effective)
    # ========================================================================
    echo "## Basic Structure Validation" >> "$review_file"
    echo "" >> "$review_file"

    local missing_sections=()
    for section in "Technical Summary" "Technology Stack" "System Architecture" "Components"; do
        if ! grep -q "## $section" "$architect_file"; then
            missing_sections+=("$section")
            has_concerns=true
        fi
    done

    if [[ ${#missing_sections[@]} -eq 0 ]]; then
        echo "✓ **PASS**: All required sections present" >> "$review_file"
        log_info "✓ Structure validation passed"
    else
        echo "⚠ **CONCERNS**: Missing sections:" >> "$review_file"
        printf ' - %s\n' "${missing_sections[@]}" >> "$review_file"
        log_warn "⚠ Architecture missing sections: ${missing_sections[*]}"
    fi
    echo "" >> "$review_file"

    # Check 2: Technical clarity
    echo "## Technical Clarity" >> "$review_file"
    echo "" >> "$review_file"

    local word_count
    word_count=$(wc -w < "$architect_file")

    if [[ $word_count -ge 500 ]]; then
        echo "✓ **PASS**: Sufficient technical depth (${word_count} words)" >> "$review_file"
        log_info "✓ Technical clarity validated"
    else
        echo "⚠ **CONCERNS**: Limited technical detail (only ${word_count} words, recommended 500+)" >> "$review_file"
        has_concerns=true
        log_warn "⚠ Architecture lacks sufficient technical depth"
    fi
    echo "" >> "$review_file"

    # Check 3: Risk assessment
    echo "## Risk Assessment" >> "$review_file"
    echo "" >> "$review_file"

    if grep -q "## Technical Risks\|risk\|Risk" "$architect_file"; then
        echo "✓ **PASS**: Risks identified and documented" >> "$review_file"
        log_info "✓ Risk assessment found"
    else
        echo "⚠ **CONCERNS**: No explicit risk documentation" >> "$review_file"
        has_concerns=true
        log_warn "⚠ Architecture lacks explicit risk assessment"
    fi
    echo "" >> "$review_file"

    # ========================================================================
    # PHASE 2: DEEP AI-ASSISTED ANALYSIS (SONNET - Capable, Thorough)
    # ========================================================================
    local ai_review_result
    ai_review_result=$(_architect_deep_review "$session_id" "$architect_file" 2>/dev/null || echo "")

    if [[ -n "$ai_review_result" ]]; then
        echo "## AI-Assisted Architecture Analysis" >> "$review_file"
        echo "" >> "$review_file"
        echo "$ai_review_result" >> "$review_file"
        echo "" >> "$review_file"

        # Update concerns flag if AI found any
        if echo "$ai_review_result" | grep -q "CONCERNS\|⚠"; then
            has_concerns=true
        fi
    fi

    # Generate verdict
    echo "## Verdict" >> "$review_file"
    echo "" >> "$review_file"

    local verdict="PASS"
    if [[ "$has_concerns" == "true" ]]; then
        verdict="CONCERNS"
    fi

    # Check for strict mode
    local plan_strict
    plan_strict=$(config_get_or "review.plan_strict" "false")
    local block_on_concerns
    block_on_concerns=$(config_get_or "review.block_on_concerns" "false")

    case "$verdict" in
        PASS)
            echo "✓ **PASS**: Architecture is well-defined and ready for planning." >> "$review_file"
            log_info "✓ VERDICT: PASS - Architecture ready for planning"
            return 0
            ;;
        CONCERNS)
            echo "⚠ **CONCERNS**: Architecture has issues but can proceed. Review recommended." >> "$review_file"

            # In strict mode, pause for review on concerns
            if [[ "$plan_strict" == "true" ]]; then
                echo "" >> "$review_file"
                echo "**STRICT MODE**: Pausing for review of architecture concerns." >> "$review_file"
                log_warn "⚠ STRICT MODE: Pausing for architecture review"

                # Prompt user to review
                echo ""
                echo "Architecture review found concerns. Review details in: $review_file"
                read -p "Review architecture concerns and press Enter to continue, or Ctrl+C to abort: "
            fi

            log_warn "⚠ VERDICT: CONCERNS - Review issues before planning"
            return 1
            ;;
    esac
}

# AI-assisted deep review of architecture (uses SONNET model for thorough analysis)
#
# Model Selection Strategy:
# - PHASE 1 (HAIKU): Basic structure/format checks (fast, cost-effective)
#   - Section validation, word count, keyword matching
#   - Deterministic rules that don't require AI
# - PHASE 2 (SONNET): Deep feasibility and quality analysis (thorough, capable)
#   - AI-powered review of implementation feasibility, design quality, risks
#   - Requires model sophistication to understand architectural implications
#
_architect_deep_review() {
    local session_id="$1"
    local architect_file="$2"

    # Read architecture content
    local architect_content
    architect_content=$(cat "$architect_file" 2>/dev/null || echo "")

    if [[ -z "$architect_content" ]]; then
        return 1
    fi

    # Build AI review prompt
    local prompt
    prompt=$(cat <<'EOF'
You are an expert software architect reviewing a technical design document.

Please analyze this architecture for:
1. **Feasibility**: Can this be realistically implemented? Are there technical blockers?
2. **Completeness**: Are all major components addressed? Any obvious gaps?
3. **Quality**: Does the design follow best practices? Are there anti-patterns?
4. **Risks**: What are the main technical risks? Are mitigation strategies documented?

Architecture Document:
---
{{ARCHITECTURE}}
---

Provide a concise, actionable review. Format your response as:

**Feasibility**: [PASS/CONCERNS] - [brief explanation]
**Completeness**: [PASS/CONCERNS] - [brief explanation]
**Quality**: [PASS/CONCERNS] - [brief explanation]
**Risks**: [PASS/CONCERNS] - [brief explanation]

If any concerns found, include specific suggestions for improvement.
EOF
)

    # Replace placeholder
    prompt="${prompt//{{ARCHITECTURE}}/$architect_content}"

    # Invoke Claude with SONNET model for deep analysis
    # SONNET is used for deep analysis because it can:
    # - Understand architectural patterns and best practices
    # - Identify subtle feasibility issues
    # - Assess design quality beyond surface-level checks
    # - Provide sophisticated risk analysis
    # Note: CUB_MODEL may be set globally, so we override it temporarily for this review
    local sonnet_output
    sonnet_output=$(echo "$prompt" | CUB_MODEL="sonnet" claude --print 2>/dev/null || echo "")

    if [[ -n "$sonnet_output" ]]; then
        echo "$sonnet_output"
        return 0
    fi

    return 1
}

_architect_help() {
    cat <<EOF
Usage: cub architect [OPTIONS] [SESSION_ID]

Stage 2: Technical Design

Translate requirements into a pragmatic technical architecture.

Arguments:
  SESSION_ID         Session ID from triage (default: most recent)

Options:
  --mindset TYPE     prototype, mvp, production, or enterprise
  --scale LEVEL      personal, team, product, or internet
  --review           Validate architecture after generation
  -h, --help         Show this help message

Examples:
  cub architect                        # Use most recent session
  cub architect myproj-20260113-...    # Specific session
  cub architect --mindset mvp          # Specify mindset upfront
  cub architect --review               # With quality validation

Output:
  .cub/sessions/{session-id}/architect.md
  .cub/sessions/{session-id}/architect_review.md (if --review)

Next Step:
  cub plan {session-id}
EOF
}

# ============================================================================
# Plan Stage (cmd_plan)
# ============================================================================

cmd_plan() {
    local session_id=""
    local granularity="micro"
    local prefix=""
    local review="false"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --granularity)
                granularity="$2"
                shift 2
                ;;
            --granularity=*)
                granularity="${1#--granularity=}"
                shift
                ;;
            --prefix)
                prefix="$2"
                shift 2
                ;;
            --prefix=*)
                prefix="${1#--prefix=}"
                shift
                ;;
            --review)
                review="true"
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

    # Validate granularity
    case "$granularity" in
        micro|standard|macro) ;;
        *)
            _log_error_console "Invalid granularity: $granularity (must be micro, standard, or macro)"
            return 1
            ;;
    esac

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
        _log_error_console "Run 'cub architect ${session_id}' first."
        return 1
    fi

    local session_dir
    session_dir=$(pipeline_session_dir "$session_id")

    # Generate default prefix from project dir if not provided
    if [[ -z "$prefix" ]]; then
        prefix=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]//g')
        prefix="${prefix:0:8}"
    fi

    # Read previous outputs
    local triage_content architect_content
    triage_content=$(cat "${session_dir}/triage.md")
    architect_content=$(cat "${session_dir}/architect.md")

    # Build plan prompt
    local prompt
    prompt=$(_build_plan_prompt "$session_id" "$triage_content" "$architect_content" "$granularity" "$prefix")

    # Run planner with Claude
    log_info "Generating implementation plan (granularity: ${granularity})..."

    local jsonl_file="${session_dir}/plan.jsonl"
    local md_file="${session_dir}/plan.md"

    if echo "$prompt" | claude --print > "${session_dir}/.plan_response.txt" 2>&1; then
        if [[ -f "$jsonl_file" ]]; then
            pipeline_update_session "$session_id" "plan" "complete"

            # Count tasks
            local epic_count task_count
            epic_count=$(grep -c '"issue_type":"epic"' "$jsonl_file" 2>/dev/null || echo "0")
            task_count=$(grep -c '"issue_type":"task"' "$jsonl_file" 2>/dev/null || echo "0")

            log_success "Plan generated: ${epic_count} epics, ${task_count} tasks"
            log_info "JSONL: ${jsonl_file}"
            [[ -f "$md_file" ]] && log_info "Summary: ${md_file}"

            # If --review flag is set, validate the plan
            if [[ "$review" == "true" ]]; then
                _plan_review "$session_id" "$session_dir" "$jsonl_file"
                if [[ $? -ne 0 ]]; then
                    log_warn "Plan review found issues. Review: ${session_dir}/plan_review.md"
                fi
            fi

            log_info "Next step: cub bootstrap ${session_id}"
        else
            log_warn "Plan session completed but JSONL file not created."
            log_info "Response saved to: ${session_dir}/.plan_response.txt"
        fi
    else
        _log_error_console "Plan generation failed"
        return 1
    fi

    return 0
}

_build_plan_prompt() {
    local session_id="$1"
    local triage_content="$2"
    local architect_content="$3"
    local granularity="$4"
    local prefix="$5"

    cat <<EOF
You are the **Planner Agent**. Your role is to break down the architecture into executable tasks.

You output tasks in a format compatible with **Beads** task management system.

## Session Information

- **Session ID:** ${session_id}
- **Session Directory:** .cub/sessions/${session_id}/
- **JSONL Output:** .cub/sessions/${session_id}/plan.jsonl
- **Summary Output:** .cub/sessions/${session_id}/plan.md
- **Granularity:** ${granularity}
- **Task Prefix:** ${prefix}

## Triage Output

${triage_content}

## Architecture Output

${architect_content}

## Granularity Guidelines

- **Micro (15-30 min)**: Optimal for AI agents - fits one context window
- **Standard (1-2 hours)**: Good for humans or mixed workflows
- **Macro (half-day+)**: High-level milestones

## Instructions

1. Transform phases into **epics**
2. Break epics into **tasks** based on granularity
3. Apply proper **labels** and **priorities**
4. Wire **dependencies** (parent-child and blocking)
5. Generate **JSONL** file (one JSON object per line)
6. Generate **human-readable summary** (plan.md)

## Required Labels

Every task MUST have:
- \`phase-N\` - Implementation phase
- \`model:opus-4.5|sonnet|haiku\` - Recommended model
- \`complexity:high|medium|low\` - Task complexity

Optional labels:
- \`domain:setup|model|api|ui|logic|test|docs\`
- \`risk:high|medium\`
- \`checkpoint\` - Validation pause point
- \`v0.14\` - Version label

## JSONL Schema

Write to: .cub/sessions/${session_id}/plan.jsonl

Each line is a complete JSON object:

\`\`\`json
{"id":"${prefix}-001","title":"Task title","description":"## Context\\n...","status":"open","priority":2,"issue_type":"task","labels":["phase-1","model:sonnet","complexity:medium","v0.14"],"dependencies":[{"depends_on_id":"${prefix}-E01","type":"parent-child"}]}
\`\`\`

**ID Format:**
- Epics: \`${prefix}-E01\`, \`${prefix}-E02\`, etc.
- Tasks: \`${prefix}-001\`, \`${prefix}-002\`, etc.

**Dependencies Array:**
- \`parent-child\`: Links task to its epic
- \`blocks\`: Task dependency (blocked-by relationship)

## Task Description Template

\`\`\`markdown
## Context
{Why this task exists}

## Implementation Hints
**Recommended Model:** {opus-4.5|sonnet|haiku}
**Estimated Duration:** {15m|30m|1h|2h}
**Approach:** {Brief guidance}

## Implementation Steps
1. {Step}

## Acceptance Criteria
- [ ] {Criterion}

## Files Likely Involved
- {path}
\`\`\`

## Model Selection

- **opus-4.5**: Complex, security-sensitive, novel problems
- **sonnet**: Standard feature work, moderate complexity
- **haiku**: Boilerplate, repetitive, simple changes

## Summary Template

Write to: .cub/sessions/${session_id}/plan.md

\`\`\`markdown
# Implementation Plan: {Project}

**Session:** ${session_id}
**Generated:** $(date +%Y-%m-%d)
**Granularity:** ${granularity}

---

## Summary
{Overview}

## Task Hierarchy

### Phase 1: {Name}

| ID | Task | Model | Est |
|----|------|-------|-----|
| ${prefix}-001 | {title} | haiku | 15m |

## Model Distribution

| Model | Count |
|-------|-------|
| opus-4.5 | {N} |
| sonnet | {M} |
| haiku | {K} |

## Ready to Start
- ${prefix}-001: {title}

---

**Next Step:** Run \`cub bootstrap ${session_id}\` to initialize beads.
\`\`\`

Generate the plan now. First ask about task prefix if the default (${prefix}) isn't appropriate.
EOF
}

_plan_review() {
    local session_id="$1"
    local session_dir="$2"
    local jsonl_file="$3"
    local review_file="${session_dir}/plan_review.md"

    log_info "Reviewing generated plan..."

    # Initialize review report
    {
        echo "# Plan Review"
        echo ""
        echo "Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        echo ""
    } > "$review_file"

    local has_concerns=false

    # ========================================================================
    # PHASE 1: BASIC CHECKS (HAIKU - Fast, Cost-Effective)
    # ========================================================================

    # Check 1: JSONL validity
    echo "## JSONL Format Validation" >> "$review_file"
    echo "" >> "$review_file"

    local valid_lines=0
    local invalid_lines=0
    while IFS= read -r line; do
        if jq empty <<< "$line" 2>/dev/null; then
            ((valid_lines++))
        else
            ((invalid_lines++))
        fi
    done < "$jsonl_file"

    if [[ $invalid_lines -eq 0 ]]; then
        echo "✓ **PASS**: All ${valid_lines} JSONL lines are valid" >> "$review_file"
        log_info "✓ JSONL format validation passed"
    else
        echo "⚠ **CONCERNS**: ${invalid_lines} invalid JSONL lines out of $((valid_lines + invalid_lines))" >> "$review_file"
        has_concerns=true
        log_warn "⚠ Plan has invalid JSONL lines"
    fi
    echo "" >> "$review_file"

    # Check 2: Task completeness
    echo "## Task Definition Completeness" >> "$review_file"
    echo "" >> "$review_file"

    local missing_fields=0
    while IFS= read -r line; do
        # Check for required fields: id, title, description, issue_type
        if ! echo "$line" | jq -e '.id and .title and .description and .issue_type' >/dev/null 2>&1; then
            ((missing_fields++))
        fi
    done < "$jsonl_file"

    if [[ $missing_fields -eq 0 ]]; then
        echo "✓ **PASS**: All tasks have required fields (id, title, description, issue_type)" >> "$review_file"
        log_info "✓ Task completeness validation passed"
    else
        echo "⚠ **CONCERNS**: ${missing_fields} tasks missing required fields" >> "$review_file"
        has_concerns=true
        log_warn "⚠ Plan has tasks with missing fields"
    fi
    echo "" >> "$review_file"

    # Check 3: Label presence
    echo "## Label Validation" >> "$review_file"
    echo "" >> "$review_file"

    local tasks_missing_labels=0
    while IFS= read -r line; do
        # Check for at least one label
        if ! echo "$line" | jq -e '.labels and (.labels | length) > 0' >/dev/null 2>&1; then
            ((tasks_missing_labels++))
        fi
    done < "$jsonl_file"

    if [[ $tasks_missing_labels -eq 0 ]]; then
        echo "✓ **PASS**: All tasks have labels" >> "$review_file"
        log_info "✓ Label validation passed"
    else
        echo "⚠ **CONCERNS**: ${tasks_missing_labels} tasks missing labels" >> "$review_file"
        has_concerns=true
        log_warn "⚠ Plan has tasks without labels"
    fi
    echo "" >> "$review_file"

    # Check 4: Task hierarchy
    echo "## Task Hierarchy" >> "$review_file"
    echo "" >> "$review_file"

    local epic_count=0
    local task_count=0
    local other_count=0
    while IFS= read -r line; do
        local issue_type
        issue_type=$(echo "$line" | jq -r '.issue_type // "unknown"')
        case "$issue_type" in
            epic) ((epic_count++)) ;;
            task) ((task_count++)) ;;
            *) ((other_count++)) ;;
        esac
    done < "$jsonl_file"

    if [[ $epic_count -gt 0 && $task_count -gt 0 ]]; then
        echo "✓ **PASS**: Plan has ${epic_count} epics and ${task_count} tasks" >> "$review_file"
        log_info "✓ Task hierarchy valid (${epic_count} epics, ${task_count} tasks)"
    else
        if [[ $epic_count -eq 0 && $task_count -eq 0 ]]; then
            echo "⚠ **CONCERNS**: Plan has no epics or tasks" >> "$review_file"
            has_concerns=true
        elif [[ $epic_count -eq 0 ]]; then
            echo "⚠ **CONCERNS**: Plan has tasks but no epics (${task_count} tasks)" >> "$review_file"
            has_concerns=true
        else
            echo "⚠ **CONCERNS**: Plan has epics but no tasks (${epic_count} epics)" >> "$review_file"
            has_concerns=true
        fi
        log_warn "⚠ Plan hierarchy incomplete (epics: ${epic_count}, tasks: ${task_count})"
    fi
    echo "" >> "$review_file"

    # ========================================================================
    # PHASE 2: DEEP AI-ASSISTED ANALYSIS (SONNET - Capable, Thorough)
    # ========================================================================
    local ai_review_result
    ai_review_result=$(_plan_deep_review "$session_id" "$jsonl_file" 2>/dev/null || echo "")

    if [[ -n "$ai_review_result" ]]; then
        echo "## AI-Assisted Plan Analysis" >> "$review_file"
        echo "" >> "$review_file"
        echo "$ai_review_result" >> "$review_file"
        echo "" >> "$review_file"

        # Update concerns flag if AI found any
        if echo "$ai_review_result" | grep -q "CONCERNS\|⚠"; then
            has_concerns=true
        fi
    fi

    # Generate verdict
    echo "## Verdict" >> "$review_file"
    echo "" >> "$review_file"

    local verdict="PASS"
    if [[ "$has_concerns" == "true" ]]; then
        verdict="CONCERNS"
    fi

    # Check for strict mode and block_on_concerns
    local plan_strict
    plan_strict=$(config_get_or "review.plan_strict" "false")
    local block_on_concerns
    block_on_concerns=$(config_get_or "review.block_on_concerns" "false")

    case "$verdict" in
        PASS)
            echo "✓ **PASS**: Plan is well-formed and ready for bootstrap." >> "$review_file"
            log_info "✓ VERDICT: PASS - Plan ready for bootstrap"
            return 0
            ;;
        CONCERNS)
            echo "⚠ **CONCERNS**: Plan has issues but can proceed. Review recommended." >> "$review_file"

            # In strict mode, pause for review on concerns
            if [[ "$plan_strict" == "true" ]]; then
                echo "" >> "$review_file"
                echo "**STRICT MODE**: Pausing for review of plan concerns." >> "$review_file"
                log_warn "⚠ STRICT MODE: Pausing for plan review"

                # Prompt user to review
                echo ""
                echo "Plan review found concerns. Review details in: $review_file"
                read -p "Review plan concerns and press Enter to continue, or Ctrl+C to abort: "
            fi

            log_warn "⚠ VERDICT: CONCERNS - Review issues before bootstrap"
            return 1
            ;;
    esac
}

# AI-assisted deep review of plan (uses SONNET model for thorough analysis)
#
# Model Selection Strategy:
# - PHASE 1 (HAIKU): Basic format/structure checks (fast, cost-effective)
#   - JSONL validity, field presence, label validation, hierarchy validation
#   - Deterministic rules that don't require AI
# - PHASE 2 (SONNET): Deep feasibility and readiness analysis (thorough, capable)
#   - AI-powered review of task feasibility, completeness, implementation readiness
#   - Requires model sophistication to understand task clarity for AI execution
#
_plan_deep_review() {
    local session_id="$1"
    local jsonl_file="$2"

    # Read plan content and convert to readable format
    local plan_tasks=""
    local task_index=1
    while IFS= read -r line; do
        local task_id task_title task_desc
        task_id=$(echo "$line" | jq -r '.id // ""')
        task_title=$(echo "$line" | jq -r '.title // ""')
        task_desc=$(echo "$line" | jq -r '.description // ""' | head -c 100)
        if [[ -n "$task_id" && -n "$task_title" ]]; then
            plan_tasks+="$task_index. **$task_id**: $task_title"$'\n'
            if [[ -n "$task_desc" ]]; then
                plan_tasks+="   $task_desc..."$'\n'
            fi
            ((task_index++))
        fi
    done < "$jsonl_file"

    if [[ -z "$plan_tasks" ]]; then
        return 1
    fi

    # Build AI review prompt
    local prompt
    prompt=$(cat <<'EOF'
You are an expert software engineer reviewing a task plan for implementation.

Please analyze this plan for:
1. **Feasibility**: Can each task be realistically completed? Are dependencies properly ordered?
2. **Completeness**: Does the plan address all requirements? Are there any gaps or missing tasks?
3. **Implementation Readiness**: Are task descriptions clear enough for an AI agent to execute?
4. **Risk Assessment**: Are there risky tasks? Should any tasks be split further?

Plan Tasks:
---
{{PLAN_TASKS}}
---

Provide a concise, actionable review. Format your response as:

**Feasibility**: [PASS/CONCERNS] - [brief explanation]
**Completeness**: [PASS/CONCERNS] - [brief explanation]
**Implementation Readiness**: [PASS/CONCERNS] - [brief explanation]
**Risks**: [PASS/CONCERNS] - [brief explanation]

If any concerns found, include specific suggestions for improvement.
EOF
)

    # Replace placeholder
    prompt="${prompt//{{PLAN_TASKS}}/$plan_tasks}"

    # Invoke Claude with SONNET model for deep analysis
    # SONNET is used for deep analysis because it can:
    # - Understand task dependencies and ordering
    # - Assess if descriptions are clear for AI execution
    # - Identify gaps in coverage
    # - Evaluate implementation risk and complexity
    # Note: CUB_MODEL may be set globally, so we override it temporarily for this review
    local sonnet_output
    sonnet_output=$(echo "$prompt" | CUB_MODEL="sonnet" claude --print 2>/dev/null || echo "")

    if [[ -n "$sonnet_output" ]]; then
        echo "$sonnet_output"
        return 0
    fi

    return 1
}

_plan_help() {
    cat <<EOF
Usage: cub plan [OPTIONS] [SESSION_ID]

Stage 3: Task Decomposition

Break architecture into executable, AI-agent-friendly tasks.

Arguments:
  SESSION_ID         Session ID from architect (default: most recent)

Options:
  --granularity LVL  micro (default), standard, or macro
  --prefix PREFIX    Task ID prefix (default: project name)
  --review           Validate plan after generation
  -h, --help         Show this help message

Examples:
  cub plan                             # Use most recent session
  cub plan --granularity micro         # Small tasks for AI agents
  cub plan --prefix myproj             # Custom task prefix
  cub plan --review                    # With quality validation

Output:
  .cub/sessions/{session-id}/plan.jsonl     (Beads-compatible)
  .cub/sessions/{session-id}/plan.md        (Human-readable)
  .cub/sessions/{session-id}/plan_review.md (if --review)

Next Step:
  cub bootstrap {session-id}
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
    local vision_path=""
    local depth="standard"
    local mindset=""
    local granularity="micro"
    local prefix=""
    local auto="false"
    local auto_review="false"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --depth)
                depth="$2"
                shift 2
                ;;
            --depth=*)
                depth="${1#--depth=}"
                shift
                ;;
            --mindset)
                mindset="$2"
                shift 2
                ;;
            --mindset=*)
                mindset="${1#--mindset=}"
                shift
                ;;
            --granularity)
                granularity="$2"
                shift 2
                ;;
            --granularity=*)
                granularity="${1#--granularity=}"
                shift
                ;;
            --prefix)
                prefix="$2"
                shift 2
                ;;
            --prefix=*)
                prefix="${1#--prefix=}"
                shift
                ;;
            --auto)
                auto="true"
                shift
                ;;
            --auto-review)
                auto_review="true"
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
                vision_path="$1"
                shift
                ;;
        esac
    done

    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "         CUB VISION-TO-TASKS PIPELINE"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Stage 1: Triage
    log_info "[1/4] TRIAGE - Requirements Refinement"
    echo ""

    local triage_args=("--depth" "$depth")
    [[ -n "$vision_path" ]] && triage_args+=("$vision_path")

    if ! cmd_triage "${triage_args[@]}"; then
        _log_error_console "Triage failed. Pipeline stopped."
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

    local architect_args=("$session_id")
    [[ -n "$mindset" ]] && architect_args=("--mindset" "$mindset" "${architect_args[@]}")
    [[ "$auto_review" == "true" ]] && architect_args+=("--review")

    if ! cmd_architect "${architect_args[@]}"; then
        _log_error_console "Architecture failed. Pipeline stopped."
        return 1
    fi

    echo ""
    log_success "✓ Architecture complete"
    echo ""

    # Stage 3: Plan
    log_info "[3/4] PLAN - Task Decomposition"
    echo ""

    local plan_args=("--granularity" "$granularity" "$session_id")
    [[ -n "$prefix" ]] && plan_args=("--prefix" "$prefix" "${plan_args[@]}")
    [[ "$auto_review" == "true" ]] && plan_args+=("--review")

    if ! cmd_plan "${plan_args[@]}"; then
        _log_error_console "Planning failed. Pipeline stopped."
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
Usage: cub prep [OPTIONS] [VISION.md]

Run the complete Vision-to-Tasks prep pipeline.

Stages:
  1. Triage    - Refine requirements from vision document
  2. Architect - Design technical architecture (--auto-review validates here)
  3. Plan      - Decompose into executable tasks (--auto-review validates here)
  4. Bootstrap - Initialize beads and import tasks

Arguments:
  VISION.md          Path to vision/PRD document (optional)

Options:
  --depth LEVEL      Triage depth: light, standard, deep
  --mindset TYPE     prototype, mvp, production, enterprise
  --granularity LVL  Task size: micro, standard, macro
  --prefix PREFIX    Task ID prefix
  --auto             Non-interactive mode (use defaults)
  --auto-review      Enable automatic review gates between stages
  -h, --help         Show this help message

Examples:
  cub prep VISION.md              # Full prep from vision doc
  cub prep --depth deep           # Deep triage, default others
  cub prep --mindset mvp          # Pre-set mindset for architect
  cub prep --auto-review          # With quality validation gates

Output:
  .cub/sessions/{session-id}/
    ├── triage.md            # Refined requirements
    ├── architect.md         # Technical design
    ├── architect_review.md  # (with --auto-review)
    ├── plan.jsonl           # Beads-compatible tasks
    ├── plan.md              # Human-readable plan
    └── plan_review.md       # (with --auto-review)

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
# Migration Command (cmd_migrate)
# ============================================================================

cmd_migrate() {
    local source="${1:-chopshop}"

    case "$source" in
        chopshop)
            _migrate_from_chopshop
            ;;
        --help|-h|help)
            _migrate_help
            ;;
        *)
            _log_error_console "Unknown migration source: ${source}"
            _migrate_help
            return 1
            ;;
    esac
}

_migrate_from_chopshop() {
    log_info "Migrating from chopshop..."

    local chopshop_dir="${PROJECT_DIR}/.chopshop"
    local cub_dir="${PROJECT_DIR}/.cub"

    if [[ ! -d "$chopshop_dir" ]]; then
        _log_error_console "No .chopshop directory found."
        return 1
    fi

    # Create .cub if needed
    mkdir -p "${cub_dir}/sessions"

    # Migrate sessions
    if [[ -d "${chopshop_dir}/sessions" ]]; then
        log_info "Migrating sessions..."

        for session_dir in "${chopshop_dir}/sessions"/*; do
            if [[ -d "$session_dir" ]]; then
                local session_name
                session_name=$(basename "$session_dir")
                local target_dir="${cub_dir}/sessions/${session_name}"

                log_info "  Migrating: ${session_name}"

                mkdir -p "$target_dir"

                # Copy and rename files
                [[ -f "${session_dir}/triage-output.md" ]] && \
                    cp "${session_dir}/triage-output.md" "${target_dir}/triage.md"
                [[ -f "${session_dir}/architect-output.md" ]] && \
                    cp "${session_dir}/architect-output.md" "${target_dir}/architect.md"
                [[ -f "${session_dir}/plan.jsonl" ]] && \
                    cp "${session_dir}/plan.jsonl" "${target_dir}/plan.jsonl"
                [[ -f "${session_dir}/plan-output.md" ]] && \
                    cp "${session_dir}/plan-output.md" "${target_dir}/plan.md"
            fi
        done
    fi

    log_success "Migration complete!"
    log_info "Original .chopshop directory preserved."
    log_info "You can safely remove it with: rm -rf .chopshop"

    # Update .gitignore if needed
    if [[ -f "${PROJECT_DIR}/.gitignore" ]]; then
        if ! grep -q ".cub/sessions/" "${PROJECT_DIR}/.gitignore"; then
            echo ".cub/sessions/" >> "${PROJECT_DIR}/.gitignore"
            log_info "Added .cub/sessions/ to .gitignore"
        fi
    fi

    return 0
}

_migrate_help() {
    cat <<EOF
Usage: cub migrate [SOURCE]

Migrate from other planning systems to cub.

Sources:
  chopshop           Migrate from .chopshop to .cub (default)

Actions:
  - Copy session artifacts to .cub/sessions/
  - Rename files to cub conventions
  - Update .gitignore

Examples:
  cub migrate                  # Migrate from chopshop
  cub migrate chopshop         # Explicit source
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

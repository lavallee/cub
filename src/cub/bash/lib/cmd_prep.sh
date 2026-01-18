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

# Run `claude -p` reliably even without a TTY.
# Some environments hang unless a pseudo-tty is allocated.
_claude_prompt_to_file() {
    local prompt="$1"
    local out_file="$2"

    local tmp
    tmp=$(mktemp)

    if [[ -t 1 ]]; then
        claude -p "$prompt" >"$tmp"
    else
        # Allocate a pseudo-tty and capture stdout.
        # `script` writes the child output to its own stdout.
        script -q /dev/null -c "claude -p $(printf %q "$prompt")" >"$tmp"
    fi

    # Strip common ANSI escape sequences so downstream tools can parse artifacts.
    perl -pe 's/\e\[[0-9;]*[A-Za-z]//g; s/\r//g' "$tmp" >"$out_file"
    rm -f "$tmp"
}

_normalize_plan_jsonl_file() {
    local file="$1"

    # Best-effort normalizer to handle common non-beads schemas.
    # - `type` -> `issue_type`
    # - `labels` defaults to []
    # - `dependencies` defaults to []
    # - `status` defaults to "open"
    # - `priority` defaults to 2
    # - Ensure required keys exist
    if [[ ! -f "$file" ]]; then
        return 0
    fi

    local tmp
    tmp=$(mktemp)

    # If jq fails, leave as-is (validation will catch it).
    jq -c '
      . as $o
      | ($o.issue_type // $o.type) as $it
      | $o
      | del(.type)
      | .issue_type = ($it // .issue_type)
      | .status = (.status // "open")
      | .priority = (.priority // 2)
      | .labels = (.labels // [])
      | .dependencies = (.dependencies // [])
      | .id = (.id // "")
      | .title = (.title // "")
      | .description = (.description // "")
    ' "$file" >"$tmp" 2>/dev/null || { rm -f "$tmp"; return 0; }

    mv "$tmp" "$file"
}

_validate_plan_jsonl_file() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        return 1
    fi

    # Fail if any line isn't valid JSON.
    if ! jq -e -c . "$file" >/dev/null 2>&1; then
        return 1
    fi

    # Fail if required keys missing.
    if ! jq -e -c 'select((.id|type=="string") and (.title|type=="string") and (.description|type=="string") and (.issue_type|type=="string"))' "$file" >/dev/null 2>&1; then
        return 1
    fi

    return 0
}

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

# Generate a random epic ID (5 lowercase alphanumeric chars)
pipeline_random_epic_id() {
    LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | fold -w 5 | head -n 1
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

    # Generate a random epic ID (5 char alphanumeric)
    local epic_id
    epic_id=$(pipeline_random_epic_id)

    # Create session metadata
    cat > "${session_dir}/session.json" <<EOF
{
  "id": "${session_id}",
  "epic_id": "${epic_id}",
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
    local non_interactive="false"
    local vision_path=""

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
            --vision)
                vision_path="$2"
                shift 2
                ;;
            --vision=*)
                vision_path="${1#--vision=}"
                shift
                ;;
            --non-interactive|--auto)
                non_interactive="true"
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
                # Allow a positional vision path.
                if [[ -z "$vision_path" ]]; then
                    vision_path="$1"
                fi
                shift
                ;;
        esac
    done

    if [[ "$non_interactive" == "false" ]]; then
        # Check that triage skill is installed
        if [[ ! -f ".claude/commands/cub:triage.md" ]]; then
            _log_error_console "Triage skill not installed."
            _log_error_console "Run 'cub init' to install Claude Code skills."
            return 1
        fi
    else
        if [[ -z "$vision_path" || ! -f "$vision_path" ]]; then
            _log_error_console "Non-interactive triage requires a vision file path."
            _log_error_console "Usage: cub triage --non-interactive --vision VISION.md"
            return 1
        fi
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

    if [[ "$non_interactive" == "true" ]]; then
        log_info "Running non-interactive triage (best-effort)..."
        local vision
        vision=$(cat "$vision_path")

        _claude_prompt_to_file "You are Cub's prep assistant.\n\nYou will produce a TRIAGE document from a raw vision input.\n\nRules:\n- Make best-effort assumptions when details are missing.\n- If you are blocked on critical missing info, add a section '## Needs Human Input' with 1-5 specific questions.\n- Output MUST be valid Markdown. Do not wrap in code fences.\n- Output ONLY the document content (no preamble, no permission requests).\n\nOutput a triage document with these sections:\n- ## Summary\n- ## Goals\n- ## Non-Goals\n- ## Requirements\n- ## Constraints\n- ## Risks\n- ## Open Questions\n- ## Needs Human Input (only if blocked)\n\nVISION INPUT:\n---\n${vision}\n---\n" "$output_file"
    else
        # Run claude with the /triage skill
        claude "/cub:triage ${output_file}"
    fi

    # Check if output was created
    if [[ -f "$output_file" ]]; then
        if grep -q "^## Needs Human Input" "$output_file"; then
            pipeline_update_session "$session_id" "triage" "needs_human"
            echo ""
            log_warn "Triage needs human input before continuing."
            log_info "Output: ${output_file}"
            echo ""
            sed -n '/^## Needs Human Input/,$p' "$output_file"
            return 2
        fi

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
  --session ID             Resume an existing session
  --non-interactive        Run without an interactive Claude session
  --vision PATH            Vision/input markdown file (required with --non-interactive)
  -h, --help               Show this help message

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
    local non_interactive="false"

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
            --non-interactive|--auto)
                non_interactive="true"
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

    if [[ "$non_interactive" == "false" ]]; then
        # Check that architect skill is installed
        if [[ ! -f ".claude/commands/cub:architect.md" ]]; then
            _log_error_console "Architect skill not installed."
            _log_error_console "Run 'cub init' to install Claude Code skills."
            return 1
        fi
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

    if [[ "$non_interactive" == "true" ]]; then
        log_info "Running non-interactive architect (best-effort)..."
        local triage
        triage=$(cat "${session_dir}/triage.md")

        _claude_prompt_to_file "You are Cub's prep assistant.\n\nYou will produce a TECHNICAL ARCHITECTURE document based on triage output.\n\nRules:\n- Make best-effort assumptions when details are missing.\n- If blocked on a critical missing decision, add a section '## Needs Human Input' with 1-5 specific questions.\n- Output MUST be valid Markdown. Do not wrap in code fences.\n- Output ONLY the document content (no preamble, no permission requests).\n\nOutput an architecture document with these sections:\n- ## Summary\n- ## Approach\n- ## Components\n- ## Data & State\n- ## Interfaces\n- ## Risks & Tradeoffs\n- ## Testing & Verification\n- ## Needs Human Input (only if blocked)\n\nTRIAGE INPUT:\n---\n${triage}\n---\n" "$output_file"
    else
        # Run claude with the /architect skill
        claude "/cub:architect ${output_file}"
    fi

    # Check if output was created
    if [[ -f "$output_file" ]]; then
        if grep -q "^## Needs Human Input" "$output_file"; then
            pipeline_update_session "$session_id" "architect" "needs_human"
            echo ""
            log_warn "Architecture needs human input before continuing."
            log_info "Output: ${output_file}"
            echo ""
            sed -n '/^## Needs Human Input/,$p' "$output_file"
            return 2
        fi

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
  --session ID             Specify session ID
  --non-interactive        Run without an interactive Claude session
  -h, --help               Show this help message

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
    local non_interactive="false"

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
            --non-interactive|--auto)
                non_interactive="true"
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

    if [[ "$non_interactive" == "false" ]]; then
        # Check that plan skill is installed
        if [[ ! -f ".claude/commands/cub:plan.md" ]]; then
            _log_error_console "Plan skill not installed."
            _log_error_console "Run 'cub init' to install Claude Code skills."
            return 1
        fi
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

    if [[ "$non_interactive" == "true" ]]; then
        log_info "Running non-interactive plan (best-effort)..."

        local triage architect plan_prefix
        triage=$(cat "${session_dir}/triage.md")
        architect=$(cat "${session_dir}/architect.md")
        plan_prefix=$(jq -r '.epic_id // ""' "${session_dir}/session.json" 2>/dev/null)
        if [[ -z "$plan_prefix" ]]; then
            # Fallback for legacy sessions
            plan_prefix="${session_id%%-*}"
        fi

        # 1) Ask the model for a strict Markdown plan (more reliable than JSONL).
        _claude_prompt_to_file "You are Cub's prep assistant.\n\nProduce a STRICT Markdown plan. Do NOT output JSON/JSONL.\n\nFormat requirements (must follow exactly):\n- Start with '# Plan'\n- Epic sections start with: '## Epic: <id> - <title>'\n- Task sections start with: '### Task: <id> - <title>'\n- Each epic and each task MUST include these metadata lines (exact keys):\n  Priority: <integer>\n  Labels: comma,separated,labels\n  Description:\n  <freeform markdown>\n- Tasks may additionally include:\n  Blocks: comma,separated,task_ids\n\nIDs should be short (e.g. V1, V1.1) and do NOT need the project prefix.\n\nTRIAGE:\n---\n${triage}\n---\n\nARCHITECT:\n---\n${architect}\n---\n" "$md_file"

        # 2) Deterministically convert markdown -> beads JSONL.
        python3 - "$plan_prefix" "$md_file" "$jsonl_file" <<'PY'
import json
import re
import sys
from pathlib import Path

prefix = sys.argv[1]
md_path = Path(sys.argv[2])
out_path = Path(sys.argv[3])

EPIC_RE = re.compile(r"^##\s+Epic:\s*(?P<id>[^-]+?)\s*-\s*(?P<title>.+?)\s*$")
TASK_RE = re.compile(r"^###\s+Task:\s*(?P<id>[^-]+?)\s*-\s*(?P<title>.+?)\s*$")
KEY_RE = re.compile(r"^(Priority|Labels|Blocks):\s*(.*)$")

def split_csv(v: str):
    return [x.strip() for x in v.split(',') if x.strip()]

def norm_id(raw: str):
    raw = raw.strip()
    if not raw:
        return raw
    if prefix and not raw.startswith(prefix + '-'): 
        return f"{prefix}-{raw}"
    return raw

text = md_path.read_text(encoding='utf-8')
lines = text.splitlines()

out = []
cur_epic = None
cur_task = None
buf = []
in_desc = False


def flush():
    global buf
    if not buf:
        return
    body = "\n".join(buf).strip() + "\n"
    if cur_task is not None:
        cur_task['description'] = body
    elif cur_epic is not None:
        cur_epic['description'] = body
    buf.clear()

for line in lines:
    m = EPIC_RE.match(line)
    if m:
        flush()
        cur_task = None
        cur_epic = {
            'id': m.group('id').strip(),
            'title': m.group('title').strip(),
            'description': '',
            'priority': 2,
            'labels': [],
            'tasks': [],
        }
        in_desc = False
        continue

    m = TASK_RE.match(line)
    if m:
        flush()
        if cur_epic is None:
            continue
        cur_task = {
            'id': m.group('id').strip(),
            'title': m.group('title').strip(),
            'description': '',
            'priority': 2,
            'labels': [],
            'blocks': [],
        }
        cur_epic['tasks'].append(cur_task)
        in_desc = False
        continue

    m = KEY_RE.match(line)
    if m:
        flush()
        key, value = m.group(1), m.group(2).strip()
        target = cur_task if cur_task is not None else cur_epic
        if target is None:
            continue
        if key == 'Priority':
            try:
                target['priority'] = int(value)
            except ValueError:
                pass
        elif key == 'Labels':
            target['labels'] = split_csv(value)
        elif key == 'Blocks' and cur_task is not None:
            cur_task['blocks'] = split_csv(value)
        in_desc = False
        continue

    if line.strip() in ('Description:', 'Description'):
        flush()
        in_desc = True
        continue

    if in_desc:
        buf.append(line)

flush()

for epic in [cur_epic] if False else []:
    pass

# Re-parse to collect all epics encountered
# (we didn't store them while iterating to keep code minimal)

epics = []
cur_epic = None
cur_task = None
buf = []
in_desc = False

def flush2():
    global buf, cur_epic, cur_task
    if not buf:
        return
    body = "\n".join(buf).strip() + "\n"
    if cur_task is not None:
        cur_task['description'] = body
    elif cur_epic is not None:
        cur_epic['description'] = body
    buf = []

for line in lines:
    m = EPIC_RE.match(line)
    if m:
        flush2()
        cur_task = None
        cur_epic = {
            'id': m.group('id').strip(),
            'title': m.group('title').strip(),
            'description': '',
            'priority': 2,
            'labels': [],
            'tasks': [],
        }
        epics.append(cur_epic)
        in_desc = False
        continue

    m = TASK_RE.match(line)
    if m:
        flush2()
        if cur_epic is None:
            continue
        cur_task = {
            'id': m.group('id').strip(),
            'title': m.group('title').strip(),
            'description': '',
            'priority': 2,
            'labels': [],
            'blocks': [],
        }
        cur_epic['tasks'].append(cur_task)
        in_desc = False
        continue

    m = KEY_RE.match(line)
    if m:
        flush2()
        key, value = m.group(1), m.group(2).strip()
        target = cur_task if cur_task is not None else cur_epic
        if target is None:
            continue
        if key == 'Priority':
            try:
                target['priority'] = int(value)
            except ValueError:
                pass
        elif key == 'Labels':
            target['labels'] = split_csv(value)
        elif key == 'Blocks' and cur_task is not None:
            cur_task['blocks'] = split_csv(value)
        in_desc = False
        continue

    if line.strip() in ('Description:', 'Description'):
        flush2()
        in_desc = True
        continue

    if in_desc:
        buf.append(line)

flush2()

json_lines = []
for epic in epics:
    epic_id = norm_id(epic['id'])
    json_lines.append(json.dumps({
        'id': epic_id,
        'title': epic['title'],
        'description': epic.get('description',''),
        'status': 'open',
        'priority': epic.get('priority',2),
        'issue_type': 'epic',
        'labels': epic.get('labels',[]),
        'dependencies': [],
    }, ensure_ascii=False))
    for task in epic.get('tasks', []):
        task_id = norm_id(task['id'])
        deps = [{'depends_on_id': epic_id, 'type': 'parent-child'}]
        for b in task.get('blocks', []):
            deps.append({'depends_on_id': norm_id(b), 'type': 'blocks'})
        json_lines.append(json.dumps({
            'id': task_id,
            'title': task['title'],
            'description': task.get('description',''),
            'status': 'open',
            'priority': task.get('priority',2),
            'issue_type': 'task',
            'labels': task.get('labels',[]),
            'dependencies': deps,
        }, ensure_ascii=False))

out_path.write_text("\n".join(json_lines) + ("\n" if json_lines else ""), encoding='utf-8')
PY

        # 3) Validate the generated JSONL.
        if ! _validate_plan_jsonl_file "$jsonl_file"; then
            echo "{\"id\":\"${plan_prefix}-NEEDS_HUMAN\",\"title\":\"NEEDS_HUMAN_INPUT\",\"description\":\"Non-interactive plan conversion failed: generated plan.jsonl is invalid. Please re-run interactively (cub plan) or fix the markdown plan at ${md_file}.\",\"status\":\"open\",\"priority\":1,\"issue_type\":\"note\",\"labels\":[\"prep:error\"],\"dependencies\":[]}" >"$jsonl_file"
        fi
    else
        # Run claude with the /plan skill (outputs plan.md)
        claude "/cub:plan ${session_dir}"

        # Convert the markdown plan to beads JSONL
        if [[ -f "$md_file" ]]; then
            log_info "Converting markdown plan to beads JSONL..."
            local plan_prefix
            plan_prefix=$(jq -r '.epic_id // ""' "${session_dir}/session.json" 2>/dev/null)
            if [[ -z "$plan_prefix" ]]; then
                # Fallback for legacy sessions
                plan_prefix="${session_id%%-*}"
            fi
            python3 - "$plan_prefix" "$md_file" "$jsonl_file" <<'PY'
import json
import re
import sys
from pathlib import Path

prefix = sys.argv[1]
md_path = Path(sys.argv[2])
out_path = Path(sys.argv[3])

EPIC_RE = re.compile(r"^##\s+Epic:\s*(?P<id>[^-]+?)\s*-\s*(?P<title>.+?)\s*$")
TASK_RE = re.compile(r"^###\s+Task:\s*(?P<id>[^-]+?)\s*-\s*(?P<title>.+?)\s*$")
KEY_RE = re.compile(r"^(Priority|Labels|Blocks):\s*(.*)$")

def split_csv(v: str):
    return [x.strip() for x in v.split(',') if x.strip()]

def norm_id(raw: str):
    raw = raw.strip()
    if not raw:
        return raw
    if prefix and not raw.startswith(prefix + '-'):
        return f"{prefix}-{raw}"
    return raw

text = md_path.read_text(encoding='utf-8')
lines = text.splitlines()

epics = []
cur_epic = None
cur_task = None
buf = []
in_desc = False

def flush2():
    global buf, cur_epic, cur_task
    if not buf:
        return
    body = "\n".join(buf).strip() + "\n"
    if cur_task is not None:
        cur_task['description'] = body
    elif cur_epic is not None:
        cur_epic['description'] = body
    buf = []

for line in lines:
    m = EPIC_RE.match(line)
    if m:
        flush2()
        cur_task = None
        cur_epic = {
            'id': m.group('id').strip(),
            'title': m.group('title').strip(),
            'description': '',
            'priority': 2,
            'labels': [],
            'tasks': [],
        }
        epics.append(cur_epic)
        in_desc = False
        continue

    m = TASK_RE.match(line)
    if m:
        flush2()
        if cur_epic is None:
            continue
        cur_task = {
            'id': m.group('id').strip(),
            'title': m.group('title').strip(),
            'description': '',
            'priority': 2,
            'labels': [],
            'blocks': [],
        }
        cur_epic['tasks'].append(cur_task)
        in_desc = False
        continue

    m = KEY_RE.match(line)
    if m:
        flush2()
        key, value = m.group(1), m.group(2).strip()
        target = cur_task if cur_task is not None else cur_epic
        if target is None:
            continue
        if key == 'Priority':
            try:
                target['priority'] = int(value)
            except ValueError:
                pass
        elif key == 'Labels':
            target['labels'] = split_csv(value)
        elif key == 'Blocks' and cur_task is not None:
            cur_task['blocks'] = split_csv(value)
        in_desc = False
        continue

    if line.strip() in ('Description:', 'Description'):
        flush2()
        in_desc = True
        continue

    if in_desc:
        buf.append(line)

flush2()

json_lines = []
for epic in epics:
    epic_id = norm_id(epic['id'])
    json_lines.append(json.dumps({
        'id': epic_id,
        'title': epic['title'],
        'description': epic.get('description',''),
        'status': 'open',
        'priority': epic.get('priority',2),
        'issue_type': 'epic',
        'labels': epic.get('labels',[]),
        'dependencies': [],
    }, ensure_ascii=False))
    for task in epic.get('tasks', []):
        task_id = norm_id(task['id'])
        deps = [{'depends_on_id': epic_id, 'type': 'parent-child'}]
        for b in task.get('blocks', []):
            deps.append({'depends_on_id': norm_id(b), 'type': 'blocks'})
        json_lines.append(json.dumps({
            'id': task_id,
            'title': task['title'],
            'description': task.get('description',''),
            'status': 'open',
            'priority': task.get('priority',2),
            'issue_type': 'task',
            'labels': task.get('labels',[]),
            'dependencies': deps,
        }, ensure_ascii=False))

out_path.write_text("\n".join(json_lines) + ("\n" if json_lines else ""), encoding='utf-8')
PY
        fi
    fi

    # Check if output was created
    if [[ -f "$jsonl_file" ]]; then
        if grep -q '"title"[[:space:]]*:[[:space:]]*"NEEDS_HUMAN_INPUT"' "$jsonl_file"; then
            pipeline_update_session "$session_id" "plan" "needs_human"
            echo ""
            log_warn "Plan needs human input before continuing."
            log_info "Output: ${jsonl_file}"
            echo ""
            cat "$jsonl_file"
            return 2
        fi

        pipeline_update_session "$session_id" "plan" "complete"
        echo ""

        # Count tasks
        local epic_count task_count
        epic_count=$(grep -c '"issue_type":"epic"' "$jsonl_file" 2>/dev/null || echo "0")
        task_count=$(grep -c '"issue_type":"task"' "$jsonl_file" 2>/dev/null || echo "0")

        log_success "Plan generated: ${epic_count} epics, ${task_count} tasks"
        log_info "JSONL: ${jsonl_file}"
        [[ -f "$md_file" ]] && log_info "Summary: ${md_file}"
        log_info "Next step: cub bootstrap ${session_id}"
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
  --session ID             Specify session ID
  --non-interactive        Run without an interactive Claude session
  -h, --help               Show this help message

Examples:
  cub plan                             # Use most recent session
  cub plan --session myproj-...        # Specific session

Output:
  .cub/sessions/{session-id}/plan.jsonl     (Beads-compatible)
  .cub/sessions/{session-id}/plan.md        (Human-readable)

Next Step:
  cub bootstrap {session-id}
EOF
}

# ============================================================================
# Bootstrap Stage (cmd_bootstrap)
# ============================================================================

# Wire up dependencies from plan.jsonl after import
# This is a workaround for beads not importing dependencies
# See: https://github.com/steveyegge/beads/issues/XXX
_wire_dependencies_from_plan() {
    local plan_file="$1"
    local dep_count=0

    if [[ ! -f "$plan_file" ]]; then
        log_warn "Plan file not found: ${plan_file}"
        return 0
    fi

    # Process each line with dependencies
    while IFS= read -r line; do
        local issue_id
        issue_id=$(echo "$line" | jq -r '.id // empty')

        if [[ -z "$issue_id" ]]; then
            continue
        fi

        # Extract dependencies array
        local deps
        deps=$(echo "$line" | jq -c '.dependencies // []')

        if [[ "$deps" == "[]" || "$deps" == "null" ]]; then
            continue
        fi

        # Process each dependency
        echo "$deps" | jq -c '.[]' | while IFS= read -r dep; do
            local depends_on_id dep_type
            depends_on_id=$(echo "$dep" | jq -r '.depends_on_id // empty')
            dep_type=$(echo "$dep" | jq -r '.type // "blocks"')

            if [[ -n "$depends_on_id" ]]; then
                # Add the dependency silently
                if bd dep add "$issue_id" "$depends_on_id" --type "$dep_type" 2>/dev/null; then
                    ((dep_count++)) || true
                fi
            fi
        done
    done < "$plan_file"

    log_debug "  Added ${dep_count} dependencies"
}

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

    # Wire up dependencies (bd import doesn't preserve them - beads bug)
    log_info "Wiring up dependencies..."
    _wire_dependencies_from_plan "$plan_file"

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
    local session_id=""
    local non_interactive="false"
    local vision_path=""
    local continue_last="false"

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
            --continue)
                continue_last="true"
                shift
                ;;
            --vision)
                vision_path="$2"
                shift 2
                ;;
            --vision=*)
                vision_path="${1#--vision=}"
                shift
                ;;
            --non-interactive|--auto)
                non_interactive="true"
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
                # Allow a positional vision path.
                if [[ -z "$vision_path" ]]; then
                    vision_path="$1"
                fi
                shift
                ;;
        esac
    done

    echo ""
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "         CUB VISION-TO-TASKS PREP"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Determine which stage to start
    local start_stage=""
    local session_dir=""

    if [[ -n "$session_id" ]]; then
        # Explicit session provided
        if ! pipeline_session_exists "$session_id"; then
            _log_error_console "Session not found: $session_id"
            return 1
        fi
        session_dir=$(pipeline_session_dir "$session_id")
        log_info "Resuming session: ${session_id}"
    elif [[ "$continue_last" == "true" ]]; then
        # Continue most recent session
        session_id=$(pipeline_most_recent_session)
        if [[ -n "$session_id" ]]; then
            session_dir=$(pipeline_session_dir "$session_id")
            log_info "Continuing most recent session: ${session_id}"
        else
            _log_error_console "No existing sessions found. Run without --continue to create a new session."
            return 1
        fi
    else
        # Default: create a new session
        log_info "Starting new session..."
    fi

    # Determine next step based on existing artifacts
    if [[ -n "$session_dir" ]]; then
        if [[ -f "${session_dir}/plan.jsonl" ]]; then
            start_stage="bootstrap"
        elif [[ -f "${session_dir}/architect.md" ]]; then
            start_stage="plan"
        elif [[ -f "${session_dir}/triage.md" ]]; then
            start_stage="architect"
        else
            start_stage="triage"
        fi
    else
        start_stage="triage"
    fi

    # Launch the appropriate stage
    case "$start_stage" in
        triage)
            log_info "Starting Stage 1: Triage"
            echo ""
            if [[ "$non_interactive" == "true" ]]; then
                cmd_triage --non-interactive --vision "$vision_path"
            else
                cmd_triage
            fi
            ;;
        architect)
            log_info "Starting Stage 2: Architect"
            echo ""
            if [[ "$non_interactive" == "true" ]]; then
                cmd_architect --non-interactive --session "$session_id"
            else
                cmd_architect --session "$session_id"
            fi
            ;;
        plan)
            log_info "Starting Stage 3: Plan"
            echo ""
            if [[ "$non_interactive" == "true" ]]; then
                cmd_plan --non-interactive --session "$session_id"
            else
                cmd_plan --session "$session_id"
            fi
            ;;
        bootstrap)
            log_info "Starting Stage 4: Bootstrap"
            echo ""
            cmd_bootstrap "$session_id"
            ;;
    esac

    # Get session ID after stage completes (may have been created during triage)
    session_id=$(pipeline_most_recent_session)
    session_dir=$(pipeline_session_dir "$session_id")

    # Report prep status
    echo ""
    _prep_report_status "$session_id"

    return 0
}

# Report the current prep status and remaining steps
_prep_report_status() {
    local session_id="$1"
    local session_dir
    session_dir=$(pipeline_session_dir "$session_id")

    local has_triage=false
    local has_architect=false
    local has_plan=false
    local has_bootstrap=false

    [[ -f "${session_dir}/triage.md" ]] && has_triage=true
    [[ -f "${session_dir}/architect.md" ]] && has_architect=true
    [[ -f "${session_dir}/plan.jsonl" ]] && has_plan=true

    # Check bootstrap status from session.json
    if [[ -f "${session_dir}/session.json" ]]; then
        local bs_status
        bs_status=$(jq -r '.stages.bootstrap // ""' "${session_dir}/session.json" 2>/dev/null)
        [[ "$bs_status" == "complete" ]] && has_bootstrap=true
    fi

    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "         PREP STATUS"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    log_info "Session: ${session_id}"
    echo ""

    # Show status of each stage
    if [[ "$has_triage" == "true" ]]; then
        echo "  [✓] Triage    - triage.md"
    else
        echo "  [ ] Triage    - pending"
    fi

    if [[ "$has_architect" == "true" ]]; then
        echo "  [✓] Architect - architect.md"
    else
        echo "  [ ] Architect - pending"
    fi

    if [[ "$has_plan" == "true" ]]; then
        echo "  [✓] Plan      - plan.jsonl"
    else
        echo "  [ ] Plan      - pending"
    fi

    if [[ "$has_bootstrap" == "true" ]]; then
        echo "  [✓] Bootstrap - complete"
    else
        echo "  [ ] Bootstrap - pending"
    fi

    echo ""

    # Determine next step
    if [[ "$has_bootstrap" == "true" ]]; then
        log_success "Prep complete!"
        log_info "Ready to start: cub run"
    elif [[ "$has_plan" == "true" ]]; then
        log_info "Next step: cub bootstrap ${session_id}"
    elif [[ "$has_architect" == "true" ]]; then
        log_info "Next step: cub plan --session ${session_id}"
    elif [[ "$has_triage" == "true" ]]; then
        log_info "Next step: cub architect --session ${session_id}"
    else
        log_info "Next step: cub triage --session ${session_id}"
    fi

    log_info "Or run: cub prep --session ${session_id}"
    echo ""
}

_prep_help() {
    cat <<EOF
Usage: cub prep [OPTIONS]

Run the Vision-to-Tasks prep workflow one stage at a time.

Each invocation launches an interactive Claude session for the next
incomplete stage. After you exit Claude, prep shows your progress
and the next step.

Stages:
  1. Triage    - Interactive requirements refinement (/cub:triage)
  2. Architect - Interactive technical design (/cub:architect)
  3. Plan      - Interactive task decomposition (/cub:plan)
  4. Bootstrap - Initialize beads and import tasks (shell)

Options:
  --session ID             Resume a specific session
  --continue               Resume the most recent session (default: create new)
  --non-interactive        Run stages using `claude -p` (best-effort)
  --vision PATH            Vision/input markdown file (required for non-interactive triage)
  -h, --help               Show this help message

Examples:
  cub prep                          # Start or continue prep
  cub prep --session myproj-...     # Resume specific session

Workflow:
  1. Run 'cub prep' - starts triage session
  2. Complete triage interview, exit Claude
  3. Run 'cub prep' again - continues to architect
  4. Repeat until all stages complete

Output:
  .cub/sessions/{session-id}/
    ├── triage.md            # Refined requirements
    ├── architect.md         # Technical design
    ├── plan.jsonl           # Beads-compatible tasks
    └── plan.md              # Human-readable plan

Individual Commands:
  cub triage                 # Just run triage
  cub architect              # Just run architect
  cub plan                   # Just run plan
  cub bootstrap              # Just run bootstrap
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

    for session in $sessions; do
        local triage_status="[ ]"
        local architect_status="[ ]"
        local plan_status="[ ]"
        local bootstrap_status="[ ]"

        pipeline_has_triage "$session" && triage_status="[x]"
        pipeline_has_architect "$session" && architect_status="[x]"
        pipeline_has_plan "$session" && plan_status="[x]"

        local session_dir
        session_dir=$(pipeline_session_dir "$session")
        local session_file="${session_dir}/session.json"
        if [[ -f "$session_file" ]]; then
            local bs_status
            bs_status=$(jq -r '.stages.bootstrap // "-"' "$session_file" 2>/dev/null)
            [[ "$bs_status" == "complete" ]] && bootstrap_status="[x]"
        fi

        echo "$session"
        echo "  Triage: $triage_status  Architect: $architect_status  Plan: $plan_status  Bootstrap: $bootstrap_status"
        echo ""
    done
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

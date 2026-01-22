#!/usr/bin/env bash
#
# cmd_plan.sh - Vision-to-Tasks Planning Pipeline
#
# Unified planning pipeline from vision document to executable tasks:
#   cub plan run VISION.md       - Run full planning pipeline
#   cub plan orient [VISION.md]  - Stage 1: Requirements refinement
#   cub plan architect [session] - Stage 2: Technical design
#   cub plan itemize [session]   - Stage 3: Task decomposition
#   cub stage [session]          - Stage 4: Initialize beads
#   cub plan list                - List/manage sessions
#
# Plans are stored in plans/{plan-slug}/
# Each plan produces artifacts: orientation.md, architecture.md, itemized-plan.jsonl, itemized-plan.md
#

# Plans directory root
PLANS_DIR="${PROJECT_DIR}/plans"

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
# Plan Management Functions
# ============================================================================

# Generate a new plan slug: {spec-stem} or {project}-{timestamp}
# Args: [spec_path]
plan_new_slug() {
    local spec_path="${1:-}"

    if [[ -n "$spec_path" && -f "$spec_path" ]]; then
        # Use spec filename stem as slug
        local stem
        stem=$(basename "$spec_path" .md)
        echo "$stem"
        return 0
    fi

    # Fallback: project-timestamp
    local project_name
    project_name=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]//g')
    project_name="${project_name:0:12}"

    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)

    echo "${project_name}-${timestamp}"
}

# Generate a random epic ID (5 lowercase alphanumeric chars)
plan_random_epic_id() {
    local chars="abcdefghijklmnopqrstuvwxyz0123456789"
    local result=""
    for i in 1 2 3 4 5; do
        result+="${chars:RANDOM%36:1}"
    done
    printf '%s' "$result"
}

# Get the most recent plan slug
# Returns: plan slug or empty if none
plan_most_recent() {
    if [[ -d "$PLANS_DIR" ]]; then
        ls -t "$PLANS_DIR" 2>/dev/null | head -1
    fi
}

# Check if a plan exists
# Args: plan_slug
plan_exists() {
    local plan_slug="$1"
    [[ -d "${PLANS_DIR}/${plan_slug}" ]]
}

# Get plan directory path
# Args: plan_slug
plan_dir() {
    local plan_slug="$1"
    echo "${PLANS_DIR}/${plan_slug}"
}

# Create a new plan directory
# Args: plan_slug [spec_path]
plan_create() {
    local plan_slug="$1"
    local spec_path="${2:-}"
    local plan_dir="${PLANS_DIR}/${plan_slug}"

    mkdir -p "$plan_dir"

    # Generate a random epic ID (5 char alphanumeric)
    local epic_id
    epic_id=$(plan_random_epic_id)

    # Create plan metadata with optional spec_path
    local spec_json="null"
    if [[ -n "$spec_path" ]]; then
        # Convert to absolute path if relative
        if [[ ! "$spec_path" = /* ]]; then
            spec_path="${PROJECT_DIR}/${spec_path}"
        fi
        spec_json="\"${spec_path}\""
    fi

    # Create plan metadata
    cat > "${plan_dir}/plan.json" <<EOF
{
  "slug": "${plan_slug}",
  "epic_id": "${epic_id}",
  "created": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "status": "pending",
  "spec_path": ${spec_json},
  "stages": {
    "orient": null,
    "architect": null,
    "itemize": null,
    "stage": null
  }
}
EOF

    echo "$plan_dir"
}

# Update plan status
# Args: plan_slug stage status
plan_update() {
    local plan_slug="$1"
    local stage="$2"
    local status="$3"
    local plan_dir="${PLANS_DIR}/${plan_slug}"
    local plan_file="${plan_dir}/plan.json"

    if [[ -f "$plan_file" ]]; then
        local tmp_file="${plan_file}.tmp"
        jq --arg stage "$stage" --arg status "$status" \
            '.stages[$stage] = $status | .updated = (now | strftime("%Y-%m-%dT%H:%M:%SZ"))' \
            "$plan_file" > "$tmp_file" && mv "$tmp_file" "$plan_file"
    fi
}

# List all plans
plan_list_all() {
    if [[ ! -d "$PLANS_DIR" ]]; then
        return 0
    fi

    local plans
    plans=$(ls -t "$PLANS_DIR" 2>/dev/null)

    if [[ -z "$plans" ]]; then
        return 0
    fi

    echo "$plans"
}

# Get plan info
# Args: plan_slug
plan_info() {
    local plan_slug="$1"
    local plan_dir="${PLANS_DIR}/${plan_slug}"
    local plan_file="${plan_dir}/plan.json"

    if [[ -f "$plan_file" ]]; then
        cat "$plan_file"
    else
        echo "{}"
    fi
}

# Get spec path from plan metadata
# Args: plan_slug
# Returns: spec path or empty if not set
plan_get_spec_path() {
    local plan_slug="$1"
    local plan_dir="${PLANS_DIR}/${plan_slug}"
    local plan_file="${plan_dir}/plan.json"

    if [[ -f "$plan_file" ]]; then
        jq -r '.spec_path // empty' "$plan_file" 2>/dev/null
    fi
}

# ============================================================================
# Plan Stage Checkers
# ============================================================================

# Check if orient is complete for plan
plan_has_orient() {
    local plan_slug="$1"
    [[ -f "${PLANS_DIR}/${plan_slug}/orientation.md" ]]
}

# Check if architect is complete for plan
plan_has_architect() {
    local plan_slug="$1"
    [[ -f "${PLANS_DIR}/${plan_slug}/architecture.md" ]]
}

# Check if itemize is complete for plan
plan_has_itemize() {
    local plan_slug="$1"
    [[ -f "${PLANS_DIR}/${plan_slug}/itemized-plan.jsonl" ]]
}

# ============================================================================
# Spec Document Finder
# ============================================================================

# Find spec document in priority order
# Args: [explicit_path]
# Returns: path to spec document or empty
plan_find_spec() {
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

    # No spec document found
    return 1
}

# ============================================================================
# Orient Stage (cmd_orient)
# ============================================================================

cmd_orient() {
    local plan_slug=""
    local resume_plan=""
    local non_interactive="false"
    local spec_path=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --plan)
                resume_plan="$2"
                shift 2
                ;;
            --plan=*)
                resume_plan="${1#--plan=}"
                shift
                ;;
            --spec)
                spec_path="$2"
                shift 2
                ;;
            --spec=*)
                spec_path="${1#--spec=}"
                shift
                ;;
            --non-interactive|--auto)
                non_interactive="true"
                shift
                ;;
            --help|-h)
                _orient_help
                return 0
                ;;
            -*)
                _log_error_console "Unknown option: $1"
                _orient_help
                return 1
                ;;
            *)
                # Allow a positional spec path.
                if [[ -z "$spec_path" ]]; then
                    spec_path="$1"
                fi
                shift
                ;;
        esac
    done

    if [[ "$non_interactive" == "false" ]]; then
        # Check that orient skill is installed
        if [[ ! -f ".claude/commands/cub:orient.md" ]]; then
            _log_error_console "Orient skill not installed."
            _log_error_console "Run 'cub update' to install Claude Code skills."
            return 1
        fi
    else
        if [[ -z "$spec_path" || ! -f "$spec_path" ]]; then
            _log_error_console "Non-interactive orient requires a spec file path."
            _log_error_console "Usage: cub plan orient --non-interactive --spec SPEC.md"
            return 1
        fi
    fi

    # Resume existing plan or create new
    if [[ -n "$resume_plan" ]]; then
        if ! plan_exists "$resume_plan"; then
            _log_error_console "Plan not found: $resume_plan"
            return 1
        fi
        plan_slug="$resume_plan"
        log_info "Resuming plan: ${plan_slug}"

        # Get spec path from plan if not explicitly provided
        if [[ -z "$spec_path" ]]; then
            spec_path=$(plan_get_spec_path "$plan_slug")
        fi
    else
        plan_slug=$(plan_new_slug "$spec_path")
        plan_create "$plan_slug" "$spec_path"
        log_info "Starting new plan: ${plan_slug}"
    fi

    local plan_dir
    plan_dir=$(plan_dir "$plan_slug")
    local output_file="${plan_dir}/orientation.md"

    # Invoke the orient skill with output path
    log_info "Starting orient interview..."
    log_info "Plan: ${plan_slug}"
    echo ""

    if [[ "$non_interactive" == "true" ]]; then
        log_info "Running non-interactive orient (best-effort)..."
        local spec
        spec=$(cat "$spec_path")

        _claude_prompt_to_file "You are Cub's planning assistant.\n\nYou will produce an ORIENTATION document from a raw spec/vision input.\n\nRules:\n- Make best-effort assumptions when details are missing.\n- If you are blocked on critical missing info, add a section '## Needs Human Input' with 1-5 specific questions.\n- Output MUST be valid Markdown. Do not wrap in code fences.\n- Output ONLY the document content (no preamble, no permission requests).\n\nOutput an orientation document with these sections:\n- ## Summary\n- ## Goals\n- ## Non-Goals\n- ## Requirements\n- ## Constraints\n- ## Risks\n- ## Open Questions\n- ## Needs Human Input (only if blocked)\n\nSPEC INPUT:\n---\n${spec}\n---\n" "$output_file"
    else
        # Run claude with the /orient skill
        claude --dangerously-skip-permissions "/cub:orient ${output_file}"
    fi

    # Check if output was created
    if [[ -f "$output_file" ]]; then
        if grep -q "^## Needs Human Input" "$output_file"; then
            plan_update "$plan_slug" "orient" "needs_human"
            echo ""
            log_warn "Orient needs human input before continuing."
            log_info "Output: ${output_file}"
            echo ""
            sed -n '/^## Needs Human Input/,$p' "$output_file"
            return 2
        fi

        plan_update "$plan_slug" "orient" "complete"
        echo ""
        log_success "Orient complete!"
        log_info "Output: ${output_file}"
        log_info "Next step: cub plan architect ${plan_slug}"
    else
        echo ""
        log_warn "Orient session ended but output file not created."
        log_info "Plan: ${plan_slug}"
        log_info "Expected output: ${output_file}"
        log_info "Resume with: cub plan orient --plan ${plan_slug}"
    fi

    return 0
}

_orient_help() {
    cat <<EOF
Usage: cub plan orient [OPTIONS] [SPEC_FILE]

Stage 1: Requirements Refinement

Launches an interactive Claude session to conduct a product orientation interview,
clarify requirements, identify gaps, and produce a refined requirements document.

Arguments:
  SPEC_FILE              Spec/vision document to use as input
                         (e.g., specs/researching/new-idea.md)

Options:
  --plan SLUG            Resume an existing plan
  --non-interactive      Run without an interactive Claude session
  --spec PATH            Spec/input file path (alternative to positional arg)
  -h, --help             Show this help message

Examples:
  cub plan orient                           # Start new orient session
  cub plan orient specs/new-feature.md      # Start with specific spec
  cub plan orient --plan my-feature         # Resume existing plan
  cub plan orient --spec specs/ideas.md     # Explicit spec file

Output:
  plans/{plan-slug}/orientation.md

Next Step:
  cub plan architect {plan-slug}
EOF
}

# ============================================================================
# Architect Stage (cmd_architect)
# ============================================================================

cmd_architect() {
    local plan_slug=""
    local non_interactive="false"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --plan)
                plan_slug="$2"
                shift 2
                ;;
            --plan=*)
                plan_slug="${1#--plan=}"
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
                plan_slug="$1"
                shift
                ;;
        esac
    done

    if [[ "$non_interactive" == "false" ]]; then
        # Check that architect skill is installed
        if [[ ! -f ".claude/commands/cub:architect.md" ]]; then
            _log_error_console "Architect skill not installed."
            _log_error_console "Run 'cub update' to install Claude Code skills."
            return 1
        fi
    fi

    # Get plan slug
    if [[ -z "$plan_slug" ]]; then
        plan_slug=$(plan_most_recent)
        if [[ -z "$plan_slug" ]]; then
            _log_error_console "No plan specified and no recent plan found."
            _log_error_console "Run 'cub plan orient' first to create a plan."
            return 1
        fi
        log_info "Using most recent plan: ${plan_slug}"
    fi

    # Verify plan exists
    if ! plan_exists "$plan_slug"; then
        _log_error_console "Plan not found: ${plan_slug}"
        return 1
    fi

    # Verify orient is complete
    if ! plan_has_orient "$plan_slug"; then
        _log_error_console "Orient not complete for plan: ${plan_slug}"
        _log_error_console "Run 'cub plan orient --plan ${plan_slug}' first."
        return 1
    fi

    local plan_dir
    plan_dir=$(plan_dir "$plan_slug")
    local output_file="${plan_dir}/architecture.md"

    # Invoke the architect skill with output path
    log_info "Starting architecture design session..."
    log_info "Plan: ${plan_slug}"
    echo ""

    if [[ "$non_interactive" == "true" ]]; then
        log_info "Running non-interactive architect (best-effort)..."
        local orientation
        orientation=$(cat "${plan_dir}/orientation.md")

        _claude_prompt_to_file "You are Cub's planning assistant.\n\nYou will produce a TECHNICAL ARCHITECTURE document based on orientation output.\n\nRules:\n- Make best-effort assumptions when details are missing.\n- If blocked on a critical missing decision, add a section '## Needs Human Input' with 1-5 specific questions.\n- Output MUST be valid Markdown. Do not wrap in code fences.\n- Output ONLY the document content (no preamble, no permission requests).\n\nOutput an architecture document with these sections:\n- ## Summary\n- ## Approach\n- ## Components\n- ## Data & State\n- ## Interfaces\n- ## Risks & Tradeoffs\n- ## Testing & Verification\n- ## Needs Human Input (only if blocked)\n\nORIENTATION INPUT:\n---\n${orientation}\n---\n" "$output_file"
    else
        # Run claude with the /architect skill
        claude --dangerously-skip-permissions "/cub:architect ${output_file}"
    fi

    # Check if output was created
    if [[ -f "$output_file" ]]; then
        if grep -q "^## Needs Human Input" "$output_file"; then
            plan_update "$plan_slug" "architect" "needs_human"
            echo ""
            log_warn "Architecture needs human input before continuing."
            log_info "Output: ${output_file}"
            echo ""
            sed -n '/^## Needs Human Input/,$p' "$output_file"
            return 2
        fi

        plan_update "$plan_slug" "architect" "complete"
        echo ""
        log_success "Architecture design complete!"
        log_info "Output: ${output_file}"
        log_info "Next step: cub plan itemize ${plan_slug}"
    else
        echo ""
        log_warn "Architect session ended but output file not created."
        log_info "Plan: ${plan_slug}"
        log_info "Expected output: ${output_file}"
        log_info "Resume with: cub plan architect ${plan_slug}"
    fi

    return 0
}

_architect_help() {
    cat <<EOF
Usage: cub plan architect [OPTIONS] [PLAN_SLUG]

Stage 2: Technical Design

Launches an interactive Claude session to design a technical architecture
based on the orientation output.

Arguments:
  PLAN_SLUG         Plan slug from orient (default: most recent)

Options:
  --plan SLUG            Specify plan slug
  --non-interactive      Run without an interactive Claude session
  -h, --help             Show this help message

Examples:
  cub plan architect                    # Use most recent plan
  cub plan architect my-feature         # Specific plan
  cub plan architect --plan my-feature  # Explicit plan flag

Output:
  plans/{plan-slug}/architecture.md

Next Step:
  cub plan itemize {plan-slug}
EOF
}

# ============================================================================
# Itemize Stage (cmd_itemize)
# ============================================================================

cmd_itemize() {
    local plan_slug=""
    local non_interactive="false"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --plan)
                plan_slug="$2"
                shift 2
                ;;
            --plan=*)
                plan_slug="${1#--plan=}"
                shift
                ;;
            --non-interactive|--auto)
                non_interactive="true"
                shift
                ;;
            --help|-h)
                _itemize_help
                return 0
                ;;
            -*)
                _log_error_console "Unknown option: $1"
                _itemize_help
                return 1
                ;;
            *)
                plan_slug="$1"
                shift
                ;;
        esac
    done

    if [[ "$non_interactive" == "false" ]]; then
        # Check that itemize skill is installed
        if [[ ! -f ".claude/commands/cub:itemize.md" ]]; then
            _log_error_console "Itemize skill not installed."
            _log_error_console "Run 'cub update' to install Claude Code skills."
            return 1
        fi
    fi

    # Get plan slug
    if [[ -z "$plan_slug" ]]; then
        plan_slug=$(plan_most_recent)
        if [[ -z "$plan_slug" ]]; then
            _log_error_console "No plan specified and no recent plan found."
            return 1
        fi
        log_info "Using most recent plan: ${plan_slug}"
    fi

    # Verify plan exists
    if ! plan_exists "$plan_slug"; then
        _log_error_console "Plan not found: ${plan_slug}"
        return 1
    fi

    # Verify architect is complete
    if ! plan_has_architect "$plan_slug"; then
        _log_error_console "Architecture not complete for plan: ${plan_slug}"
        _log_error_console "Run 'cub plan architect ${plan_slug}' first."
        return 1
    fi

    local plan_dir
    plan_dir=$(plan_dir "$plan_slug")
    local jsonl_file="${plan_dir}/itemized-plan.jsonl"
    local md_file="${plan_dir}/itemized-plan.md"

    # Invoke the itemize skill with plan dir
    log_info "Starting plan generation session..."
    log_info "Plan: ${plan_slug}"
    echo ""

    if [[ "$non_interactive" == "true" ]]; then
        log_info "Running non-interactive itemize (best-effort)..."

        local orientation architecture plan_prefix
        orientation=$(cat "${plan_dir}/orientation.md")
        architecture=$(cat "${plan_dir}/architecture.md")
        plan_prefix=$(jq -r '.epic_id // ""' "${plan_dir}/plan.json" 2>/dev/null)
        if [[ -z "$plan_prefix" ]]; then
            plan_prefix="${plan_slug%%-*}"
        fi

        # 1) Ask the model for a strict Markdown plan (more reliable than JSONL).
        _claude_prompt_to_file "You are Cub's planning assistant.\n\nProduce a STRICT Markdown plan. Do NOT output JSON/JSONL.\n\nFormat requirements (must follow exactly):\n- Start with '# Plan'\n- Epic sections start with: '## Epic: <id> - <title>'\n- Task sections start with: '### Task: <id> - <title>'\n- Each epic and each task MUST include these metadata lines (exact keys):\n  Priority: <integer>\n  Labels: comma,separated,labels\n  Description:\n  <freeform markdown>\n- Tasks may additionally include:\n  Blocks: comma,separated,task_ids\n\nIDs should be short (e.g. V1, V1.1) and do NOT need the project prefix.\n\nORIENTATION:\n---\n${orientation}\n---\n\nARCHITECTURE:\n---\n${architecture}\n---\n" "$md_file"

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
            echo "{\"id\":\"${plan_prefix}-NEEDS_HUMAN\",\"title\":\"NEEDS_HUMAN_INPUT\",\"description\":\"Non-interactive plan conversion failed: generated itemized-plan.jsonl is invalid. Please re-run interactively (cub plan itemize) or fix the markdown plan at ${md_file}.\",\"status\":\"open\",\"priority\":1,\"issue_type\":\"note\",\"labels\":[\"plan:error\"],\"dependencies\":[]}" >"$jsonl_file"
        fi
    else
        # Run claude with the /itemize skill (outputs itemized-plan.md)
        claude --dangerously-skip-permissions "/cub:itemize ${plan_dir}"

        # Convert the markdown plan to beads JSONL
        if [[ -f "$md_file" ]]; then
            log_info "Converting markdown plan to beads JSONL..."
            local plan_prefix
            plan_prefix=$(jq -r '.epic_id // ""' "${plan_dir}/plan.json" 2>/dev/null)
            if [[ -z "$plan_prefix" ]]; then
                plan_prefix="${plan_slug%%-*}"
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
            plan_update "$plan_slug" "itemize" "needs_human"
            echo ""
            log_warn "Plan needs human input before continuing."
            log_info "Output: ${jsonl_file}"
            echo ""
            cat "$jsonl_file"
            return 2
        fi

        plan_update "$plan_slug" "itemize" "complete"
        echo ""

        # Count tasks
        local epic_count task_count
        epic_count=$(grep -c '"issue_type":"epic"' "$jsonl_file" 2>/dev/null || echo "0")
        task_count=$(grep -c '"issue_type":"task"' "$jsonl_file" 2>/dev/null || echo "0")

        log_success "Plan generated: ${epic_count} epics, ${task_count} tasks"
        log_info "JSONL: ${jsonl_file}"
        [[ -f "$md_file" ]] && log_info "Summary: ${md_file}"
        log_info "Next step: cub stage ${plan_slug}"
    else
        echo ""
        log_warn "Plan session ended but JSONL file not created."
        log_info "Plan: ${plan_slug}"
        log_info "Expected output: ${jsonl_file}"
        log_info "Resume with: cub plan itemize ${plan_slug}"
    fi

    return 0
}

_itemize_help() {
    cat <<EOF
Usage: cub plan itemize [OPTIONS] [PLAN_SLUG]

Stage 3: Task Decomposition

Launches an interactive Claude session to break architecture into
executable, AI-agent-friendly tasks.

Arguments:
  PLAN_SLUG         Plan slug from architect (default: most recent)

Options:
  --plan SLUG            Specify plan slug
  --non-interactive      Run without an interactive Claude session
  -h, --help             Show this help message

Examples:
  cub plan itemize                     # Use most recent plan
  cub plan itemize my-feature          # Specific plan
  cub plan itemize --plan my-feature   # Explicit plan flag

Output:
  plans/{plan-slug}/itemized-plan.jsonl     (Beads-compatible)
  plans/{plan-slug}/itemized-plan.md        (Human-readable)

Next Step:
  cub stage {plan-slug}
EOF
}

# ============================================================================
# Stage Command (cmd_stage)
# ============================================================================

# Wire up dependencies from itemized-plan.jsonl after import
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

cmd_stage() {
    local plan_slug=""
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
                _stage_help
                return 0
                ;;
            -*)
                _log_error_console "Unknown option: $1"
                _stage_help
                return 1
                ;;
            *)
                plan_slug="$1"
                shift
                ;;
        esac
    done

    # Get plan slug
    if [[ -z "$plan_slug" ]]; then
        plan_slug=$(plan_most_recent)
        if [[ -z "$plan_slug" ]]; then
            _log_error_console "No plan specified and no recent plan found."
            return 1
        fi
        log_info "Using most recent plan: ${plan_slug}"
    fi

    # Verify plan exists
    if ! plan_exists "$plan_slug"; then
        _log_error_console "Plan not found: ${plan_slug}"
        return 1
    fi

    # Verify itemize is complete
    if ! plan_has_itemize "$plan_slug"; then
        _log_error_console "Itemize not complete for plan: ${plan_slug}"
        _log_error_console "Run 'cub plan itemize ${plan_slug}' first."
        return 1
    fi

    local plan_dir
    plan_dir=$(plan_dir "$plan_slug")
    local plan_file="${plan_dir}/itemized-plan.jsonl"

    log_info "Staging from plan: ${plan_slug}"

    # Pre-flight checks
    log_info "Running pre-flight checks..."

    # Check 1: Git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        _log_error_console "Not a git repository. Initialize with 'git init' first."
        return 1
    fi
    log_debug "  Git repository found"

    # Check 2: Clean working directory
    local git_status
    git_status=$(git status --porcelain)
    if [[ -n "$git_status" ]]; then
        log_warn "Uncommitted changes detected:"
        echo "$git_status" | head -10
        log_warn "Consider committing or stashing before staging."
    else
        log_debug "  Working directory clean"
    fi

    # Check 3: Required tools
    if ! command -v bd &> /dev/null; then
        _log_error_console "Beads CLI (bd) not found."
        _log_error_console "Install from: https://github.com/steveyegge/beads"
        return 1
    fi
    log_debug "  Beads CLI found"

    if ! command -v jq &> /dev/null; then
        _log_error_console "jq not found. Install with: brew install jq"
        return 1
    fi
    log_debug "  jq found"

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
        _generate_prompt_md "$plan_dir"
        _generate_agent_md "$plan_dir"
    fi

    # Update plan status
    plan_update "$plan_slug" "stage" "complete"

    # Create git commit
    log_info "Creating staging commit..."
    git add .beads/
    [[ -f "${PROJECT_DIR}/.cub/prompt.md" ]] && git add .cub/prompt.md
    [[ -f "${PROJECT_DIR}/.cub/agent.md" ]] && git add .cub/agent.md

    git commit -m "chore: bootstrap beads from cub plan

Plan: ${plan_slug}
Imported: ${epic_count} epics, ${task_count} tasks

Generated by: cub stage" || true

    # Summary
    echo ""
    log_success "Staging complete!"
    echo ""
    log_info "Next steps:"
    log_info "  1. Review tasks: bd ready"
    log_info "  2. Start work: cub run"

    return 0
}

_generate_prompt_md() {
    local plan_dir="$1"
    local orientation_file="${plan_dir}/orientation.md"
    local architecture_file="${plan_dir}/architecture.md"
    local output_file
    output_file=$(get_prompt_file "${PROJECT_DIR}")

    # Extract key sections from orientation and architecture
    cat > "$output_file" <<EOF
# Project Prompt

This file provides context for AI coding agents working on this project.

## Overview

$(grep -A5 "## Executive Summary" "$orientation_file" 2>/dev/null | tail -n+2 || echo "See orientation.md for details.")

## Problem Statement

$(grep -A5 "## Problem Statement" "$orientation_file" 2>/dev/null | tail -n+2 || echo "See orientation.md for details.")

## Technical Approach

$(grep -A10 "## Technical Summary" "$architecture_file" 2>/dev/null | tail -n+2 || echo "See architecture.md for details.")

## Architecture

$(grep -A20 "## System Architecture" "$architecture_file" 2>/dev/null | tail -n+2 || echo "See architecture.md for details.")

## Requirements

### P0 (Must Have)
$(grep -A10 "### P0" "$orientation_file" 2>/dev/null | tail -n+2 | head -5 || echo "See orientation.md")

## Constraints

$(grep -A5 "## Constraints" "$orientation_file" 2>/dev/null | tail -n+2 || echo "None specified.")

---

Generated by cub plan. Plan artifacts in plans/
EOF

    log_debug "  Created prompt.md"
}

_generate_agent_md() {
    local plan_dir="$1"
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

Generated by cub plan. Customize based on your project.
EOF

    log_debug "  Created agent.md"
}

_stage_help() {
    cat <<EOF
Usage: cub stage [OPTIONS] [PLAN_SLUG]

Stage 4: Transition to Execution

Initialize beads and import the generated plan.

Arguments:
  PLAN_SLUG         Plan slug from itemize (default: most recent)

Options:
  --prefix PREFIX    Beads prefix for issue IDs
  --skip-prompt      Don't generate PROMPT.md and AGENT.md
  --dry-run          Preview actions without executing
  -h, --help         Show this help message

Examples:
  cub stage                        # Stage most recent plan
  cub stage my-feature             # Stage specific plan
  cub stage --dry-run              # Preview staging actions
  cub stage --prefix myproj        # Use custom prefix

Actions:
  1. Run pre-flight checks (git, tools)
  2. Initialize beads (if needed)
  3. Import itemized-plan.jsonl
  4. Generate PROMPT.md and AGENT.md
  5. Create git commit

Next Step:
  cub run    # Start autonomous execution
EOF
}

# ============================================================================
# Unified Plan Run Command (cmd_plan_run)
# ============================================================================

cmd_plan_run() {
    local plan_slug=""
    local non_interactive="false"
    local spec_path=""
    local continue_last="false"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --plan)
                plan_slug="$2"
                shift 2
                ;;
            --plan=*)
                plan_slug="${1#--plan=}"
                shift
                ;;
            --continue)
                continue_last="true"
                shift
                ;;
            --spec)
                spec_path="$2"
                shift 2
                ;;
            --spec=*)
                spec_path="${1#--spec=}"
                shift
                ;;
            --non-interactive|--auto)
                non_interactive="true"
                shift
                ;;
            --help|-h)
                _plan_run_help
                return 0
                ;;
            -*)
                _log_error_console "Unknown option: $1"
                _plan_run_help
                return 1
                ;;
            *)
                # Allow a positional spec path.
                if [[ -z "$spec_path" ]]; then
                    spec_path="$1"
                fi
                shift
                ;;
        esac
    done

    echo ""
    log_info "---------------------------------------------------"
    log_info "         CUB VISION-TO-TASKS PLANNING"
    log_info "---------------------------------------------------"
    echo ""

    # Determine which stage to start
    local start_stage=""
    local plan_dir=""

    if [[ -n "$plan_slug" ]]; then
        # Explicit plan provided
        if ! plan_exists "$plan_slug"; then
            _log_error_console "Plan not found: $plan_slug"
            return 1
        fi
        plan_dir=$(plan_dir "$plan_slug")
        log_info "Resuming plan: ${plan_slug}"

        # Get spec path from plan if not explicitly provided
        if [[ -z "$spec_path" ]]; then
            spec_path=$(plan_get_spec_path "$plan_slug")
        fi
    elif [[ "$continue_last" == "true" ]]; then
        # Continue most recent plan
        plan_slug=$(plan_most_recent)
        if [[ -n "$plan_slug" ]]; then
            plan_dir=$(plan_dir "$plan_slug")
            log_info "Continuing most recent plan: ${plan_slug}"

            # Get spec path from plan if not explicitly provided
            if [[ -z "$spec_path" ]]; then
                spec_path=$(plan_get_spec_path "$plan_slug")
            fi
        else
            _log_error_console "No existing plans found. Run without --continue to create a new plan."
            return 1
        fi
    else
        # Default: create a new plan
        log_info "Starting new plan..."
    fi

    # Determine next step based on existing artifacts
    if [[ -n "$plan_dir" ]]; then
        if [[ -f "${plan_dir}/itemized-plan.jsonl" ]]; then
            start_stage="stage"
        elif [[ -f "${plan_dir}/architecture.md" ]]; then
            start_stage="itemize"
        elif [[ -f "${plan_dir}/orientation.md" ]]; then
            start_stage="architect"
        else
            start_stage="orient"
        fi
    else
        start_stage="orient"
    fi

    # Launch the appropriate stage
    case "$start_stage" in
        orient)
            log_info "Starting Stage 1: Orient"
            echo ""
            # Build orient arguments
            local orient_args=()
            if [[ "$non_interactive" == "true" ]]; then
                orient_args+=("--non-interactive")
            fi
            if [[ -n "$spec_path" ]]; then
                orient_args+=("--spec" "$spec_path")
            fi
            cmd_orient "${orient_args[@]}"
            ;;
        architect)
            log_info "Starting Stage 2: Architect"
            echo ""
            if [[ "$non_interactive" == "true" ]]; then
                cmd_architect --non-interactive --plan "$plan_slug"
            else
                cmd_architect --plan "$plan_slug"
            fi
            ;;
        itemize)
            log_info "Starting Stage 3: Itemize"
            echo ""
            if [[ "$non_interactive" == "true" ]]; then
                cmd_itemize --non-interactive --plan "$plan_slug"
            else
                cmd_itemize --plan "$plan_slug"
            fi
            ;;
        stage)
            log_info "Starting Stage 4: Stage"
            echo ""
            cmd_stage "$plan_slug"
            ;;
    esac

    # Get plan slug after stage completes (may have been created during orient)
    plan_slug=$(plan_most_recent)
    plan_dir=$(plan_dir "$plan_slug")

    # Report plan status
    echo ""
    _plan_report_status "$plan_slug"

    return 0
}

# Report the current plan status and remaining steps
_plan_report_status() {
    local plan_slug="$1"
    local plan_dir
    plan_dir=$(plan_dir "$plan_slug")

    local has_orient=false
    local has_architect=false
    local has_itemize=false
    local has_stage=false

    [[ -f "${plan_dir}/orientation.md" ]] && has_orient=true
    [[ -f "${plan_dir}/architecture.md" ]] && has_architect=true
    [[ -f "${plan_dir}/itemized-plan.jsonl" ]] && has_itemize=true

    # Check stage status from plan.json
    if [[ -f "${plan_dir}/plan.json" ]]; then
        local stage_status
        stage_status=$(jq -r '.stages.stage // ""' "${plan_dir}/plan.json" 2>/dev/null)
        [[ "$stage_status" == "complete" ]] && has_stage=true
    fi

    log_info "---------------------------------------------------"
    log_info "         PLAN STATUS"
    log_info "---------------------------------------------------"
    echo ""
    log_info "Plan: ${plan_slug}"
    echo ""

    # Show status of each stage
    if [[ "$has_orient" == "true" ]]; then
        echo "  [x] Orient    - orientation.md"
    else
        echo "  [ ] Orient    - pending"
    fi

    if [[ "$has_architect" == "true" ]]; then
        echo "  [x] Architect - architecture.md"
    else
        echo "  [ ] Architect - pending"
    fi

    if [[ "$has_itemize" == "true" ]]; then
        echo "  [x] Itemize   - itemized-plan.jsonl"
    else
        echo "  [ ] Itemize   - pending"
    fi

    if [[ "$has_stage" == "true" ]]; then
        echo "  [x] Stage     - complete"
    else
        echo "  [ ] Stage     - pending"
    fi

    echo ""

    # Determine next step
    if [[ "$has_stage" == "true" ]]; then
        log_success "Planning complete!"
        log_info "Ready to start: cub run"
    elif [[ "$has_itemize" == "true" ]]; then
        log_info "Next step: cub stage ${plan_slug}"
    elif [[ "$has_architect" == "true" ]]; then
        log_info "Next step: cub plan itemize ${plan_slug}"
    elif [[ "$has_orient" == "true" ]]; then
        log_info "Next step: cub plan architect ${plan_slug}"
    else
        log_info "Next step: cub plan orient --plan ${plan_slug}"
    fi

    log_info "Or run: cub plan run --plan ${plan_slug}"
    echo ""
}

_plan_run_help() {
    cat <<EOF
Usage: cub plan run [OPTIONS] [SPEC_FILE]

Run the Vision-to-Tasks planning workflow one stage at a time.

Each invocation launches an interactive Claude session for the next
incomplete stage. After you exit Claude, plan shows your progress
and the next step.

Stages:
  1. Orient    - Interactive requirements refinement (/cub:orient)
  2. Architect - Interactive technical design (/cub:architect)
  3. Itemize   - Interactive task decomposition (/cub:itemize)
  4. Stage     - Initialize beads and import tasks (shell)

Arguments:
  SPEC_FILE              Spec/vision document to prime the planning pipeline
                         (e.g., specs/researching/new-idea.md)
                         Stored in plan metadata for all stages

Options:
  --plan SLUG            Resume a specific plan
  --continue             Resume the most recent plan (default: create new)
  --non-interactive      Run stages using \`claude -p\` (best-effort)
  --spec PATH            Explicit spec file path (alternative to positional arg)
  -h, --help             Show this help message

Examples:
  cub plan run                               # Start or continue planning
  cub plan run specs/new-feature.md          # Start plan with specific spec
  cub plan run --plan my-feature             # Resume specific plan
  cub plan run --spec specs/ideas.md         # Explicit spec file

Workflow:
  1. Run 'cub plan run specs/doc.md' - starts orient session with spec
  2. Complete orient interview, exit Claude
  3. Run 'cub plan run' again - continues to architect (uses saved spec)
  4. Repeat until all stages complete

Output:
  plans/{plan-slug}/
    |-- plan.json              # Plan metadata (includes spec_path)
    |-- orientation.md         # Refined requirements
    |-- architecture.md        # Technical design
    |-- itemized-plan.jsonl    # Beads-compatible tasks
    \`-- itemized-plan.md       # Human-readable plan

Individual Commands:
  cub plan orient [SPEC_FILE]   # Just run orient
  cub plan architect [PLAN]     # Just run architect
  cub plan itemize [PLAN]       # Just run itemize
  cub stage [PLAN]              # Just run stage
EOF
}

# ============================================================================
# Plan List Management (cmd_plan_list)
# ============================================================================

cmd_plan_list() {
    local subcommand="${1:-list}"
    shift || true

    case "$subcommand" in
        list|ls)
            _plan_list "$@"
            ;;
        show)
            _plan_show "$@"
            ;;
        delete|rm)
            _plan_delete "$@"
            ;;
        --help|-h|help)
            _plan_list_help
            ;;
        *)
            # Default: treat as list
            _plan_list "$subcommand" "$@"
            ;;
    esac
}

_plan_list() {
    local plans
    plans=$(plan_list_all)

    if [[ -z "$plans" ]]; then
        log_info "No plans found."
        log_info "Run 'cub plan orient' to create a plan."
        return 0
    fi

    echo ""
    log_info "Plans"
    echo ""

    for plan in $plans; do
        local orient_status="[ ]"
        local architect_status="[ ]"
        local itemize_status="[ ]"
        local stage_status="[ ]"

        plan_has_orient "$plan" && orient_status="[x]"
        plan_has_architect "$plan" && architect_status="[x]"
        plan_has_itemize "$plan" && itemize_status="[x]"

        local plan_dir
        plan_dir=$(plan_dir "$plan")
        local plan_file="${plan_dir}/plan.json"
        if [[ -f "$plan_file" ]]; then
            local st_status
            st_status=$(jq -r '.stages.stage // "-"' "$plan_file" 2>/dev/null)
            [[ "$st_status" == "complete" ]] && stage_status="[x]"
        fi

        echo "$plan"
        echo "  Orient: $orient_status  Architect: $architect_status  Itemize: $itemize_status  Stage: $stage_status"
        echo ""
    done
}

_plan_show() {
    local plan_slug="${1:-}"

    if [[ -z "$plan_slug" ]]; then
        plan_slug=$(plan_most_recent)
        if [[ -z "$plan_slug" ]]; then
            _log_error_console "No plan specified and no plans found."
            return 1
        fi
    fi

    if ! plan_exists "$plan_slug"; then
        _log_error_console "Plan not found: ${plan_slug}"
        return 1
    fi

    local plan_dir
    plan_dir=$(plan_dir "$plan_slug")

    echo ""
    log_info "Plan: ${plan_slug}"
    echo ""
    log_info "Directory: ${plan_dir}"
    echo ""
    log_info "Artifacts:"

    [[ -f "${plan_dir}/orientation.md" ]] && echo "  orientation.md"
    [[ -f "${plan_dir}/architecture.md" ]] && echo "  architecture.md"
    [[ -f "${plan_dir}/itemized-plan.jsonl" ]] && echo "  itemized-plan.jsonl"
    [[ -f "${plan_dir}/itemized-plan.md" ]] && echo "  itemized-plan.md"
    [[ -f "${plan_dir}/plan.json" ]] && echo "  plan.json"

    echo ""

    if [[ -f "${plan_dir}/plan.json" ]]; then
        log_info "Plan Info:"
        jq '.' "${plan_dir}/plan.json"
    fi
}

_plan_delete() {
    local plan_slug="${1:-}"

    if [[ -z "$plan_slug" ]]; then
        _log_error_console "Plan slug required for delete."
        return 1
    fi

    if ! plan_exists "$plan_slug"; then
        _log_error_console "Plan not found: ${plan_slug}"
        return 1
    fi

    local plan_dir
    plan_dir=$(plan_dir "$plan_slug")

    log_warn "Deleting plan: ${plan_slug}"
    rm -rf "$plan_dir"
    log_success "Plan deleted."
}

_plan_list_help() {
    cat <<EOF
Usage: cub plan list [COMMAND] [OPTIONS]

Manage plans.

Commands:
  list, ls           List all plans (default)
  show [PLAN]        Show plan details
  delete, rm PLAN    Delete a plan

Examples:
  cub plan list                      # List all plans
  cub plan list show                 # Show most recent plan
  cub plan list show my-feature      # Show specific plan
  cub plan list delete my-feature    # Delete plan
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
        _log_error_console "No .beads directory found. Run 'cub stage' first."
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

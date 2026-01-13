# PRD Import / Document Conversion

**Source:** [ralph-claude-code](https://github.com/frankbria/ralph-claude-code)
**Dependencies:** None
**Complexity:** High

---

## Integration Note: Vision-to-Tasks Pipeline

**PRD Import is the LIGHTWEIGHT alternative** to the full Vision-to-Tasks Pipeline.

| Approach | Command | When to Use |
|----------|---------|-------------|
| **Full Pipeline** | `cub pipeline` | Complex projects, greenfield, need architecture |
| **PRD Import** | `cub import` | Simple projects, existing structured docs, quick start |

**Full Pipeline:** `cub triage` → `cub architect` → `cub plan` → `cub bootstrap`
- Interactive interviews
- Architecture design
- Mindset-aware task generation
- Rich task descriptions with implementation hints

**PRD Import:** `cub import document.md`
- Direct conversion
- Minimal interaction
- Best for already-structured documents
- Faster but less sophisticated

Both output beads-compatible tasks. Use PRD Import when you have a well-structured document and want to skip the interactive planning stages.

---

## Overview

Convert existing requirements documents into cub task format, enabling quick project bootstrapping from various input sources.

## Reference Implementation

From Ralph:
> "PRD import converting existing requirements (markdown, PDF, JSON, etc.) into Ralph format"

Command: `ralph-import requirements.md project-name`

Ralph transforms documents into:
- PROMPT.md (system instructions)
- @fix_plan.md (task list)
- specs/ directory (detailed specifications)

## Proposed Interface

```bash
# Import from local file
cub import requirements.md
cub import spec.pdf
cub import tasks.json

# Import from URL
cub import https://example.com/spec.md

# Import from GitHub
cub import --github owner/repo           # All open issues
cub import --github owner/repo/issues/42 # Single issue
cub import --github owner/repo --labels "priority:high"

# Import from Linear/Jira (future)
cub import --linear project-id
cub import --jira PROJECT-KEY

# Options
cub import requirements.md --dry-run     # Preview without creating
cub import requirements.md --backend beads|json
cub import requirements.md --epic "Feature X"  # Group under epic
```

## Supported Input Formats

### Markdown (.md)
Parse structure:
- `# Headings` -> Epic/feature boundaries
- `## Subheadings` -> Task groups
- `- [ ] Checkbox items` -> Individual tasks
- `- Bullet points` -> Tasks or acceptance criteria
- Code blocks -> Technical requirements

### PDF (.pdf)
- Extract text using `pdftotext` or similar
- Parse as markdown after extraction
- Preserve section structure where possible

### JSON (.json)
Support common formats:
```json
// Array of tasks
[
  {"title": "...", "description": "...", "priority": "P1"}
]

// Structured PRD
{
  "project": "...",
  "features": [
    {
      "name": "...",
      "tasks": [...]
    }
  ]
}
```

### Plain Text (.txt)
- Line-based parsing
- Numbered lists -> ordered tasks
- Blank lines -> task boundaries

### GitHub Issues
```bash
# Fetch via gh CLI
gh issue list --repo owner/repo --json number,title,body,labels,milestone

# Convert to tasks with:
# - Issue number as reference
# - Labels preserved
# - Milestone as epic
# - Body parsed for acceptance criteria
```

## Conversion Logic

### Task Extraction

```bash
# Pseudocode for markdown parsing
parse_markdown() {
  local file=$1
  local current_epic=""
  local current_task=""

  while IFS= read -r line; do
    case "$line" in
      "# "*)
        # H1 = Epic
        current_epic="${line#\# }"
        emit_epic "$current_epic"
        ;;
      "## "*)
        # H2 = Feature/Task group
        emit_feature "${line#\#\# }" "$current_epic"
        ;;
      "- [ ] "*)
        # Checkbox = Task
        emit_task "${line#- \[ \] }" "$current_epic"
        ;;
      "- "*)
        # Bullet = Task or acceptance criteria (context-dependent)
        handle_bullet "${line#- }"
        ;;
    esac
  done < "$file"
}
```

### Priority Inference

Detect priority from:
- Explicit markers: `[P0]`, `(high priority)`, `CRITICAL`
- Position in document (earlier = higher)
- Keywords: "must", "critical", "blocker", "nice to have"

```bash
infer_priority() {
  local text=$1

  if [[ "$text" =~ (P0|critical|blocker|must.have) ]]; then
    echo "P0"
  elif [[ "$text" =~ (P1|high|important|required) ]]; then
    echo "P1"
  elif [[ "$text" =~ (P3|low|nice.to.have|optional) ]]; then
    echo "P3"
  else
    echo "P2"  # Default
  fi
}
```

### Dependency Detection

Look for dependency signals:
- "after X is complete"
- "depends on Y"
- "blocked by Z"
- "requires A"
- Numbered sequences imply order

### Acceptance Criteria Extraction

Parse from:
- Sub-bullets under tasks
- "Acceptance criteria:" sections
- "Done when:" markers
- Checkbox sublists

## Output Generation

### For JSON Backend (prd.json)

```json
{
  "tasks": [
    {
      "id": "imported-001",
      "type": "feature",
      "title": "User authentication",
      "description": "Implement login and registration flow",
      "acceptanceCriteria": [
        "Login form validates email format",
        "Password requires 8+ characters",
        "Session persists across page refresh"
      ],
      "priority": "P1",
      "status": "open",
      "dependsOn": [],
      "labels": ["imported", "auth"],
      "source": {
        "file": "requirements.md",
        "line": 42
      }
    }
  ]
}
```

### For Beads Backend

```bash
# Create tasks via bd CLI
bd create --title "User authentication" \
          --type feature \
          --priority 1 \
          --label imported \
          --label auth

# Add dependencies after all created
bd dep add $task_id $depends_on_id
```

## AI-Assisted Parsing

For complex documents, use AI to help parse:

```bash
parse_with_ai() {
  local file=$1
  local content
  content=$(cat "$file")

  # Generate structured task list using harness
  local prompt="Parse this requirements document into a structured task list.
Output JSON with: title, description, acceptanceCriteria[], priority, dependencies[]

Document:
$content"

  invoke_harness --prompt "$prompt" --output json
}
```

## Configuration

```json
{
  "import": {
    "default_backend": "auto",
    "default_priority": "P2",
    "default_type": "task",
    "ai_assisted": true,
    "preserve_source_refs": true,
    "github": {
      "include_closed": false,
      "label_filter": null,
      "milestone_as_epic": true
    }
  }
}
```

## Implementation Notes

### Dependencies

- `pdftotext` (poppler-utils) for PDF support
- `gh` CLI for GitHub import
- `jq` for JSON processing (already required)

### New Files

- `lib/cmd_import.sh` - Import subcommand
- `lib/parsers/` - Format-specific parsers
  - `lib/parsers/markdown.sh`
  - `lib/parsers/json.sh`
  - `lib/parsers/github.sh`
  - `lib/parsers/pdf.sh`

## Acceptance Criteria

- [ ] Import from Markdown files
- [ ] Import from JSON files
- [ ] Import from GitHub issues (via gh CLI)
- [ ] Dry-run mode shows preview
- [ ] Tasks created in configured backend
- [ ] Dependencies extracted and linked
- [ ] Priority inferred from content
- [ ] Source references preserved
- [ ] Works with both beads and json backends

## Future Enhancements

- Linear integration
- Jira integration
- Notion import
- Google Docs import
- Figma design spec import
- Interactive import wizard
- Conflict resolution for re-imports

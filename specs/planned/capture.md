---
status: planned
priority: high
complexity: medium
dependencies: []
blocks:
  - capture-workflow.md
  - pm-workbench.md
created: 2026-01-15
updated: 2026-01-19
implementation_status: partial
notes: |
  Core capture command implemented in Clawdbot skill.
  Needs cub capture CLI, import-captures, organize-captures.
  Auto-tagging and search improvements remain.
readiness:
  score: 7
  blockers:
    - import-captures command not yet implemented
    - organize-captures command not yet implemented
    - Auto-tagging not yet implemented
  questions:
    - Should we maintain a suggested tag vocabulary per project?
    - Any concern about captures/ growing unboundedly? Periodic archive prompts?
    - Search implementation: simple grep or build an index?
    - Should URL capture fetch and summarize content automatically?
  decisions_needed:
    - Choose search backend (grep vs fzf vs dedicated index)
    - Decide on capture promotion workflow (manual vs assisted)
  tools_needed:
    - API Design Validator (design CLI interface and capture format)
    - Implementation Path Generator (break into tasks)
    - Tag suggester (domain-specific: analyze content and suggest relevant tags)
    - Capture search indexer (domain-specific: for faster search across many captures)
    - Similarity detector (domain-specific: find related/duplicate captures)
---

# Feature Spec: Capture

## Overview

`cub capture` provides low-friction idea collection—a scratchpad for thoughts, links, observations, and inspiration that feeds into the vision-to-tasks pipeline. Captures are the raw material from which specs, spikes, and features eventually emerge.

## Goals

- **Zero friction**: Capture an idea in seconds
- **Human-editable**: Markdown files that can be manually created/edited
- **Searchable**: Find captures by tag, content, or time
- **Progressive**: Ideas can be refined through interactive sessions
- **Portable**: Global captures for ideas not yet tied to a project

## Non-Goals (v1)

- URL fetching/summarization (punt for now)
- Automatic promotion to specs (manual process)
- Cross-project capture linking
- Rich media attachments

---

## Storage

Captures use a **two-tier storage model**:

1. **Global captures** (default): Stored outside the repo, safe from branch chaos
2. **Project captures** (imported): Version-controlled with the project

### Global Captures (Default)

All captures are written to a global location by default, organized by project:

```
~/.local/share/cub/captures/
├── cub/                          # Captures made in "cub" project
│   ├── 2026-01-16-parallel-clones.md
│   └── 2026-01-16-ui-ideas.md
├── jefe/                         # Captures made in "jefe" project
│   └── 2026-01-17-api-redesign.md
└── _global/                      # Captures made outside any git repo
    └── 2026-01-15-random-thought.md
```

**Why global by default?**
- Captures survive branch deletion
- No accidental commits mixing ideas with feature work
- Safe across repo re-clones (captures are external)
- Enables cross-project capture browsing

### Project Captures (Imported)

When a capture is ready to be version-controlled with the project, import it:

```
captures/
├── 2026-01-16-parallel-clones.md   # Imported, now tracked in git
└── 2026-01-17-finalized-spec.md
```

Import is a conscious decision: "this idea is now part of this project's permanent record."

### Project Identifier

To maintain consistency across multiple working copies and repo renames, the project identifier is stored in `.cub/config.json`:

```json
{
  "project_id": "cub"
}
```

**Auto-inference**: If `project_id` is missing, cub infers it from the git remote origin:
- `git@github.com:user/my-project.git` → `my-project`
- `https://github.com/user/my-project.git` → `my-project`
- No remote → directory basename

Once inferred, the ID is written to `.cub/config.json` for consistency.

---

## File Format

Individual markdown files with YAML frontmatter:

```markdown
---
id: cap-001
created: 2026-01-16T14:32:00Z
tags: [git, workflow]
title: "Parallel Clones Instead of Worktrees"
source: cli
status: active
priority: null
---

# Parallel Clones Instead of Worktrees

Ryan Carson approach: Clone repo 3x (project-01, -02, -03), run agents
in each, use `git pushsync` to sync without switching branches.

Simpler than worktrees. Worth considering if we want parallel agent support.
```

### Frontmatter Schema

| Field | Required | Auto-generated | Description |
|-------|----------|----------------|-------------|
| `id` | Yes | Yes | Sequential ID: `cap-001`, `cap-002`, etc. |
| `created` | Yes | Yes | ISO 8601 timestamp |
| `tags` | No | Yes (auto) | Array of tags; auto-suggested, can override with `--tag` |
| `title` | No | Yes | Short title; auto-generated from content, can override |
| `source` | No | Yes | How it was created: `cli`, `pipe`, `interactive`, `manual` |
| `status` | No | Yes | `active` (default), `archived` |
| `priority` | No | No | Optional priority signal for later processing |

### File Naming

Format: `{date}-{slug}.md`

- **Date**: `YYYY-MM-DD` from creation timestamp
- **Slug**: Auto-generated from first ~40 chars of content, kebab-cased
- **Override**: `--name` flag for explicit filename

Examples:
- `2026-01-16-parallel-clones-instead-of-worktrees.md`
- `2026-01-16-ui-ideas-for-cub.md`

### ID Generation

Sequential within the captures directory:
- Scan existing files for highest `cap-NNN`
- Increment for new capture
- IDs are stable once assigned (don't renumber on delete)

---

## CLI Interface

### Creating Captures

```bash
# Basic capture - content as argument
cub capture "parallel clones instead of worktrees - see ryan carson"

# With explicit tags (in addition to auto-tags)
cub capture --tag git --tag workflow "some idea"

# With explicit filename
cub capture --name my-idea "explicit filename becomes my-idea.md"

# With priority
cub capture --priority 1 "urgent idea to explore"

# Pipe support
echo "idea from script" | cub capture
pbpaste | cub capture --tag ui

# Interactive mode - guided session
cub capture -i
cub capture -i "topic to explore"
```

### Listing Captures

```bash
# List captures for current project (both global and imported)
cub captures

# Output shows both locations:
#   GLOBAL (3 captures in ~/.local/share/cub/captures/cub/)
#   cap-001  2026-01-16  parallel-clones-idea        [git, workflow]
#   cap-002  2026-01-16  ui-dashboard-concepts       [ui]
#   cap-003  2026-01-17  worktree-alternatives       [git]
#
#   PROJECT (1 capture in ./captures/)
#   cap-004  2026-01-15  finalized-auth-spec         [auth, spec]

# List all captures (default: 20 most recent)
cub captures --all

# Filter by tag
cub captures --tag git

# Filter by time
cub captures --since 7d
cub captures --since 2026-01-01

# Full-text search
cub captures --search "worktree"

# Only global captures
cub captures --global

# Only project captures
cub captures --project

# All projects (cross-project view)
cub captures --all-projects

# JSON output for scripting
cub captures --json
```

### Managing Captures

```bash
# Show full capture
cub captures show cap-001
cub captures show 001              # Short form

# Edit in $EDITOR
cub captures edit cap-001

# Archive (sets status: archived)
cub captures archive cap-001
```

### Importing Captures

Import graduates a capture from global storage to version-controlled project storage:

```bash
# Import specific capture by ID
cub import-captures cap-001

# Import specific capture by filename
cub import-captures 2026-01-16-parallel-clones.md

# Import all global captures for this project
cub import-captures --all

# Preview what would be imported
cub import-captures --all --dry-run
```

After import:
- File is copied from `~/.local/share/cub/captures/{project}/` to `./captures/`
- Original global file can be kept (`--keep`) or removed (default)
- ID remains the same for traceability

### Organizing Captures

```bash
# Normalize manually-added files
cub organize-captures

# Preview changes without applying
cub organize-captures --dry-run
```

The `organize-captures` command:
- Adds missing frontmatter to .md files without it
- Generates IDs for files without them
- Normalizes filenames **only when**:
  - File lacks date prefix
  - File lacks complete frontmatter (was added out-of-band)
- Detects potential duplicates (same title/similar content)
- Interactive confirmation before changes (unless `--yes`)

---

## Interactive Mode

`cub capture -i` invokes a guided skill session, lighter than triage but more structured than raw capture.

The skill can also be invoked directly in Claude Code: `/cub:capture`

### Skill Definition: `/cub:capture`

**Purpose**: Help a person think through a nascent idea, extract the core insight, and save it as a capture.

**Tone**: Curious collaborator. Not interrogating, not validating—genuinely exploring alongside the user. Think "coffee chat with a thoughtful colleague" not "requirements gathering interview."

**Principles**:
- **Short sessions**: 2-5 minutes, not a deep dive (that's what `/cub:triage` is for)
- **Permissive**: Even half-baked ideas are valid captures
- **Non-judgmental**: Don't evaluate whether the idea is "good"
- **Extractive**: Help the user articulate what they already sense but haven't put into words
- **Generative**: Offer connections, analogies, or framings that might help
- **Actionable end state**: Always produce a capture file

**Conversation Flow**:

1. **Seed** (if topic provided): Acknowledge the starting point
2. **Explore** (2-3 open-ended questions):
   - "What caught your attention about this?"
   - "What problem might this solve?" / "What would this enable?"
   - "Where did this come from?" (saw something, frustration, shower thought?)
3. **Connect** (optional, if relevant):
   - "Does this relate to anything you're currently working on?"
   - "Have you seen similar approaches elsewhere?"
   - Offer your own connections if you see them
4. **Clarify** (help sharpen):
   - "If you had to explain this in one sentence, what would it be?"
   - "What's the key insight here?"
   - Reflect back what you're hearing to confirm understanding
5. **Capture** (wrap up):
   - Propose a title
   - Suggest tags based on conversation
   - Confirm and write the file

**Exit conditions**:
- User indicates they're done
- Core insight has been articulated and confirmed
- User explicitly asks to save
- Natural conclusion reached

**What NOT to do**:
- Don't turn this into a planning session (that's later stages)
- Don't evaluate feasibility or priority (unless asked)
- Don't ask more than 4-5 questions total
- Don't require the user to have answers—"I don't know yet" is valid

### Invocation

```bash
# Via CLI (launches Claude with skill)
cub capture -i
cub capture -i "topic to seed the conversation"

# Directly in Claude Code
/cub:capture
/cub:capture UI ideas for monitoring dashboard
```

### Flow (summary)

### Output Format

The resulting capture file contains:
- **Synopsis**: AI-generated summary at the top (after frontmatter)
- **Conversation log**: Full transcript of the interactive session

```markdown
---
id: cap-003
created: 2026-01-16T15:00:00Z
tags: [ui, dashboard, monitoring]
title: "UI for Cub - Dashboard Concepts"
source: interactive
status: active
---

# UI for Cub - Dashboard Concepts

## Synopsis

Explored potential UI approaches for cub, focusing on execution monitoring.
Key ideas: terminal dashboard (like k9s), web UI for cross-project view,
integration with existing tools. Priority is visibility into running tasks.

---

## Conversation

**What are you thinking about?**

I've been wanting some kind of UI for cub. Right now it's all CLI...

**Why is this interesting?**

Visibility into what's happening during cub run...

[rest of conversation]
```

---

## Auto-Tagging

When creating a capture, attempt to auto-generate relevant tags:

1. **Keyword extraction**: Common terms (git, ui, api, etc.)
2. **Project context**: If inside a project, consider project tech stack
3. **Content analysis**: LLM-assisted tag suggestion (lightweight, optional)

Auto-tags are suggestions. User can:
- Accept them (default)
- Override with `--tag` (adds to auto-tags)
- Disable with `--no-auto-tags`

---

## Implementation Notes

### Module Structure

```
src/cub/
├── cli/
│   ├── capture.py           # cub capture command
│   ├── captures.py          # cub captures command (list/show/edit/archive)
│   ├── import_captures.py   # cub import-captures command
│   └── organize_captures.py # cub organize-captures command
├── core/
│   └── captures/
│       ├── store.py         # Capture storage/retrieval (both global and project)
│       ├── models.py        # Capture Pydantic model
│       ├── project_id.py    # Project ID inference and storage
│       └── tagging.py       # Auto-tagging logic
└── .claude/commands/
    └── cub:capture.md       # Skill for /cub:capture and cub capture -i
```

### Dependencies

- **Existing**: typer, rich, pydantic
- **New**: python-frontmatter (for parsing/writing YAML frontmatter)

### Storage Paths

```python
# Global captures (organized by project)
GLOBAL_CAPTURES = Path.home() / ".local" / "share" / "cub" / "captures" / "{project_id}"

# Global captures for non-project contexts
GLOBAL_CAPTURES_UNSCOPED = Path.home() / ".local" / "share" / "cub" / "captures" / "_global"

# Project captures (version-controlled)
PROJECT_CAPTURES = PROJECT_DIR / "captures"

# Project config (stores project_id)
PROJECT_CONFIG = PROJECT_DIR / ".cub" / "config.json"
```

### Project ID Resolution

```python
def get_project_id() -> str:
    """Get or infer the project identifier."""
    # 1. Check .cub/config.json
    config = load_project_config()
    if config and config.get("project_id"):
        return config["project_id"]

    # 2. Infer from git remote
    remote = get_git_remote_origin()
    if remote:
        # git@github.com:user/project.git -> project
        # https://github.com/user/project.git -> project
        project_id = extract_repo_name(remote)
    else:
        # 3. Fall back to directory name
        project_id = Path.cwd().name

    # 4. Save for consistency
    save_project_config({"project_id": project_id})
    return project_id
```

---

## Future Considerations

These are explicitly out of scope for v1 but worth noting:

- **URL capture with summarization**: `cub capture https://...` fetches and extracts key points
- **Image/screenshot capture**: Store in captures/, reference in markdown
- **Capture promotion**: `cub captures promote cap-001 --to spec` creates spec from capture
- **Capture linking**: Reference other captures with `[[cap-001]]` syntax
- **Cross-project routing**: `cub capture -p other-project` to capture to a different project
- **Sync across machines**: Global captures directory could be synced via Dropbox/iCloud/git

---

## Implementation Status

- [x] Skill definition: `.claude/commands/cub:capture.md` (created)
- [ ] Core: Project ID inference and storage
- [ ] Core: Capture storage/retrieval (global + project)
- [ ] CLI: `cub capture` command
- [ ] CLI: `cub captures` command
- [ ] CLI: `cub import-captures` command
- [ ] CLI: `cub organize-captures` command
- [ ] Core: Auto-tagging

## Success Criteria

- [ ] `cub capture "text"` creates a file in `~/.local/share/cub/captures/{project}/` in < 1 second
- [ ] `cub captures` lists both global and project captures with clear separation
- [ ] `cub capture -i` / `/cub:capture` guides user through structured capture session
- [ ] `cub import-captures` moves captures from global to project storage
- [ ] Project ID is auto-inferred from git remote and persisted to `.cub/config.json`
- [ ] Captures survive branch deletion (stored externally)
- [ ] Manually-created .md files in `./captures/` are recognized by `cub captures`

---

## Open Questions

1. **Tag vocabulary**: Should we maintain a suggested tag list per project? Or purely free-form?
2. **Capture limits**: Any concern about captures/ growing unboundedly? Periodic archive prompts?
3. **Search implementation**: Simple grep, or build an index for faster search?

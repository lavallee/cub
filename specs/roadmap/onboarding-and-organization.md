# Onboarding & Project Organization

**Source:** Original feature for cub
**Dependencies:** None (foundational)
**Complexity:** Medium
**Priority:** High (affects all users, first impression)

## Overview

Improve the cub installation, initialization, and project organization experience to:
1. Make installation foolproof with clear feedback
2. Provide guided project setup with sensible defaults
3. Organize cub-related files cleanly in `.cub/`
4. Clarify which files are user-managed vs cub-managed
5. Deliver excellent documentation at every step

## Problem Statement

### Current Pain Points

**1. File Scatter at Project Root**
```
my-project/
├── AGENT.md           # Confusing: is this for me or the agent?
├── AGENTS.md          # Symlink to AGENT.md - why two files?
├── PROMPT.md          # System prompt - should I edit this?
├── progress.txt       # Agent appends here
├── @progress.txt      # Wait, what's this one?
├── fix_plan.md        # Agent maintains this
├── prd.json           # Tasks file
├── specs/             # My specs
├── .beads/            # If using beads
└── .cub/              # Runtime stuff
    └── runs/
```

Users are confused about:
- Which files to edit vs leave alone
- Why there are two progress files
- What goes in AGENT.md vs PROMPT.md
- The relationship between prd.json and .beads/

**2. Installation Confusion**
- `install.sh` vs cloning to PATH vs global install
- Dependencies not clearly checked upfront
- No verification that installation worked
- Harness installation is separate and unclear

**3. Initialization is One-Shot**
- `cub init` creates files without explanation
- No interactive mode for customization
- No detection of existing project patterns
- No templates for common project types

**4. Documentation is Scattered**
- README.md (long)
- docs/CONFIG.md (reference)
- UPGRADING.md (changes)
- In-template comments (brief)
- No quick-start guide

---

## Proposed Solution

### 1. Clean File Organization

Move all cub-managed files into `.cub/` with clear categories:

```
my-project/
├── .cub/                      # ALL cub files live here
│   ├── config.json            # Project-specific config (was .cub.json)
│   ├── prompt.md              # System prompt (was PROMPT.md)
│   ├── agent.md               # Agent instructions (was AGENT.md)
│   ├── guardrails.md          # Lessons learned (new)
│   ├── progress.md            # Session learnings (was progress.txt)
│   ├── fix_plan.md            # Discovered issues (moved)
│   ├── tasks.json             # Tasks (was prd.json, optional)
│   ├── hooks/                 # Project-specific hooks
│   │   ├── pre-loop.d/
│   │   ├── post-task.d/
│   │   └── ...
│   └── runs/                  # Run artifacts
│       └── {session-id}/
│           ├── run.json
│           └── tasks/
├── specs/                     # User specifications (stays at root)
├── CLAUDE.md                  # Symlink to .cub/agent.md (Claude Code convention)
└── AGENTS.md                  # Symlink to .cub/agent.md (Codex convention)
```

**Key Changes:**
- Everything cub touches is in `.cub/`
- User's specs stay at root (they own these)
- Symlinks at root for harness compatibility
- Single source of truth for agent instructions
- No more duplicate progress files

### 2. Improved Installation

#### 2.1 Installer Script

Enhanced `install.sh` with:

```bash
#!/usr/bin/env bash
# install.sh - Interactive cub installer

# Pre-flight checks with clear feedback
echo "Checking system requirements..."

check_requirement() {
  local name=$1 cmd=$2 install_hint=$3 required=$4

  if command -v "$cmd" &>/dev/null; then
    echo "  ✓ $name"
    return 0
  elif [[ "$required" == "true" ]]; then
    echo "  ✗ $name (required)"
    echo "    Install: $install_hint"
    return 1
  else
    echo "  ○ $name (optional)"
    echo "    Install: $install_hint"
    return 0
  fi
}

# Required
check_requirement "bash 3.2+" "bash" "brew install bash" true
check_requirement "jq" "jq" "brew install jq" true
check_requirement "git" "git" "brew install git" true

# Optional (harnesses)
echo ""
echo "Checking AI harnesses (need at least one)..."
HARNESS_OK=false
check_requirement "Claude Code" "claude" "npm install -g @anthropic/claude-code" false && HARNESS_OK=true
check_requirement "OpenAI Codex" "codex" "npm install -g @openai/codex" false && HARNESS_OK=true

if [[ "$HARNESS_OK" != "true" ]]; then
  echo ""
  echo "⚠ No AI harness found. Install one before using cub:"
  echo "  Claude Code: npm install -g @anthropic/claude-code"
  echo "  Codex:       npm install -g @openai/codex"
fi

# Installation with verification
echo ""
echo "Installing cub..."
# ... installation steps ...

# Verification
echo ""
echo "Verifying installation..."
if cub --version &>/dev/null; then
  echo "  ✓ cub $(cub --version)"
else
  echo "  ✗ Installation failed. Check PATH."
  exit 1
fi

# Next steps
echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "  1. cub init --global    # One-time global setup"
echo "  2. cd your-project"
echo "  3. cub init             # Initialize project"
echo "  4. cub doctor           # Verify everything works"
```

#### 2.2 One-Line Install

Support curl-pipe installation:

```bash
# One-liner for quick install
curl -fsSL https://raw.githubusercontent.com/lavallee/cub/main/install.sh | bash

# Or with options
curl -fsSL ... | bash -s -- --global
```

### 3. Guided Project Initialization

#### 3.1 Interactive Mode

```bash
$ cub init

Welcome to Cub! Let's set up your project.

? What type of project is this?
  ❯ Web application (Node/React/Next.js)
    API/Backend (Node/Python/Go)
    CLI tool (Bash/Go/Rust)
    Library/Package
    Other/Custom

? How do you want to manage tasks?
  ❯ Simple JSON file (recommended for solo projects)
    Beads CLI (advanced, better for teams)

? Do you have an AI harness configured?
  ✓ Claude Code detected
  ✓ Codex detected

Creating .cub/ directory structure...
  ✓ .cub/config.json
  ✓ .cub/prompt.md
  ✓ .cub/agent.md (customize this with your build commands)
  ✓ .cub/progress.md
  ✓ .cub/tasks.json (with starter task)
  ✓ CLAUDE.md → .cub/agent.md
  ✓ Updated .gitignore

Done! Your project is ready.

Next steps:
  1. Edit .cub/agent.md with your build/test commands
  2. Add tasks: cub task add "Description" or edit .cub/tasks.json
  3. Run: cub run --once

For help: cub --help or cub doctor
```

#### 3.2 Smart Detection

Auto-detect project characteristics:

```bash
detect_project_type() {
  if [[ -f "package.json" ]]; then
    if grep -q "next" package.json; then
      echo "nextjs"
    elif grep -q "react" package.json; then
      echo "react"
    else
      echo "node"
    fi
  elif [[ -f "requirements.txt" ]] || [[ -f "pyproject.toml" ]]; then
    echo "python"
  elif [[ -f "go.mod" ]]; then
    echo "go"
  elif [[ -f "Cargo.toml" ]]; then
    echo "rust"
  else
    echo "generic"
  fi
}

generate_agent_md() {
  local project_type=$1

  case "$project_type" in
    nextjs|react|node)
      cat <<'EOF'
# Agent Instructions

## Tech Stack
- Node.js / TypeScript
- [Framework details]

## Development
npm install
npm run dev

## Feedback Loops
npm run typecheck    # Type checking
npm test             # Tests
npm run lint         # Linting
npm run build        # Build
EOF
      ;;
    python)
      cat <<'EOF'
# Agent Instructions

## Tech Stack
- Python 3.x
- [Framework details]

## Development
pip install -r requirements.txt
python main.py

## Feedback Loops
mypy .               # Type checking
pytest               # Tests
ruff check .         # Linting
EOF
      ;;
    # ... other types
  esac
}
```

#### 3.3 Quick Mode

Non-interactive mode with sensible defaults:

```bash
# Quick init with all defaults
cub init --quick

# Quick init with options
cub init --quick --backend beads --type nextjs
```

### 4. Documentation Improvements

#### 4.1 Contextual Help

Every file cub creates includes helpful comments:

```markdown
<!-- .cub/agent.md -->
<!--
  AGENT INSTRUCTIONS
  ==================
  This file tells the AI how to build and test your project.
  The AI reads this before each task.

  YOU SHOULD EDIT THIS FILE to match your project.

  Key sections:
  - Tech Stack: Languages, frameworks, key dependencies
  - Development: How to run the project locally
  - Feedback Loops: Commands to validate changes (tests, lint, build)

  Tips:
  - Be specific about commands that must pass
  - Include common gotchas the AI should know about
  - Update this as you learn new things about your project
-->

# Agent Instructions
...
```

#### 4.2 In-Project Quick Reference

Create `.cub/README.md` during init:

```markdown
# Cub Project Files

This directory contains cub configuration and runtime data.

## Files You Can Edit

| File | Purpose | Edit? |
|------|---------|-------|
| `agent.md` | Build/test instructions | Yes - customize for your project |
| `prompt.md` | System prompt | Rarely - defaults work well |
| `config.json` | Project settings | Yes - override global defaults |
| `guardrails.md` | Lessons learned | Add manually, AI also appends |

## Files Managed by Cub

| File | Purpose |
|------|---------|
| `progress.md` | AI appends learnings here |
| `fix_plan.md` | AI tracks discovered issues |
| `tasks.json` | Task backlog |
| `runs/` | Execution history |

## Common Commands

```bash
cub run           # Start autonomous loop
cub run --once    # Single iteration
cub status        # Show progress
cub doctor        # Check setup
```

## Getting Help

- `cub --help` - Command reference
- `cub doctor` - Diagnose issues
- Docs: https://github.com/lavallee/cub
```

#### 4.3 Doctor Command Enhancement

Comprehensive health check:

```bash
$ cub doctor

Cub Health Check
================

System:
  ✓ bash 5.2.26
  ✓ jq 1.7
  ✓ git 2.43.0

Harnesses:
  ✓ claude (Claude Code 1.2.3)
  ○ codex (not installed)
  ○ gemini (not installed)

Global Config:
  ✓ ~/.config/cub/config.json exists
  ✓ ~/.config/cub/hooks/ exists
  ✓ ~/.local/share/cub/logs/ exists

Project (/Users/me/my-project):
  ✓ .cub/ directory exists
  ✓ .cub/config.json valid JSON
  ✓ .cub/agent.md exists
  ✓ .cub/prompt.md exists
  ✓ .cub/tasks.json valid (3 tasks: 1 open, 2 closed)
  ✓ CLAUDE.md symlink valid
  ✓ .gitignore includes .cub patterns

Recommendations:
  ○ Consider adding build commands to .cub/agent.md
  ○ No hooks configured - see examples/hooks/

Overall: ✓ Ready to run
```

### 5. Migration Path

For existing projects using the old file layout:

```bash
$ cub migrate-layout

Migrating to new .cub/ layout...

Found files to migrate:
  PROMPT.md → .cub/prompt.md
  AGENT.md → .cub/agent.md
  progress.txt → .cub/progress.md
  fix_plan.md → .cub/fix_plan.md
  prd.json → .cub/tasks.json
  .cub.json → .cub/config.json

? Proceed with migration? [Y/n] y

Migrating...
  ✓ Created .cub/ structure
  ✓ Moved PROMPT.md → .cub/prompt.md
  ✓ Moved AGENT.md → .cub/agent.md
  ✓ Created CLAUDE.md symlink
  ✓ Updated AGENTS.md symlink
  ✓ Merged progress.txt and @progress.txt → .cub/progress.md
  ✓ Moved fix_plan.md → .cub/fix_plan.md
  ✓ Moved prd.json → .cub/tasks.json
  ✓ Moved .cub.json → .cub/config.json
  ✓ Updated .gitignore

Migration complete!

Note: Old files have been moved, not deleted.
Run 'git status' to review changes.
```

### 6. First-Run Experience

After `cub init`, the first `cub run` should be welcoming:

```bash
$ cub run

╭──────────────────────────────────────────╮
│  Welcome to your first Cub run!          │
│                                          │
│  Session: fox-20260113-143022            │
│  Harness: claude                         │
│  Tasks:   1 ready                        │
╰──────────────────────────────────────────╯

Starting task: proj-init "Project initialization"

Tip: Use --stream to watch the AI work in real-time
     Use --debug for verbose output

...
```

---

## Configuration

New configuration options for onboarding features:

```json
{
  "init": {
    "template": "auto",
    "interactive": true,
    "create_symlinks": true
  },
  "doctor": {
    "check_harnesses": true,
    "check_hooks": true,
    "suggest_improvements": true
  }
}
```

---

## CLI Interface

### New Commands

```bash
# Installation verification
cub doctor                  # Full health check

# Migration
cub migrate-layout          # Migrate to .cub/ organization
cub migrate-layout --dry-run

# Enhanced init
cub init                    # Interactive mode
cub init --quick            # Non-interactive with defaults
cub init --type nextjs      # Pre-configured for project type
cub init --template minimal # Minimal files
```

### Updated Commands

```bash
# Task management (tasks now in .cub/tasks.json)
cub task add "Description"    # Add task to .cub/tasks.json
cub task list                 # List tasks
cub status                    # Show summary (same as before)
```

---

## Acceptance Criteria

### Phase 1: File Organization
- [ ] Move cub-managed files to `.cub/`
- [ ] Create symlinks for harness compatibility
- [ ] Update all file references in codebase
- [ ] Migration script for existing projects
- [ ] Update .gitignore patterns

### Phase 2: Enhanced Init
- [ ] Interactive mode with project type detection
- [ ] Project-type-specific templates
- [ ] Quick mode for non-interactive use
- [ ] Contextual help in generated files
- [ ] `.cub/README.md` generation

### Phase 3: Doctor Command
- [ ] System requirements check
- [ ] Harness detection and version display
- [ ] Config validation
- [ ] Project structure validation
- [ ] Recommendations engine

### Phase 4: Documentation
- [ ] Quick-start guide (separate from README)
- [ ] In-file contextual comments
- [ ] Video/GIF walkthrough
- [ ] Common issues troubleshooting

---

## Migration Strategy

### Backward Compatibility

During transition, cub should support both layouts:

```bash
detect_layout() {
  if [[ -f ".cub/prompt.md" ]]; then
    echo "new"
  elif [[ -f "PROMPT.md" ]]; then
    echo "legacy"
  else
    echo "none"
  fi
}

get_prompt_file() {
  case "$(detect_layout)" in
    new)    echo ".cub/prompt.md" ;;
    legacy) echo "PROMPT.md" ;;
    none)   echo "" ;;
  esac
}
```

### Deprecation Timeline

1. **v1.x**: Support both layouts, prefer new
2. **v2.0**: Warn on legacy layout
3. **v2.1**: Require migration or `--legacy` flag
4. **v3.0**: Remove legacy support

---

## Future Enhancements

- **Project templates repository**: `cub init --template github:user/template`
- **Team onboarding**: `cub team add user@example.com`
- **Cub Cloud**: Hosted dashboard for team visibility
- **VS Code extension**: Sidebar with task status, quick actions
- **Shell completion**: Tab completion for all commands

---

## Appendix: Full Directory Structure

### After `cub init` (new project)

```
my-project/
├── .cub/
│   ├── README.md              # Quick reference for .cub/ contents
│   ├── config.json            # Project config (optional)
│   ├── prompt.md              # System prompt
│   ├── agent.md               # Agent instructions
│   ├── guardrails.md          # Lessons learned
│   ├── progress.md            # Session learnings
│   ├── fix_plan.md            # Discovered issues
│   ├── tasks.json             # Task backlog
│   └── hooks/
│       ├── pre-loop.d/
│       ├── pre-task.d/
│       ├── post-task.d/
│       ├── on-error.d/
│       └── post-loop.d/
├── specs/                     # User specifications
├── CLAUDE.md → .cub/agent.md  # Symlink for Claude Code
├── AGENTS.md → .cub/agent.md  # Symlink for Codex
└── .gitignore                 # Updated with .cub patterns
```

### After `cub run` (with artifacts)

```
my-project/
├── .cub/
│   ├── ... (as above)
│   └── runs/
│       └── fox-20260113-143022/
│           ├── run.json
│           └── tasks/
│               └── proj-abc/
│                   ├── task.json
│                   ├── rendered_prompt.md
│                   ├── harness_output.log
│                   ├── git_state.json
│                   ├── changes.patch
│                   └── summary.md
└── ...
```

### Global Structure

```
~/.config/cub/
├── config.json                # Global defaults
└── hooks/
    ├── pre-loop.d/
    ├── pre-task.d/
    ├── post-task.d/
    ├── on-error.d/
    └── post-loop.d/

~/.local/share/cub/
└── logs/
    └── {project}/
        └── {session}.jsonl

~/.cache/cub/
└── ... (future cache data)
```

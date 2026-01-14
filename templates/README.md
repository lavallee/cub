# Project Setup Guide

<!--
WHAT IS THIS FILE?
This file is a quick reference guide for your project's cub configuration. It shows what each file in .cub/ does,
which files you should edit, and common commands you'll use.

WHAT TO EDIT:
- Update the "Files in .cub/" table below with your project-specific information
- Add project-specific commands to the "Common Commands" section
- Update links if your documentation or specs are in different locations

WHAT NOT TO ADD:
- Don't add build instructions here (that belongs in agent.md)
- Don't add detailed architecture docs here (see architecture documentation in docs/)
- Don't add deployment/operations info (that's in docs/ or team wikis)

FILE PURPOSES:
- .cub/README.md (this file): Quick reference for cub files and commands
- .cub/agent.md: How to build, test, and run the project
- .cub/prompt.md: System prompt for the AI assistant working on this project
- .cub/progress.txt: Learnings and discoveries from development sessions
- .cub/fix_plan.md: Known issues, bugs, and technical debt

WHEN TO UPDATE:
- Update this file when you discover new cub commands you use regularly
- Update file descriptions if the purpose of any .cub file changes
- Add project-specific commands as you learn them
-->

## Files in .cub/

| File | Status | Purpose |
|------|--------|---------|
| **README.md** | 📖 Reference | This file - quick start and file guide |
| **agent.md** | ✏️ Editable | Build/run instructions for your project type |
| **prompt.md** | ✏️ Editable | System prompt for Claude Code or other harnesses |
| **progress.txt** | ✏️ Editable | Session learnings, discoveries, and gotchas |
| **fix_plan.md** | ✏️ Editable | Known issues, bugs, and technical debt tracker |

**Key:**
- ✏️ **Editable** - Update these files as you learn new things
- 🔄 **Managed** - Cub manages these (you shouldn't edit them directly)
- 📖 **Reference** - Quick lookup files

## Quick Start

### Essential Commands

```bash
# Show project status
cub status

# Start the autonomous loop
cub

# Run single iteration
cub --once

# Show ready tasks
cub --ready

# Create a new task
bd create "Task description"

# View a task
bd show <task-id>

# Update task status
bd update <task-id> --status in_progress
bd close <task-id>
```

### Development Commands

```bash
# Edit build instructions
$EDITOR .cub/agent.md

# Edit system prompt
$EDITOR .cub/prompt.md

# Add a learning/gotcha
$EDITOR .cub/progress.txt

# Track an issue
$EDITOR .cub/fix_plan.md
```

## When to Edit Each File

### agent.md
Edit this file whenever you discover:
- New build commands or build steps
- Test/lint commands that work for your project
- Gotchas that would surprise a new contributor
- Project structure changes
- New dependencies or prerequisites

### prompt.md
Edit this file to:
- Add context about the codebase
- Document critical architectural patterns
- Include links to important docs
- Add team conventions or standards

### progress.txt
Add entries for:
- Surprising behaviors in the codebase
- Performance characteristics
- Workarounds that fixed problems
- Build/test system quirks
- Commands that helped solve issues

### fix_plan.md
Add issues for:
- Bugs discovered during development
- Technical debt and refactoring opportunities
- Performance improvements
- Test coverage gaps

## File Status

```
.cub/
├── README.md           ← You are here
├── agent.md            ← Edit with project setup info
├── prompt.md           ← Edit with context & patterns
├── progress.txt        ← Add learnings as you work
└── fix_plan.md         ← Track issues & improvements
```

## Next Steps

1. **Review agent.md** - Check that build/test commands are correct for your project
2. **Update prompt.md** - Add context about your codebase
3. **Use progress.txt** - Add learnings as you discover them
4. **Track issues in fix_plan.md** - Document bugs and technical debt
5. **Run `cub --ready`** - See what tasks are ready to work on

## Learn More

- **Full agent documentation**: See `.cub/agent.md`
- **Build/test commands**: Check `.cub/agent.md` → Feedback Loops section
- **Code patterns**: Check `.cub/prompt.md` and project documentation
- **Known issues**: Check `.cub/fix_plan.md`
- **Session learnings**: Check `.cub/progress.txt`

## Tips for Agents

When an AI coding assistant works on this project:
1. Read `.cub/agent.md` first for build/test instructions
2. Check `.cub/progress.txt` for known gotchas
3. Review `.cub/fix_plan.md` before making changes
4. Update these files as you learn new things
5. Use `bd list` to see open tasks
6. Update task status with `bd update <id> --status in_progress` when starting work

---

**💡 Tip:** This file is committed to git, so all your team members and AI assistants will see it.
Keep it up-to-date with important project information!

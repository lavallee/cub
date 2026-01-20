# .cub/ Quick Reference Guide

<!--
╔══════════════════════════════════════════════════════════════════╗
║  WHAT IS THIS FILE?                                              ║
╚══════════════════════════════════════════════════════════════════╝

This is a quick reference guide for the .cub/ directory.
It shows what each file does, which ones you should edit, and how to use cub effectively.

The .cub/ directory is where cub stores project-specific instructions and state.
All files here are committed to git and shared across your team and sessions.

╔══════════════════════════════════════════════════════════════════╗
║  WHAT TO EDIT                                                    ║
╚══════════════════════════════════════════════════════════════════╝

1. Update the "Files in .cub/" table below if descriptions need updates
2. Add project-specific commands to "Quick Start" → "Development Commands"
3. Update links in "Learn More" if your docs/specs are in different locations
4. Keep this file focused on cub-related tasks (not general project docs)

WHAT TO EDIT ELSEWHERE (NOT HERE):
- Build/test commands → Edit agent.md instead
- Architecture documentation → Create docs/architecture.md
- Deployment/operations → Create docs/operations.md or wiki
- API documentation → Create docs/api.md or use OpenAPI spec
- User guide/README → Create main README.md (root project level)

WHEN TO UPDATE THIS FILE:
- When you change what any .cub file is used for
- When you discover new cub commands worth documenting
- When you add or remove .cub files
- Quarterly review to remove stale information

WHY THIS FILE EXISTS:
- New team members need to understand .cub/ structure
- Developers context-switch between projects and need quick reminders
- This file is the "home page" for cub-related information
- It prevents hunting through documentation to find basic info
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
cub run

# Run single iteration
cub run --once

# Show ready tasks
cub run --ready
```

> **Task Management:** Add your project's task commands here.
> The task backend will provide closure instructions in each task prompt.

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
5. Follow task management instructions provided in each task prompt

---

**💡 Tip:** This file is committed to git, so all your team members and AI assistants will see it.
Keep it up-to-date with important project information!

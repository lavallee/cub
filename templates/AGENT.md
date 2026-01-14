# Agent Instructions

<!--
WHAT IS THIS FILE?
This file is your operational manual for the project. Claude Code (the AI assistant) reads this file
when starting work to understand how to build, test, and contribute to your project.

WHAT TO EDIT:
- Fill in the template sections below with YOUR project-specific information
- Update this file whenever you discover new build steps, test commands, or gotchas
- This file is committed to git, so it's shared with your team and preserved across sessions

TIPS FOR AGENTS:
- Keep sections concise and focused on actionable information
- List exact commands (npm run dev, pytest, etc.) - not generic examples
- Document "gotchas" that would surprise a new contributor
- If a step isn't applicable (e.g., no type checking), delete the section rather than leaving it empty
-->

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

<!--
EDIT THIS: Write 2-3 sentences explaining what this project does and who uses it.
Example: "MyApp is a React web app that helps teams track sprints and velocity metrics."
-->

## Tech Stack

<!--
EDIT THIS: List the languages, frameworks, and key dependencies.
Format as a bulleted list for readability.
Example:
- Language: JavaScript/TypeScript
- Framework: Next.js 14
- Database: PostgreSQL with Prisma ORM
- Testing: Jest + React Testing Library
-->

## Development Setup

```bash
# EDIT THIS: Replace with your actual setup steps.
# Keep these as copy-paste-ready commands.
# Include:
# 1. Prerequisites (Node 18+, Python 3.10, etc.)
# 2. Dependency installation
# 3. Environment configuration (if needed)
#
# Example:
# npm install
# cp .env.example .env
# npm run db:migrate
```

## Running the Project

```bash
# EDIT THIS: Replace with actual run commands for your project.
# Include both development and production modes if applicable.
#
# Example:
# npm run dev
# Open http://localhost:3000
```

## Feedback Loops

Run these before committing. If a command doesn't exist, delete that section.

```bash
# Type checking (if applicable)
# npx tsc --noEmit / mypy . / etc.

# Tests (required)
# npm test / bun test / pytest / etc.

# Linting (if applicable)
# npm run lint / eslint . / ruff check . / etc.

# Build (if applicable)
# npm run build / bun build / etc.
```

## Project Structure

```
# EDIT THIS: Update the structure to match your project layout.
# Include key directories and what they contain.
#
# Example:
├── src/           # Source code
├── specs/         # Detailed specifications for ongoing work
├── tests/         # Test files
├── .cub/          # Cub working directory (auto-generated)
│   ├── prompt.md  # System prompt for this project
│   ├── agent.md   # This file (your project guide)
│   ├── progress.txt # Learnings from previous sessions
│   └── fix_plan.md  # Known issues and fixes
├── prd.json       # Task backlog (or .beads/issues.jsonl if using beads)
└── README.md      # User-facing documentation
```

## Key Files

<!--
EDIT THIS: List the most important files an agent should know about when working on this project.
Include path and brief description.

Example:
- src/api/routes.ts - All HTTP endpoints
- src/db/migrations/ - Database schema changes
- lib/utils.ts - Shared utility functions
- tests/integration/ - End-to-end tests

This helps agents quickly understand the codebase geography.
-->

## Gotchas & Learnings

<!--
EDIT THIS: Document things that are NOT obvious from reading the code.
These are discoveries from actual development that prevent common mistakes.

Format: One bullet point per gotcha, with brief explanation.

Examples:
- The database migrations must run in order; manual reordering causes failures
- Tests must run sequentially (add --no-parallel flag) due to shared test database
- Webpack rebuild hangs if you have >500 chunks; use dynamic imports to split them
- The API requires Bearer tokens with format "Bearer {uuid}" - other formats fail silently
- Gemini CLI doesn't support streaming on versions <0.1.9; upgrade if tests fail

Update this section as you work!
-->

## Common Commands

<!--
EDIT THIS: List commands you discover while working that are useful for repeated tasks.
Include the exact command and what it does.

Format: One command per line with description

Examples:
- npm run dev:watch - Run dev server with auto-reload for template changes
- npm run db:reset - Drop and recreate test database (for local testing)
- npm run bundle:analyze - Show webpack bundle breakdown
- bd list --status open - Show all open tasks in the backlog

This helps future sessions get started faster!
-->

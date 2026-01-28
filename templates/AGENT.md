# Agent Instructions

<!--
╔══════════════════════════════════════════════════════════════════╗
║  WHAT IS THIS FILE?                                              ║
╚══════════════════════════════════════════════════════════════════╝

This file is your operational manual for the project. Claude Code (the AI assistant) reads this
file when starting work to understand how to build, test, and contribute to your project.

Think of it as a "quick reference guide" that helps any developer or AI assistant understand:
- How to get the project running locally
- What commands run the tests, linter, type checker, and build
- Common gotchas and surprising behaviors
- Project-specific patterns and conventions

This file is committed to git and shared across your team and all coding sessions.

╔══════════════════════════════════════════════════════════════════╗
║  WHAT TO EDIT                                                    ║
╚══════════════════════════════════════════════════════════════════╝

1. Fill in all EDIT THIS sections below with YOUR project-specific information
2. Update this file whenever you discover:
   - New build steps or build system quirks
   - Test commands that work (or don't work) for your setup
   - Environment variables or dependencies
   - Surprising behaviors or performance characteristics
3. Delete empty sections (e.g., if no type checking, delete that section)
4. Keep commands copy-paste ready - they should work exactly as shown

╔══════════════════════════════════════════════════════════════════╗
║  HOW TO USE THIS FILE                                            ║
╚══════════════════════════════════════════════════════════════════╝

- Read the "Project Overview" section first to understand what you're working on
- Check "Development Setup" before running anything for the first time
- Use "Running the Project" when you need to start development
- Review "Feedback Loops" before committing - these are your quality gates
- Check "Gotchas & Learnings" if something breaks unexpectedly
- See "Key Files" when you need to understand the codebase geography

╔══════════════════════════════════════════════════════════════════╗
║  TIPS FOR KEEPING THIS FILE USEFUL                               ║
╚══════════════════════════════════════════════════════════════════╝

- List EXACT commands with all necessary flags (npm run dev --port 3001, not npm dev)
- Include prerequisites (Node 16+, Python 3.10, etc.)
- Document "gotchas" that would surprise a new contributor
- Explain WHY a step is needed if it's not obvious
- Keep sections concise - verbose documentation isn't helpful
- Remove outdated information immediately
- If something breaks, add a workaround or link to the fix
-->

This file contains instructions for building and running the project.
Update this file as you learn new things about the codebase.

## Project Overview

<!--
📝 WHAT TO EDIT: Write 2-3 sentences explaining what this project does.
- What problem does it solve?
- Who are the primary users?
- What's the main value proposition?

Example: "MyApp is a React web app that helps teams track sprints and velocity metrics.
It's used by 50+ engineering teams to improve planning accuracy."

Keep this section brief. Link to user docs/README.md for more details.
-->

## Tech Stack

<!--
📝 WHAT TO EDIT: List the languages, frameworks, and key dependencies.
Focus on technologies that matter for development and understanding the code.

Format as a bulleted list. Include version numbers if they matter.

Example:
- **Language**: JavaScript/TypeScript 5.2
- **Framework**: Next.js 14 (App Router)
- **Database**: PostgreSQL 14 with Prisma 5.7 ORM
- **Testing**: Jest 29 + React Testing Library 14
- **Package Manager**: pnpm 8
- **Deployment**: Docker + AWS ECS

💡 TIP: Include minimum versions if the code requires specific features.
For example, if you use ES2020 syntax, list "Node 14.18+" as a requirement.
-->

## Development Setup

```bash
# 📝 EDIT THIS SECTION: Replace with your actual setup steps.
# These commands should be copy-paste-ready and work for a fresh checkout.
#
# Include in order:
# 1. Prerequisites check (Node 18+, Python 3.10, Postgres, etc.)
# 2. Install dependencies
# 3. Set up environment files
# 4. Initialize database or other services
# 5. Verify setup worked
#
# Example (Next.js + PostgreSQL):
# Prerequisites: Node 18.17+, PostgreSQL 14+
# npm install
# cp .env.example .env.local
# npm run db:migrate
# npm run db:seed
# npm run dev      # Should print "Ready on http://localhost:3000"
```

<!-- 💡 TIPS:
- Run these commands yourself to verify they work before committing
- If a step fails, include the error and solution
- Include any special setup for CI/CD or Docker
- If setup takes >5 minutes, explain why
-->

## Running the Project

```bash
# 📝 EDIT THIS SECTION: Replace with actual run commands for your project.
#
# Include:
# 1. Development mode (auto-reload, debug tools, etc.)
# 2. Production mode (if different from dev)
# 3. How to access it (URL, ports, etc.)
# 4. Any environment-specific setup
#
# Example (Next.js):
# npm run dev                # Development server with hot reload
# Open http://localhost:3000
#
# Example (Python + Flask):
# export FLASK_ENV=development
# export FLASK_APP=app.py
# flask run                  # Development server
# Open http://localhost:5000
```

<!-- 💡 TIPS:
- Include the exact port/URL where the app will be accessible
- Note if the app auto-reloads or if manual restart is needed
- Include any special environment variables needed
- Mention if authentication is required to access (test users, etc.)
-->

## Feedback Loops

These are your quality gates. Run these BEFORE committing to catch problems early.
If a command doesn't exist for your project, delete that section entirely.

```bash
# 📝 TYPE CHECKING (if applicable - TypeScript, Python, etc.)
# This catches type errors before runtime
# Examples:
# npx tsc --noEmit              # TypeScript
# mypy .                        # Python
# cargo check                   # Rust
# go vet ./...                  # Go

# 🧪 TESTS (required - run these before every commit)
# This catches logic errors and regressions
# Examples:
# npm test                      # Node/JavaScript
# pytest                        # Python
# cargo test                    # Rust
# bats tests/*.bats            # Bash

# 🎨 LINTING (if applicable - code style/quality)
# This catches style issues and common mistakes
# Examples:
# npm run lint                  # JavaScript/TypeScript
# ruff check .                  # Python
# cargo clippy                  # Rust
# shellcheck *.sh               # Bash

# 🔨 BUILD (if applicable - compiles/bundles the project)
# This catches compilation errors
# Examples:
# npm run build                 # JavaScript/TypeScript
# cargo build --release        # Rust
# go build ./cmd/...           # Go
# bun build                     # Bun
```

<!-- ⚠️ IMPORTANT:
- Run ALL feedback loops before committing
- Fix errors in this order: type → lint → tests → build
- If these commands fail, DON'T commit - the code isn't ready
- If you're adding new code, write tests at the same time
-->

## Project Structure

```
# 📝 EDIT THIS SECTION: Update to match your actual project layout.
# List key directories and briefly explain what they contain.
# This helps agents understand the codebase geography quickly.
#
# Example (full-stack app):
.
├── src/                  # Application source code
│   ├── pages/            # Web pages / routes
│   ├── components/       # Reusable React components
│   ├── api/              # Backend API endpoints
│   ├── lib/              # Shared utilities
│   └── styles/           # CSS and styling
├── tests/                # Test files (mirrors src/ structure)
├── docs/                 # Architecture, design docs, runbooks
├── specs/                # Task specifications and detailed plans
├── .cub/                 # Cub control files (auto-managed)
│   ├── agent.md          # This file (project instructions)
│   ├── prompt.md         # System prompt for AI assistants
│   └── fix_plan.md       # Known issues and technical debt
├── .env.example          # Environment template (copy to .env)
├── .gitignore            # Git ignore patterns
├── package.json          # Dependencies and scripts
└── README.md             # User-facing documentation

# 💡 TIP: Include only directories that matter for development.
# Skip node_modules/, build/, .git/, etc.
# If your project is small, a simpler structure is fine.
```

## Key Files

<!--
📝 WHAT TO EDIT: List the most important files agents should know about.
Include the file path and a brief description of what it does.

Format: One file per line with description

Example:
- src/api/routes.ts - All HTTP endpoints and route definitions
- src/db/migrations/ - Database schema changes (run these in order)
- src/db/schema.ts - Shared database type definitions
- src/lib/auth.ts - Authentication helpers and token validation
- src/lib/utils.ts - Shared utility functions used throughout the app
- tests/integration/ - End-to-end tests that test real API endpoints
- .env.example - Template for environment variables

Why include this section?
- Agents need to understand where important code lives
- It speeds up finding bugs and understanding the architecture
- It's a quick reference when learning the codebase

💡 TIPS:
- Focus on files agents will MODIFY, not read-only utility files
- Include files that are frequently changed or critical to functionality
- Add line counts if the file is large (src/App.tsx ~500 lines)
- Note if a file is auto-generated (don't edit!) or read-only
-->

## Gotchas & Learnings

<!--
📝 WHAT TO EDIT: Document things that are NOT obvious from reading the code.
These are discoveries from actual development that prevent bugs and save time.

When to add a gotcha:
- Something breaks unexpectedly (write down the solution!)
- A command has weird side effects or requires special flags
- A tool or library behaves differently than documented
- There's a fragile process that breaks easily
- Dependencies have version incompatibilities
- Tests are slow or flaky - document workarounds

Format: One bullet per gotcha, with brief explanation and workaround if applicable

Examples (good gotchas):
- Database migrations must run in order; manual reordering causes "table already exists" errors
  Workaround: Always run `npm run db:migrate` instead of applying migrations manually
- Tests must run sequentially with --no-parallel flag due to shared test database
  Workaround: npm test runs sequential by default, but npm run test:parallel will fail
- TypeScript build caches stale types; delete .tsbuildinfo if types don't update
  Workaround: npm run clean && npm run build
- Webpack rebuild hangs if >500 chunks; breaks the dev server
  Workaround: Use dynamic imports in components to code-split automatically
- The API requires Bearer tokens with exact format "Bearer {uuid}"; other formats fail silently
  Workaround: Always use the formatToken() helper in lib/auth.ts

Examples (things that DON'T help - skip these):
- The code uses async/await (obvious from reading it)
- There are unit tests in tests/ (obvious from structure)
- ESLint is configured (see package.json)

💡 TIPS:
- Update this section as you work - don't wait until the end
- Include the file/line number if it helps: "src/api/middleware.ts:42 has a race condition"
- Link to related issues or PRs if available
- If you find a workaround, document it here so others don't waste time
-->

## Common Commands

<!--
📝 WHAT TO EDIT: List commands you discover while working that are useful for repeated tasks.
Include the exact command with all necessary flags and a brief description.

Format: One command per line:
  command-name - What it does and when you'd use it

Examples (JavaScript/Node):
- npm run dev:watch - Dev server with auto-reload (useful for testing theme changes)
- npm run db:reset - Drop and recreate test database (run before integration tests)
- npm run bundle:analyze - Show webpack bundle breakdown (identify code splitting opportunities)
- npm run type-check -- --watch - Type checking in watch mode (fast feedback while coding)

Examples (Python):
- pytest -k auth - Run only auth tests (fast iteration on auth code)
- pytest --lf - Re-run last failed tests (quick regression testing)
- python -m flask shell - Interactive Python shell with app context (debug queries)

Examples (Task Management - add your project's task commands here):
- List open tasks
- Show task details
- Mark task complete
- Create new task

When to add a command:
- It's something you run frequently (multiple times per week)
- It's hard to remember the exact syntax or flags
- It's faster than the obvious way (e.g., pytest -k is faster than searching)
- It's a useful shortcut that saves time

💡 TIPS:
- Test the command to make sure it works before documenting
- Include the purpose/use case, not just the command
- Group related commands together
- Update this as you discover useful shortcuts
- Remove commands that become outdated
-->

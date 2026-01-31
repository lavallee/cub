# Agent Instructions

This file contains instructions for building, running, and developing this project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of your project -->

## Tech Stack

- **Language**:
- **Framework**:
- **Database**:

## Development Setup

```bash
# Setup commands here
```

## Running the Project

```bash
# Run commands here
```

## Feedback Loops

Run these before committing:

```bash
# Tests
# Type checking
# Linting
```

## Task Management

This project uses [cub](https://github.com/lavallee/cub) for task management.

### Finding Work

```bash
cub task ready                    # List tasks ready to work on
cub task list --status open       # All open tasks
cub task show <id>                # Task details
cub suggest                       # Smart suggestions for next action
cub status                        # Project progress overview
```

### Working on Tasks

```bash
cub task claim <id>               # Claim a task (mark in-progress)
cub run --task <id>               # Run autonomous loop for a task
cub run --epic <id>               # Run all tasks in an epic
cub run --once                    # Single iteration
```

### Completing Tasks

```bash
cub task close <id> -r "reason"   # Close with reason
```

### Planning

```bash
cub capture "idea"                # Quick capture
cub spec                          # Create feature spec
cub plan run                      # Plan implementation
cub stage <plan-slug>             # Import tasks from plan
```

## Git Workflow

- Feature branches per epic: `cub branch <epic-id>`
- Pull requests: `cub pr <epic-id>`
- Merge: `cub merge <pr-number>`

## Gotchas & Learnings

<!-- Add project-specific conventions, pitfalls, and decisions here -->

## Common Commands

```bash
# Add frequently used commands here
```

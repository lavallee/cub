# Cub Quick Start

Get started with Cub in 5 minutes. For detailed docs, see [README.md](README.md).

## Prerequisites (1 min)

You need:
- **Bash 3.2+** (check with `bash --version`)
- **jq** (install: `brew install jq` or `apt-get install jq`)
- **Claude Code CLI** (install from [github.com/anthropics/claude-code](https://github.com/anthropics/claude-code))

Optional:
- **beads CLI** for advanced task management (`brew install steveyegge/beads/bd`)

## Install Cub (1 min)

```bash
# Clone to a tools directory
git clone https://github.com/lavallee/cub ~/tools/cub

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$PATH:$HOME/tools/cub"

# Or create symlinks
ln -s ~/tools/cub/cub /usr/local/bin/cub
ln -s ~/tools/cub/cub-init /usr/local/bin/cub-init
```

Verify installation:
```bash
cub --version
```

## Global Setup (1 min)

First time only - initialize Cub on your system:

```bash
cub init --global
```

This creates:
- `~/.config/cub/config.json` - Global configuration
- `~/.local/share/cub/logs/` - Log storage
- `~/.cache/cub/` - Cache directory

## Initialize Your Project (1 min)

In your project directory:

```bash
cd my-project
cub init
```

This creates:
- `prd.json` - Task backlog (or use `bd init` for beads)
- `.cub/` - Runtime directory
- `AGENT.md` - Build and run instructions for the AI
- `PROMPT.md` - System instructions (edit as needed)
- `progress.txt` - Agent's learning notes

## Add Your First Tasks (1 min)

### Option A: Using prd.json

Edit `prd.json` and add a task:

```json
{
  "projectName": "my-project",
  "prefix": "proj",
  "tasks": [
    {
      "id": "proj-001",
      "type": "task",
      "title": "Implement user login",
      "description": "Add login form and authentication",
      "priority": "P1",
      "status": "open"
    }
  ]
}
```

### Option B: Using Beads

```bash
bd init          # Initialize beads
bd create "Implement user login" --type task --priority 1
```

## Run Cub (1 min)

```bash
# Run the autonomous loop
cub run

# Or run a single iteration (test mode)
cub run --once

# Or with debug output
cub run --debug --once
```

Cub will:
1. Pick the highest-priority open task
2. Generate a prompt with task details
3. Run Claude Code to implement the task
4. Create a commit when done
5. Move to the next task
6. Repeat until all tasks are closed

## Check Status

```bash
# View task progress
cub status

# View a specific task
cub explain proj-001

# View artifacts from a run
cub artifacts
```

## Common Commands

| Command | Purpose |
|---------|---------|
| `cub run` | Run the main loop |
| `cub run --once` | Single iteration (test mode) |
| `cub status` | Show task progress |
| `cub explain <id>` | Show task details |
| `cub artifacts` | List task outputs |
| `cub doctor` | Diagnose issues |

## Beads Commands (if using beads)

```bash
# List all tasks
bd list

# Show open tasks
bd list --status open

# View task details
bd show <task-id>

# Create a task
bd create "Task description"

# Mark task complete
bd close <task-id>

# Add labels
bd label add <task-id> phase-1
```

## Tips

1. **Edit AGENT.md first** - Add build/test/lint commands so the AI knows how to verify work
2. **Keep tasks small** - One task = one context window
3. **Write good descriptions** - Use acceptance criteria for clarity
4. **Check progress.txt** - Agent appends learnings after each task
5. **Use specs/** - Create detailed specs for complex features
6. **Review commits** - Each task creates a git commit you can review

## Next Steps

- Read [README.md](README.md) for comprehensive documentation
- Check [UPGRADING.md](UPGRADING.md) if upgrading from an older version
- Look at [docs/CONFIG.md](docs/CONFIG.md) for advanced configuration
- Review [docs/HARNESSES.md](docs/HARNESSES.md) for AI harness details

## Getting Help

- `cub --help` - Show help
- `cub init --help` - Help for init subcommand
- `cub run --help` - Help for run subcommand
- Open an issue: [github.com/lavallee/cub/issues](https://github.com/lavallee/cub/issues)

---
title: Cub Documentation
description: Work ahead of your AI coding agents, then let them run autonomously. Complete documentation for getting started, configuration, and advanced usage.
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

# Cub

<p class="tagline">Work ahead of your AI agents</p>
<p class="subtitle">Turn your ideas into structured tasks, then let AI execute autonomously while you focus on what matters.</p>

<div class="install-box" markdown>
```bash
curl -LsSf https://docs.cub.tools/install.sh | bash
```
</div>

[Get Started](getting-started/quickstart.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/lavallee/cub){ .md-button }

</div>

---

## Get Running in Three Steps

<div class="feature-grid" markdown>

<div class="feature-card" markdown>

#### 1. Initialize

```bash
cub init --global
cd your-project && cub init
```

Set up your global config and project files.

</div>

<div class="feature-card" markdown>

#### 2. Prep Your Tasks

```bash
cub prep
```

Transform your ideas into structured, agent-ready tasks through guided refinement.

</div>

<div class="feature-card" markdown>

#### 3. Run the Loop

```bash
cub run
```

Let Cub execute tasks autonomously until complete or budget exhausted.

</div>

</div>

---

## The Two Main Events

<div class="workflow-grid" markdown>

<div class="workflow-card prep" markdown>

### Prep: Vision to Tasks

Go from a rough idea to structured, agent-sized tasks:

- **Triage** - Clarify requirements and goals
- **Architect** - Design the technical approach
- **Plan** - Break work into agent-sized chunks
- **Bootstrap** - Write tasks to your backend

```bash
cub prep                 # Full pipeline
cub triage && cub plan   # Or run stages individually
```

[Learn about Prep](guide/prep-pipeline/index.md){ .md-button }

</div>

<div class="workflow-card run" markdown>

### Run: Tasks to Code

Execute tasks with the AI harness of your choice:

- **Autonomous loop** - Picks and executes tasks
- **Multi-harness** - Claude, Codex, Gemini, OpenCode
- **Smart routing** - Right model for each task
- **Budget tracking** - Stay within token limits

```bash
cub run                  # Run until complete
cub run --once           # Single iteration
cub run --stream         # Watch in real-time
```

[Learn about Run](guide/run-loop/index.md){ .md-button }

</div>

</div>

---

## Why Cub?

!!! tip "Finding the Balance"
    AI coding agents in 2026 are powerful. They can operate for hours, produce working code, run tests, and iterate toward production quality. But there's a gap between **too hands-on** (approving every tool call) and **too hands-off** (hoping for the best with vague instructions).

    Cub finds the middle ground. You invest time *before* code starts flying, then step back and let execution happen.

<div class="feature-grid" markdown>

<div class="feature-card" markdown>

#### Right Model for the Task

Route simple tasks to fast models, complex work to capable ones. Manage tokens as a resource.

</div>

<div class="feature-card" markdown>

#### Multi-Harness Flexibility

Claude Code, OpenAI Codex, Google Gemini, OpenCode. Use the right tool without vendor lock-in.

</div>

<div class="feature-card" markdown>

#### Deterministic Control

Task selection, retry logic, and state transitions run as traditional software, not LLM inference.

</div>

<div class="feature-card" markdown>

#### Budget Management

Track tokens across tasks with configurable limits and warnings. No runaway spending.

</div>

<div class="feature-card" markdown>

#### Git Workflow Integration

Branch per epic, commit per task. Clean state enforcement keeps your repo healthy.

</div>

<div class="feature-card" markdown>

#### Hooks System

Custom scripts at lifecycle points. Slack notifications, metrics, alerts - whatever you need.

</div>

</div>

---

## Documentation Sections

<div class="feature-grid" markdown>

<div class="feature-card" markdown>

#### [Getting Started](getting-started/index.md)

Installation, quick start guide, and core concepts to get you productive fast.

</div>

<div class="feature-card" markdown>

#### [User Guide](guide/index.md)

In-depth coverage of configuration, task management, the run loop, and advanced features.

</div>

<div class="feature-card" markdown>

#### [CLI Reference](cli/index.md)

Complete reference for all Cub commands with examples and options.

</div>

<div class="feature-card" markdown>

#### [Troubleshooting](troubleshooting/index.md)

Common issues, error reference, and frequently asked questions.

</div>

</div>

---

## Quick Links

| Topic | Description |
|-------|-------------|
| [Installation](getting-started/install.md) | Get Cub installed on your system |
| [Quick Start](getting-started/quickstart.md) | Start using Cub in 5 minutes |
| [Configuration](guide/configuration/index.md) | Customize Cub for your workflow |
| [Task Backends](guide/tasks/index.md) | Beads vs JSON task management |
| [AI Harnesses](guide/harnesses/index.md) | Claude, Codex, Gemini, OpenCode |
| [Hooks System](guide/hooks/index.md) | Extend Cub with custom scripts |
| [Contributing](contributing/index.md) | Help improve Cub |

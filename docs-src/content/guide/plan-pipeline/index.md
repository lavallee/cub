# Plan Flow

The plan flow transforms your ideas into structured, agent-ready tasks. It's a 3-stage planning process followed by staging to import tasks into your backend.

## What Plan Does

```mermaid
flowchart LR
    A[Spec] --> B[Orient]
    B --> C[Architect]
    C --> D[Itemize]
    D --> E[Stage]
    E --> F[Ready Tasks]

    style A fill:#FFC107
    style B fill:#FF9800
    style C fill:#FF5722
    style D fill:#E91E63
    style E fill:#9C27B0
    style F fill:#4CAF50,color:white
```

| Stage | Purpose | Output |
|-------|---------|--------|
| [Orient](orient.md) | Research and understand the problem | `orientation.md` |
| [Architect](architect.md) | Design technical approach | `architecture.md` |
| [Itemize](itemize.md) | Break into agent-sized tasks | `itemized-plan.md` |
| [Stage](stage.md) | Import tasks to backend | Tasks in Beads |

## Quick Start

Run the full planning pipeline with one command:

```bash
# From a spec file
cub plan run specs/researching/my-feature.md

# Or let cub auto-discover VISION.md, docs/PRD.md, etc.
cub plan run
```

This runs all three stages (orient, architect, itemize) in sequence. When complete, stage the plan to create tasks:

```bash
cub stage
```

## Creating Specs

Before planning, create a spec that describes your feature:

```bash
# Interactive interview mode
cub spec "user authentication"

# Or write a spec manually in specs/researching/
```

Specs are stored in `specs/` with subdirectories for each lifecycle stage:

```
specs/
├── researching/   # Active exploration
├── planned/       # Plan exists
├── staged/        # Tasks in backend
├── implementing/  # Active work
└── released/      # Shipped
```

## The Planning Pipeline

### Stage 1: Orient

Research and understand the problem space:

```bash
cub plan orient specs/researching/my-feature.md
```

- Analyzes your spec and existing codebase
- Identifies requirements and constraints
- Surfaces open questions and risks
- Outputs `plans/{slug}/orientation.md`

### Stage 2: Architect

Design the technical approach:

```bash
cub plan architect
```

- Proposes system structure and components
- Documents technology choices
- Creates implementation phases
- Outputs `plans/{slug}/architecture.md`

### Stage 3: Itemize

Break architecture into actionable tasks:

```bash
cub plan itemize
```

- Generates well-scoped epics and tasks
- Assigns priorities and estimates
- Creates beads-compatible IDs
- Outputs `plans/{slug}/itemized-plan.md`

### Stage 4: Stage

Import tasks into your backend:

```bash
cub stage
```

- Runs pre-flight checks (git, tools)
- Creates epics and tasks in beads
- Generates `.cub/prompt.md` and `.cub/agent.md`
- Moves spec from `planned/` to `staged/`

## Plan Directory Structure

Plans are stored in `plans/{slug}/`:

```
plans/my-feature/
├── plan.json          # Plan metadata
├── orientation.md     # Orient stage output
├── architecture.md    # Architect stage output
└── itemized-plan.md   # Itemize stage output
```

## Running Individual Stages

Run stages separately for more control:

```bash
cub plan orient my-feature.md --depth deep
cub plan architect --mindset production
cub plan itemize
cub stage --dry-run
```

## Managing Plans

List all plans:

```bash
cub plan list
cub plan list --verbose  # Show stage status
```

Continue an incomplete plan:

```bash
cub plan run --continue my-feature
```

## When to Use Plan vs Direct Task Creation

Use the plan flow when:

- Starting a new project or major feature
- You have a spec but need to clarify requirements
- You want AI-assisted decomposition into right-sized tasks
- You need technical design before implementation

Create tasks directly when:

- Adding a small feature or bug fix
- Tasks are already well-defined
- Quick experiments or prototypes

```bash
# Direct task creation with beads
bd create "Fix login bug" --type bugfix --priority 1
```

## Non-Interactive Mode

For CI/CD or automated workflows:

```bash
cub plan run specs/researching/my-feature.md --non-interactive
```

!!! warning "Best-Effort Mode"
    Non-interactive mode makes best-effort assumptions when details are missing. Review outputs carefully.

## Quick Reference

| Command | Description |
|---------|-------------|
| `cub spec` | Create spec interactively |
| `cub plan run <spec>` | Run full pipeline |
| `cub plan run --continue <slug>` | Resume incomplete plan |
| `cub plan orient <spec>` | Run only orient stage |
| `cub plan architect` | Run only architect stage |
| `cub plan itemize` | Run only itemize stage |
| `cub plan list` | List all plans |
| `cub stage` | Import tasks to backend |
| `cub stage --dry-run` | Preview staging |

## Next Steps

<div class="grid cards" markdown>

-   :material-clipboard-check: **Orient**

    ---

    Start by researching and understanding your problem space.

    [:octicons-arrow-right-24: Orient Stage](orient.md)

-   :material-sitemap: **Architect**

    ---

    Design your technical approach.

    [:octicons-arrow-right-24: Architect Stage](architect.md)

-   :material-format-list-numbered: **Itemize**

    ---

    Break work into agent-sized tasks.

    [:octicons-arrow-right-24: Itemize Stage](itemize.md)

-   :material-rocket-launch: **Stage**

    ---

    Import tasks and start execution.

    [:octicons-arrow-right-24: Stage](stage.md)

</div>

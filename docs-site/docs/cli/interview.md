# cub interview

Deep-dive questioning to refine task specifications before execution.

## Synopsis

```bash
cub interview <task-id> [OPTIONS]
cub interview --all [OPTIONS]
```

## Description

The `cub interview` command provides a structured interview process to refine task specifications before implementation begins. It systematically probes requirements across multiple categories including functional requirements, edge cases, error handling, user experience, and more.

Interview mode operates at the **task level** (for project-level requirements refinement, see `cub triage`).

The interview generates comprehensive specification documents that cover:

- Functional requirements and success criteria
- Edge cases and error handling
- User experience considerations
- Data and state management
- Integration points
- Performance and security requirements
- Testing strategy

## Options

| Option | Description |
|--------|-------------|
| `<task-id>` | Task identifier to interview |
| `--all` | Interview all open tasks in batch mode |
| `--auto` | Use AI to generate answers (requires review) |
| `--skip-review` | Skip interactive review of AI-generated answers |
| `--output <file>` | Save spec to specific file |
| `--output-dir <dir>` | Directory for batch output (default: `specs/`) |
| `--update-task` | Append generated spec to task description |

## Modes

### Interactive Mode (Default)

Questions are presented one at a time, and you provide answers manually:

```bash
cub interview task-123
```

Output:
```
Interview: Implement user authentication

[1/42] Functional Requirements
What is the primary user goal this feature enables?
> Allow users to securely access their personal data

[2/42] Functional Requirements
What inputs does this feature accept?
> Email and password, or OAuth tokens

[3/42] Edge Cases
What happens with empty input?
> Show validation error, highlight empty fields
```

### Auto Mode

AI generates answers based on the task context and codebase analysis:

```bash
cub interview task-123 --auto
```

The AI analyzes:
- Task description and metadata
- Related code in the repository
- Existing patterns and conventions

Generated answers are presented for human review before being finalized.

### Batch Mode

Interview multiple tasks automatically:

```bash
cub interview --all --auto --output-dir specs/interviews
```

This processes all open tasks, generating spec files in the specified directory.

## Examples

### Basic Interview

```bash
# Interactive interview for a single task
cub interview cub-123
```

### AI-Assisted Interview

```bash
# AI generates answers, you review and edit
cub interview cub-123 --auto
```

### Autonomous Batch Processing

```bash
# Interview all open tasks without interaction
cub interview --all --auto --skip-review --output-dir specs/
```

### Update Task Descriptions

```bash
# Append generated specs to task descriptions
cub interview --all --auto --skip-review --update-task
```

### Save to Specific File

```bash
# Save spec to custom location
cub interview cub-123 --output specs/auth-spec.md
```

## Interview Categories

The interview covers these categories:

| Category | Focus Areas |
|----------|-------------|
| Functional | Goals, inputs, outputs, success criteria |
| Edge Cases | Empty/malformed input, timeouts, failures |
| Error Handling | Error types, messages, recovery, logging |
| User Experience | Loading states, feedback, accessibility |
| Data & State | Reads, writes, persistence, validation |
| Integration | APIs, events, authentication, rate limits |
| Performance | Response time, throughput, caching, scale |
| Security | Auth, authorization, sanitization, audit |
| Testing | Unit, integration, edge case, manual tests |
| Operations | Feature flags, monitoring, debugging |

## Generated Output

The interview produces a structured specification document:

```markdown
# Task Specification: Implement User Authentication

## Overview
**Task ID:** task-123
**Generated:** 2026-01-13
**Interview Mode:** interactive

## Functional Requirements

### Primary Goal
Allow users to securely access their personal data.

### Inputs
- Email address (string, valid email format)
- Password (string, 8+ characters)

### Success Criteria
- User can log in with valid credentials
- Session persists across page refresh
- Invalid credentials show clear error

## Edge Cases & Error Handling

### Empty Input
- Show validation error
- Highlight empty required fields

...

## Acceptance Criteria (Generated)
- [ ] Login form accepts email and password
- [ ] Validation errors shown for empty input
- [ ] JWT token issued on success
```

## Configuration

Add custom questions in `.cub.json`:

```json
{
  "interview": {
    "default_mode": "interactive",
    "custom_questions": [
      {
        "category": "Project Specific",
        "question": "What is the business impact?",
        "applies_to": ["feature", "task"]
      },
      {
        "category": "Compliance",
        "question": "Are there GDPR considerations?",
        "applies_to": ["feature"],
        "requires_labels": ["user-data"]
      }
    ],
    "skip_categories": [],
    "output_format": "markdown"
  }
}
```

### Custom Question Fields

| Field | Description |
|-------|-------------|
| `category` | Category header for the question |
| `question` | The question text |
| `applies_to` | Task types: `feature`, `task`, `bugfix` |
| `requires_labels` | Only show for tasks with these labels (optional) |
| `requires_tech` | Only show when tech stack matches (optional) |
| `skip_if` | Conditional skip based on previous answers (optional) |

## Related Commands

- [`cub triage`](../guide/prep-pipeline/triage.md) - Project-level requirements refinement
- [`cub explain-task`](explain-task.md) - View task details
- [`cub run`](../guide/run-loop/index.md) - Execute tasks

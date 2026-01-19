---
status: draft
priority: high
complexity: high
dependencies:
  - tools-registry.md (needs tool execution layer)
blocks:
  - autonomous triage agent
  - AI-assisted PM flow
created: 2026-01-19
updated: 2026-01-19
readiness:
  score: 7
  blockers:
    - Need to choose expression language (Jinja2 vs custom DSL)
    - Human handoff UX not designed (CLI prompt? Notification?)
    - State persistence format not finalized
    - Error recovery strategy unclear
  questions:
    - Should workflows support sub-workflows (composition)?
    - How to handle long-running workflows (days/weeks)?
    - Should we support workflow versioning and migration?
    - How to test workflows without side effects (dry-run mode)?
    - Should workflows have access control/permissions?
    - How to share workflows across projects/teams?
    - When to integrate Windmill/Temporal vs stay native?
  decisions_needed:
    - Choose template/expression language
    - Define human handoff notification mechanism
    - Decide on workflow execution mode (blocking vs background)
    - Choose state persistence format (JSON vs SQLite vs files)
  tools_needed:
    - Workflow validator (check YAML syntax, tool availability, logic)
    - Workflow visualizer (show workflow as graph/flowchart)
    - Workflow simulator (dry-run with mocked tools)
    - Autonomy scorer (calculate autonomy requirement for workflow)
    - Workflow debugger (step through execution, inspect variables)
---

# Workflow Management Specification

## Overview

A lightweight workflow system for Cub that enables autonomous agents to orchestrate multi-step processes, compose tools, make decisions based on conditions, and hand off to humans when needed. Designed to be simple and native for now, with awareness of potential integration with Windmill or Temporal later.

## Goals

1. **Autonomous orchestration** - Agent can execute multi-step workflows without human intervention (within autonomy bounds)
2. **Tool composition** - Combine tools from registry into coherent workflows
3. **Conditional branching** - Make decisions based on results, confidence, autonomy level
4. **Human handoff** - Gracefully pause and request human input when needed
5. **Observability** - Track workflow execution, understand what happened and why
6. **Recoverable** - Handle failures, retries, and resumption
7. **Simple to start** - YAML/JSON definitions, no external dependencies required

## Architecture

### Workflow Definition

Workflows are defined in YAML (or JSON) and stored in `.cub/workflows/`:

```yaml
# .cub/workflows/triage-slow-query.yaml
id: triage-slow-query
name: "Triage Slow Database Query"
version: "1.0"

# When to trigger this workflow
trigger:
  type: capture_keywords
  keywords: [slow, query, database, performance, timeout]
  confidence: 0.7  # Minimum match confidence

# Workflow-level settings
settings:
  autonomy_required: 3      # Minimum autonomy level to run fully autonomous
  timeout_minutes: 30
  retry_on_error: true
  max_retries: 2

# Input schema
inputs:
  capture_id:
    type: string
    required: true
  context:
    type: object
    required: false

# Workflow steps
steps:
  # Step 1: Gather context
  - id: gather_context
    name: "Gather Context"
    type: parallel              # Execute tools in parallel
    tools:
      - tool: mcp:filesystem
        action: read_logs
        params:
          path: /var/log/app.log
          grep: "slow query"
          lines: 100
        output: logs
        
      - tool: mcp:postgres
        action: inspect_schema
        params:
          table: "{{ context.table }}"  # Template from input
        output: schema
        
      - tool: skill:github
        action: search
        params:
          query: "repo:myorg/app slow query"
          state: open
        output: related_issues
    
    outputs:
      logs: "{{ tools.mcp:filesystem.logs }}"
      schema: "{{ tools.mcp:postgres.schema }}"
      issues: "{{ tools.skill:github.related_issues }}"
  
  # Step 2: Research solutions
  - id: research
    name: "Research Solutions"
    type: sequential
    depends_on: [gather_context]
    tools:
      - tool: harness:web_search
        params:
          query: "postgres query optimization {{ gather_context.logs.query_pattern }}"
        output: web_results
        
      - tool: harness:web_fetch
        params:
          urls: "{{ web_results.top_3_urls }}"
        output: articles
    
    outputs:
      research_summary: "{{ combine(web_results, articles) }}"
  
  # Step 3: Analyze
  - id: analyze
    name: "Analyze and Recommend"
    type: llm_task
    depends_on: [gather_context, research]
    prompt: |
      Analyze this slow query issue:
      
      Logs: {{ gather_context.logs }}
      Schema: {{ gather_context.schema }}
      Research: {{ research.research_summary }}
      
      Provide:
      1. Root cause analysis
      2. Recommended solutions (ranked by impact/effort)
      3. Confidence level (0-1)
    
    outputs:
      analysis: "{{ llm_response }}"
      recommendations: "{{ llm_response.recommendations }}"
      confidence: "{{ llm_response.confidence }}"
  
  # Decision point: Can we proceed autonomously?
  - id: decide
    name: "Decide Next Action"
    type: conditional
    depends_on: [analyze]
    
    # Score the work required
    score:
      base: 3                                    # Base complexity
      breaking_changes: "{{ +2 if analyze.recommendations.breaking else 0 }}"
      multiple_approaches: "{{ +2 if analyze.recommendations.count > 1 else 0 }}"
      has_tests: "{{ -1 if project.has_tests else 0 }}"
    
    # Branch based on autonomy
    branches:
      - condition: "{{ score.total <= settings.autonomy_level and analyze.confidence > 0.8 }}"
        goto: implement
        
      - condition: "{{ score.total <= settings.autonomy_level and analyze.confidence > 0.5 }}"
        goto: draft_implementation
        
      - default: true
        goto: ask_human
  
  # Branch: Implement directly
  - id: implement
    name: "Implement Solution"
    type: sequential
    tools:
      - tool: mcp:filesystem
        action: write_file
        params:
          path: "{{ analyze.recommendations.files }}"
          content: "{{ generated_code }}"
        
      - tool: skill:github
        action: create_branch
        params:
          name: "fix/slow-query-{{ capture_id }}"
        
      - tool: cli:pytest
        action: run
        params:
          path: tests/
        output: test_results
        
      - tool: skill:github
        action: create_pr
        params:
          title: "Fix: Optimize slow query on {{ context.table }}"
          body: |
            ## Analysis
            {{ analyze.analysis }}
            
            ## Changes
            {{ implementation_summary }}
            
            ## Test Results
            {{ test_results }}
        output: pr_url
    
    outputs:
      pr_url: "{{ tools.skill:github.pr_url }}"
    
    on_success:
      notify_human:
        message: "✅ Implemented fix for slow query. PR: {{ pr_url }}"
  
  # Branch: Draft but don't merge
  - id: draft_implementation
    name: "Draft Implementation"
    type: sequential
    tools:
      - tool: mcp:filesystem
        action: write_file
        params:
          path: "{{ analyze.recommendations.files }}"
          content: "{{ generated_code }}"
        
      - tool: skill:github
        action: create_branch
        params:
          name: "draft/slow-query-{{ capture_id }}"
        
      - tool: skill:github
        action: create_pr
        params:
          title: "[DRAFT] Fix: Optimize slow query"
          body: "{{ analyze.analysis }}"
          draft: true
        output: pr_url
    
    on_success:
      notify_human:
        message: "📝 Drafted fix (medium confidence). Review PR: {{ pr_url }}"
  
  # Branch: Ask human
  - id: ask_human
    name: "Request Human Decision"
    type: human_handoff
    prompt: |
      Need your input on this slow query issue:
      
      ## Analysis
      {{ analyze.analysis }}
      
      ## Recommendations
      {{ analyze.recommendations }}
      
      Confidence: {{ analyze.confidence }}
      Autonomy score: {{ decide.score.total }} (your threshold: {{ settings.autonomy_level }})
      
      How should I proceed?
    
    options:
      - label: "Implement recommended fix"
        action: resume
        goto: implement
        
      - label: "Draft PR for review"
        action: resume
        goto: draft_implementation
        
      - label: "Do more research"
        action: resume
        goto: research
        params:
          focus: "{{ human_input.focus_area }}"
        
      - label: "I'll handle it"
        action: cancel
    
    on_response:
      store_preference:  # Learn from decision
        autonomy_level_effective: "{{ decide.score.total }}"
        human_chose: "{{ human_response.action }}"

# Workflow outputs
outputs:
  status: "{{ final_step.status }}"
  result: "{{ final_step.output }}"
  artifacts:
    - "{{ pr_url if pr_url else null }}"
    - "{{ analysis }}"
```

### Workflow Types

**Sequential** - Steps run in order, each waits for previous

**Parallel** - Steps run concurrently, all must complete before next step

**Conditional** - Branch based on conditions

**LLM Task** - Invoke LLM with prompt template

**Human Handoff** - Pause and request human input

**Tool Execution** - Call a tool from registry

### Step Schema

```yaml
id: unique_step_id
name: "Human Readable Name"
type: sequential | parallel | conditional | llm_task | human_handoff | tool
depends_on: [previous_step_ids]  # Optional
timeout_minutes: 10              # Optional
retry_on_error: true             # Optional
max_retries: 2                   # Optional

# For tool steps
tools:
  - tool: tool_id
    action: action_name          # Optional, tool-specific
    params: {}                   # Tool parameters
    output: output_variable      # Store result in variable

# For conditional steps
branches:
  - condition: "{{ expression }}"
    goto: step_id
  - default: true
    goto: other_step_id

# For LLM steps
prompt: "{{ template }}"

# For human handoff
prompt: "{{ question }}"
options:
  - label: "Option 1"
    action: resume | cancel
    goto: step_id
```

### Expression Language

Use Jinja2-style templates for dynamic values:

```yaml
# Variable access
"{{ capture_id }}"
"{{ gather_context.logs }}"
"{{ tools.mcp:postgres.schema }}"

# Conditionals
"{{ score.total <= autonomy_level }}"
"{{ confidence > 0.8 }}"
"{{ breaking_changes and not has_tests }}"

# Operators
"{{ +2 if condition else 0 }}"
"{{ count > 1 }}"
"{{ value in [1, 2, 3] }}"

# Functions
"{{ combine(a, b) }}"
"{{ extract_pattern(logs, 'SELECT.*FROM.*') }}"
"{{ summarize(research_results) }}"
```

## Workflow Engine

### Core Components

```python
class WorkflowEngine:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.executor = ToolExecutor(registry)
    
    def load_workflow(self, path: str) -> Workflow:
        """Load workflow definition from YAML"""
        return Workflow.from_yaml(path)
    
    def execute(self, workflow: Workflow, inputs: dict) -> WorkflowResult:
        """Execute a workflow with given inputs"""
        context = WorkflowContext(inputs)
        
        try:
            for step in workflow.steps:
                result = self._execute_step(step, context)
                context.store(step.id, result)
                
                # Check for human handoff
                if result.status == "awaiting_human":
                    return WorkflowResult.paused(context)
                
                # Handle conditional branching
                if step.type == "conditional":
                    next_step = self._evaluate_branch(step, context)
                    context.goto(next_step)
            
            return WorkflowResult.success(context)
            
        except Exception as e:
            return WorkflowResult.failed(context, e)
    
    def resume(self, workflow_id: str, human_input: dict) -> WorkflowResult:
        """Resume paused workflow with human input"""
        context = self._load_context(workflow_id)
        context.add_human_input(human_input)
        return self.execute(workflow, context.to_dict())
```

### Execution Context

```python
class WorkflowContext:
    def __init__(self, inputs: dict):
        self.inputs = inputs
        self.steps = {}           # Step results
        self.variables = {}       # Computed variables
        self.current_step = None
        self.human_inputs = []
        self.start_time = now()
    
    def store(self, step_id: str, result: StepResult):
        """Store step result"""
        self.steps[step_id] = result
        self.variables.update(result.outputs)
    
    def get(self, path: str):
        """Get value by path (e.g., 'gather_context.logs')"""
        return resolve_path(path, self.variables)
    
    def evaluate(self, expression: str):
        """Evaluate template expression"""
        env = jinja2.Environment()
        template = env.from_string(expression)
        return template.render(**self.variables)
```

### State Persistence

Workflows are persisted to disk for resumption:

```
.cub/state/workflows/
  <workflow_id>/
    definition.yaml      # Original workflow definition
    context.json         # Current execution context
    history.jsonl        # Step-by-step history
    status.json          # Current status
```

```json
// status.json
{
  "workflow_id": "triage-slow-query-abc123",
  "status": "paused",
  "paused_at": "ask_human",
  "waiting_for": "human_input",
  "started_at": "2026-01-19T15:00:00Z",
  "updated_at": "2026-01-19T15:05:00Z",
  "current_step": "ask_human",
  "completed_steps": ["gather_context", "research", "analyze", "decide"],
  "next_steps": ["implement", "draft_implementation", "cancel"]
}
```

## CLI Interface

```bash
# List workflows
cub workflow list
cub workflow list --status paused

# Show workflow definition
cub workflow show triage-slow-query

# Execute workflow
cub workflow run triage-slow-query --input capture_id=cap-abc123

# Resume paused workflow
cub workflow resume <workflow_id> --response implement

# Cancel workflow
cub workflow cancel <workflow_id>

# Show workflow status
cub workflow status <workflow_id>

# View workflow history
cub workflow history <workflow_id>

# Validate workflow definition
cub workflow validate .cub/workflows/my-workflow.yaml

# Create workflow from template
cub workflow create --template research
```

## Built-in Workflow Templates

Ship with common patterns:

### Research Template
```yaml
# .cub/workflows/templates/research.yaml
id: research-template
steps:
  - id: web_search
    tools: [harness:web_search]
  - id: fetch_content
    tools: [harness:web_fetch]
  - id: summarize
    type: llm_task
```

### Code Change Template
```yaml
# .cub/workflows/templates/code-change.yaml
steps:
  - id: analyze_codebase
  - id: draft_changes
  - id: run_tests
  - id: create_pr
  - id: ask_human
```

### Investigation Template
```yaml
# .cub/workflows/templates/investigation.yaml
steps:
  - id: gather_evidence
  - id: form_hypothesis
  - id: test_hypothesis
  - id: conclude
```

## Integration with Cub

### Workflow Triggers

Workflows can be triggered by:

1. **Captures** - Keywords, patterns, or explicit workflow selection
2. **Task state** - When task enters certain state
3. **Schedule** - Cron-like scheduling
4. **Manual** - Explicit invocation via CLI
5. **External** - Webhook, file watcher, etc

```yaml
# In capture
# @workflow: triage-slow-query

# Or auto-matched
if capture matches keywords → select workflow → execute
```

### Autonomy Scoring

Each workflow step can be scored for autonomy requirements:

```python
def score_step(step, context):
    score = step.base_score or 1
    
    # Increase score for risky actions
    if step.has_breaking_changes:
        score += 3
    if step.affects_production:
        score += 3
    if step.irreversible:
        score += 2
    
    # Decrease score for safety
    if step.has_tests:
        score -= 1
    if step.reversible:
        score -= 1
    if step.dry_run_available:
        score -= 1
    
    return score

# Compare to autonomy level
if score <= user_autonomy_level:
    execute_autonomously()
else:
    ask_human()
```

## Observability

### Workflow Dashboard

Human-readable view of workflow state:

```
Workflow: Triage Slow Query (abc123)
Status: ⏸️  Paused
Started: 2 minutes ago

Progress: ████████░░ 80%

Steps:
  ✅ gather_context (15s)
  ✅ research (30s)
  ✅ analyze (45s)
  ✅ decide (2s)
  ⏸️  ask_human (waiting)
  ⏳ implement (pending)

Current: Asking human for decision
Options:
  1. Implement recommended fix
  2. Draft PR for review
  3. Do more research
  4. I'll handle it
```

### History Log

```jsonl
{"step": "gather_context", "started_at": "...", "status": "running"}
{"step": "gather_context", "completed_at": "...", "status": "success", "outputs": {...}}
{"step": "research", "started_at": "...", "status": "running"}
{"step": "research", "completed_at": "...", "status": "success", "outputs": {...}}
{"step": "decide", "score": 5, "autonomy_level": 5, "decision": "ask_human"}
{"step": "ask_human", "paused_at": "...", "waiting_for": "human_input"}
```

## Error Handling

```yaml
steps:
  - id: risky_step
    retry_on_error: true
    max_retries: 3
    retry_delay_seconds: 5
    
    on_error:
      - if: "{{ error.type == 'NetworkError' }}"
        action: retry
      - if: "{{ error.type == 'AuthError' }}"
        action: notify_human
      - default: true
        action: fail
```

## Future Enhancements (Windmill/Temporal Integration)

When complexity grows, integrate with mature workflow engines:

### Windmill Integration
```yaml
# .cub/workflows/complex-workflow.yaml
engine: windmill  # Use Windmill instead of native engine

windmill:
  server: http://localhost:8000
  workspace: cub
```

### Temporal Integration
```yaml
# .cub/workflows/long-running-workflow.yaml
engine: temporal

temporal:
  namespace: cub
  task_queue: cub-workflows
  workflow: "triage_slow_query"
```

Native Cub workflows can be translated to these engines when needed.

## Open Questions

1. Should workflows support sub-workflows (composition)?
2. How to handle long-running workflows (days/weeks)?
3. Should we support workflow versioning and migration?
4. How to test workflows without side effects?
5. Should workflows have access control/permissions?
6. How to share workflows across projects/teams?

---

**Related:** tools-registry.md, autonomy-model.md
**Status:** Research / Early Design
**Last Updated:** 2026-01-19

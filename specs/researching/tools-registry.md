---
status: draft
priority: high
complexity: high
dependencies:
  - MCP integration
  - Clawdbot skills system
  - Harness abstraction
blocks:
  - workflow-management.md
  - autonomous triage agent
created: 2026-01-19
updated: 2026-01-19
readiness:
  score: 7
  blockers:
    - Need to decide on registry format (YAML vs JSON vs code)
    - MCP discovery protocol not fully defined
    - Tool authentication/secrets management unclear
  questions:
    - Should tool definitions be distributed with skills, or centralized?
    - How to handle tool authentication (API keys, tokens, etc)?
    - Should tools self-describe (introspection protocol)?
    - How to version the registry schema itself?
    - Should we support tool aliases/shortcuts?
    - Integration with harness custom tools feature?
  decisions_needed:
    - Choose registry file format
    - Define tool installation security model
    - Decide on tool versioning strategy
    - Map to harness abstraction's register_tool() API
  tools_needed:
    - API Design Validator (design registry format and interfaces)
    - Technical Feasibility Checker (verify MCP integration approach)
    - Trade-off Analyzer (YAML vs JSON vs code, storage formats)
    - Design Pattern Matcher (registry patterns from other systems)
    - Tool discovery scanner (domain-specific: scan system for available CLIs, MCPs, skills)
    - Schema validator (domain-specific: validate tool definitions against registry schema)
    - Capability matcher (domain-specific: semantic search for tools by capability)
    - Installation verifier (domain-specific: check if tool install succeeded)
notes: |
  Harness abstraction spec now exists with register_tool() API.
  Tools can be registered with harnesses that support CUSTOM_TOOLS feature.
  Registry tracks tools from all sources (harness, MCP, skills, CLI).
---

# Tools Registry Specification

## Overview

A unified registry for tools that Cub can discover, install, and invoke across the project lifecycle. The registry provides awareness of capabilities across harness-native tools, MCP servers, Clawdbot skills, and standard CLIs, enabling autonomous tool selection and workflow composition.

## Goals

1. **Unified discovery** - Single interface to query available tools regardless of source
2. **Dynamic installation** - Install tools on-demand to deliver consistent experience
3. **Lifecycle awareness** - Track tools at user, project, and runtime levels
4. **Capability-based selection** - Query tools by what they can do, not just by name
5. **Cross-context** - Works in pure Cub, Clawdbot-hosted Cub, or standalone environments

## Architecture

### Registry Levels

Tools are registered at three levels, with inheritance:

```
User-level:      ~/.cub/tools-registry.yaml
  ↓ inherits
Project-level:   <project>/.cub/tools-registry.yaml
  ↓ inherits
Runtime:         In-memory registry (discovered + configured)
```

**Resolution order:** Runtime → Project → User

### Tool Sources

The registry tracks tools from multiple sources:

1. **Harness-native** - Tools provided by the AI harness (Claude, GPT-4, etc)
2. **MCP servers** - Model Context Protocol servers (filesystem, database, etc)
3. **Clawdbot skills** - Packaged skills from Clawdbot ecosystem
4. **Standard CLIs** - Command-line tools (`gh`, `jq`, `curl`, etc)
5. **Custom scripts** - Project-specific tools

## Registry Schema

```yaml
# .cub/tools-registry.yaml
version: "1.0"

# Global settings
settings:
  auto_install: true          # Install missing tools automatically
  prefer_local: true          # Prefer project-level over user-level
  fallback_harness: true      # Fall back to harness tools if unavailable

# Tool definitions
tools:
  - id: web_search
    name: "Web Search"
    source:
      type: harness           # harness | mcp | skill | cli | script
      provider: claude        # For harness tools
    categories: [research, web]
    capabilities:
      - query_web
      - find_current_info
    description: "Search the web using Brave API"
    availability: always      # always | installed | conditional
    
  - id: filesystem
    name: "Filesystem"
    source:
      type: mcp
      server: filesystem
      transport: stdio
      command: uvx mcp-server-filesystem
    categories: [system, files]
    capabilities:
      - read_file
      - write_file
      - list_directory
      - search_files
    description: "Read, write, and search local files"
    availability: installed
    install:
      check: which uvx
      command: pip install uv
      
  - id: github
    name: "GitHub CLI"
    source:
      type: skill
      skill_id: github
      entry: gh
    categories: [dev, vcs]
    capabilities:
      - query_issues
      - create_pr
      - check_ci
      - search_repos
    description: "Interact with GitHub issues, PRs, and repos"
    availability: conditional
    install:
      check: which gh
      command: brew install gh  # or apt-get, etc
      docs: https://cli.github.com/manual/installation
      
  - id: jq
    name: "jq"
    source:
      type: cli
      command: jq
    categories: [data, json]
    capabilities:
      - parse_json
      - filter_json
      - transform_json
    description: "Command-line JSON processor"
    availability: conditional
    install:
      check: which jq
      command: brew install jq
      
  - id: project_build
    name: "Project Build"
    source:
      type: script
      path: ./scripts/build.sh
    categories: [dev, build]
    capabilities:
      - build_project
      - run_tests
    description: "Project-specific build script"
    availability: always
    project_specific: true
```

## Tool Metadata

Each tool includes:

- **id** - Unique identifier (scoped to source type)
- **name** - Human-readable name
- **source** - Where/how to invoke the tool
- **categories** - Organizational tags (research, dev, data, etc)
- **capabilities** - What the tool can do (semantic, for selection)
- **description** - Brief explanation
- **availability** - Whether tool is always available, needs install, or conditional
- **install** - Installation instructions (check, command, docs)
- **project_specific** - Whether tool is project-local

## Discovery Process

```python
def discover_tools():
    """Build runtime registry from all sources"""
    registry = ToolRegistry()
    
    # 1. Load user-level registry
    user_tools = load_yaml("~/.cub/tools-registry.yaml")
    registry.register_all(user_tools, level="user")
    
    # 2. Load project-level registry
    project_tools = load_yaml(".cub/tools-registry.yaml")
    registry.register_all(project_tools, level="project")
    
    # 3. Discover harness tools
    harness_tools = harness.list_tools()
    registry.register_all(harness_tools, level="runtime", source="harness")
    
    # 4. Discover installed MCP servers
    for server in scan_mcp_config():
        mcp_tools = mcp.list_tools(server)
        registry.register_all(mcp_tools, level="runtime", source="mcp")
    
    # 5. Discover Clawdbot skills (if in Clawdbot context)
    if in_clawdbot_context():
        skills = scan_skills_directory()
        registry.register_all(skills, level="runtime", source="skill")
    
    # 6. Check CLI availability
    for cli_tool in registry.get_by_source("cli"):
        cli_tool.available = check_installed(cli_tool.command)
    
    return registry
```

## Tool Selection

Query tools by capability:

```python
# Example: Need to research something
tools = registry.find_tools(
    capabilities=["query_web", "read_url"],
    categories=["research"],
    available_only=True
)
# Returns: [web_search, web_fetch, ...]

# Example: Need to work with database
tools = registry.find_tools(
    capabilities=["query_database", "inspect_schema"],
    prefer_source="mcp"  # Prefer MCP over CLI
)
# Returns: [mcp:postgres, cli:psql, ...]

# Example: Need to process JSON
tools = registry.find_tools(
    capabilities=["parse_json", "filter_json"]
)
# Returns: [jq, python_json, ...]
```

## Installation Management

When a tool is needed but not available:

```python
def ensure_tool(tool_id):
    """Install tool if missing and auto_install enabled"""
    tool = registry.get(tool_id)
    
    if tool.availability == "always":
        return tool  # No installation needed
    
    if tool.available:
        return tool  # Already installed
    
    if not settings.auto_install:
        raise ToolNotAvailableError(
            f"{tool.name} not installed. Run: {tool.install.command}"
        )
    
    # Attempt installation
    if tool.install.check:
        if run_check(tool.install.check):
            tool.available = True
            return tool
    
    if tool.install.command:
        print(f"Installing {tool.name}...")
        run_command(tool.install.command)
        tool.available = check_installed(tool)
        return tool
    
    raise ToolInstallError(f"Cannot install {tool.name}")
```

## Tool Invocation

Abstracted execution layer:

```python
class ToolExecutor:
    def execute(self, tool_id: str, **params):
        """Execute a tool with given parameters"""
        tool = registry.get(tool_id)
        
        if not tool.available:
            tool = ensure_tool(tool_id)
        
        match tool.source.type:
            case "harness":
                return self._exec_harness(tool, params)
            case "mcp":
                return self._exec_mcp(tool, params)
            case "skill":
                return self._exec_skill(tool, params)
            case "cli":
                return self._exec_cli(tool, params)
            case "script":
                return self._exec_script(tool, params)
    
    def _exec_harness(self, tool, params):
        """Invoke harness-native tool"""
        return harness.call_tool(tool.id, **params)
    
    def _exec_mcp(self, tool, params):
        """Call MCP server tool"""
        server = tool.source.server
        return mcp_client.call_tool(server, tool.id, params)
    
    def _exec_skill(self, tool, params):
        """Execute Clawdbot skill"""
        return run_skill(tool.source.skill_id, tool.source.entry, params)
    
    def _exec_cli(self, tool, params):
        """Run CLI command"""
        cmd = build_cli_command(tool.source.command, params)
        return subprocess.run(cmd, capture_output=True, text=True)
    
    def _exec_script(self, tool, params):
        """Execute custom script"""
        return subprocess.run([tool.source.path, *params], ...)
```

## Integration with Clawdbot

When Cub runs inside Clawdbot:

1. **Skills automatically registered** - Scan `~/.clawdbot/skills/` and register
2. **Inherit Clawdbot tools** - Harness tools, MCP servers, etc available
3. **Project isolation** - Project-level registry can override
4. **Installation via Clawdbot** - Use `clawdhub` for skill installation

```yaml
# .cub/tools-registry.yaml in Clawdbot context
settings:
  inherit_clawdbot_skills: true  # Register all Clawdbot skills
  inherit_clawdbot_mcp: true     # Use Clawdbot's MCP servers

tools:
  # Project overrides or additions
  - id: custom_analyzer
    source:
      type: script
      path: ./tools/analyze.py
    capabilities: [analyze_code, check_quality]
```

## CLI Interface

```bash
# List available tools
cub tools list
cub tools list --category research
cub tools list --capability query_web

# Show tool details
cub tools info web_search
cub tools info github --json

# Check tool availability
cub tools check github
cub tools check --all

# Install tool
cub tools install github
cub tools install --all-missing

# Search by capability
cub tools search "query database"

# Register custom tool
cub tools register ./my-tool-def.yaml

# Sync from user/project registry
cub tools sync
```

## Example Usage in Triage

```python
# Triager needs to research database optimization
def research_db_optimization(context):
    # Find tools that can help
    web_tools = registry.find_tools(
        capabilities=["query_web", "read_url"],
        available_only=True
    )
    
    db_tools = registry.find_tools(
        capabilities=["query_database", "inspect_schema"],
        available_only=True
    )
    
    # Execute research
    executor = ToolExecutor()
    
    search_results = executor.execute(
        "web_search", 
        query="postgres query optimization"
    )
    
    schema = executor.execute(
        "mcp:postgres",
        action="describe",
        table=context.table
    )
    
    return {
        "web_research": search_results,
        "schema_analysis": schema
    }
```

## Future Enhancements

1. **Tool versioning** - Track and manage tool versions
2. **Capability inference** - Learn capabilities from tool usage
3. **Tool chaining** - Compose tools into higher-level capabilities
4. **Usage analytics** - Track which tools are most effective
5. **Remote registries** - Pull tool definitions from central sources
6. **Cost tracking** - Monitor API usage costs per tool
7. **Security policies** - Restrict tool usage based on context

## Open Questions

1. Should tool definitions be distributed with skills, or centralized in registry?
2. How to handle tool authentication (API keys, tokens, etc)?
3. Should we support tool aliases/shortcuts?
4. How to version the registry schema itself?
5. Tool discovery protocol - should tools self-describe?

---

**Related:** workflow-management.md, mcp-integration.md
**Status:** Research / Early Design
**Last Updated:** 2026-01-19

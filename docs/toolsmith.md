# Toolsmith: Tool Discovery and Catalog Management

Toolsmith is Cub's tool discovery and management system. It helps you discover, evaluate, and catalog tools (MCP servers, skills, and other integrations) from multiple sources.

## Quick Start

### Sync tools from all sources

```bash
cub toolsmith sync
```

Expected output:
```
Syncing from all sources...

✓ Sync complete in 2.34s

Sync Statistics
Metric                  Count
────────────────────────────
Tools added              45
Tools updated             8
Total changes            53

```

### Search for a tool

```bash
cub toolsmith search "database"
```

Expected output:
```
Search Results: 'database'

┌──────────────────────┬──────────────┬─────────────┬──────────────────────────┐
│ Name                 │ Type         │ Source      │ Description              │
├──────────────────────┼──────────────┼─────────────┼──────────────────────────┤
│ SQLite Helper        │ Mcp Server   │ smithery    │ SQLite database queries  │
│ MongoDB Connector    │ Skill        │ glama       │ Connect to MongoDB       │
│ PostgreSQL CLI       │ Mcp Server   │ skillsmp    │ PostgreSQL integration   │
└──────────────────────┴──────────────┴─────────────┴──────────────────────────┘

Found 3 tools

```

### View catalog statistics

```bash
cub toolsmith stats
```

Expected output:
```
Tool Catalog Overview

┌────────────────┬──────────────┐
│ Metric         │ Value        │
├────────────────┼──────────────┤
│ Total tools    │ 248          │
│ Last sync      │ 2026-01-24…  │
└────────────────┴──────────────┘

Tools by Source

┌─────────────┬───────┐
│ Source      │ Count │
├─────────────┼───────┤
│ smithery    │  156  │
│ skillsmp    │   52  │
│ glama       │   40  │
└─────────────┴───────┘

Tools by Type

┌─────────────┬───────┐
│ Type        │ Count │
├─────────────┼───────┤
│ Mcp Server  │  165  │
│ Skill       │   83  │
└─────────────┴───────┘

```

## CLI Commands

### `cub toolsmith sync`

Sync tools from external sources into your local tool catalog.

**Usage:**
```bash
cub toolsmith sync [OPTIONS]
```

**Options:**
- `--source TEXT, -s TEXT` - Sync from a specific source (e.g., "smithery", "glama"). Omit to sync all sources.
- `--debug` - Enable debug mode with full tracebacks and verbose logging.

**Examples:**

Sync from all configured sources:
```bash
cub toolsmith sync
```

Sync from a specific source:
```bash
cub toolsmith sync --source smithery
```

Sync multiple times with progress tracking:
```bash
cub toolsmith sync
# Later, update the catalog:
cub toolsmith sync --source glama
```

With debug mode (useful for troubleshooting):
```bash
cub toolsmith sync --debug
```

**What it does:**
1. Connects to configured tool sources (Smithery, Glama, SkillsMP, etc.)
2. Fetches tool metadata and descriptions
3. Evaluates tool maturity, compatibility, and installation requirements
4. Updates local SQLite catalog with new/updated tools
5. Reports statistics: tools added, updated, and any errors

**When to use:**
- After installing Cub for the first time (to populate your tool catalog)
- Periodically (weekly/monthly) to discover new tools
- When you need to manually refresh the catalog
- To sync from a newly configured source

---

### `cub toolsmith search`

Search the tool catalog by name, description, or capability.

**Usage:**
```bash
cub toolsmith search QUERY [OPTIONS]
```

**Arguments:**
- `QUERY` (required) - Search term (e.g., "database", "http", "json")

**Options:**
- `--live, -l` - Force live search from sources (with local fallback)
- `--source TEXT, -s TEXT` - Filter results by source (e.g., "smithery")
- `--debug` - Enable debug mode

**Examples:**

Basic search in local catalog:
```bash
cub toolsmith search "json"
```

Search with live fallback (if not found locally):
```bash
cub toolsmith search "xml parsing" --live
```

Filter results by source:
```bash
cub toolsmith search "database" --source smithery
```

Search for HTTP/REST tools:
```bash
cub toolsmith search "http"
```

Expected output shows table with:
- **Name** - Tool identifier
- **Type** - MCP_SERVER or SKILL
- **Source** - Where the tool comes from
- **Description** - What the tool does

**Search Tips:**
- Search is case-insensitive and matches partial terms
- Use broad queries first ("database") then narrow down ("postgresql")
- If no results, try `--live` to search external sources
- Filter by source to see what's available from each provider

---

### `cub toolsmith stats`

Display statistics about your tool catalog.

**Usage:**
```bash
cub toolsmith stats [OPTIONS]
```

**Options:**
- `--debug` - Enable debug mode with full tracebacks

**Examples:**

View catalog overview:
```bash
cub toolsmith stats
```

With debug information:
```bash
cub toolsmith stats --debug
```

**Output includes:**

1. **Overview Panel**
   - Total tools in catalog
   - Last sync timestamp
   - Whether catalog has been populated

2. **Tools by Source**
   - Count of tools from each source (Smithery, Glama, etc.)
   - Sorted by count (descending)

3. **Tools by Type**
   - Count of MCP_SERVER vs SKILL tools
   - Breakdown by tool category

4. **Synced Sources**
   - List of sources that have been synced
   - Helpful hint if no sources have been synced yet

**When to use:**
- To verify catalog population after `sync`
- To understand tool distribution across sources
- To check when the catalog was last updated
- To decide which sources to sync next

---

## Configuration

Toolsmith's configuration lives in `.cub/toolsmith/` and the SQLite catalog at `~/.cub/toolsmith.db`.

### Catalog Location

By default, Toolsmith stores the tool catalog in:
- **SQLite database**: `~/.cub/toolsmith.db` (user's home directory)
- **Per-project**: Can be overridden with environment variable `CUB_TOOLSMITH_DB`

### Configured Sources

Toolsmith syncs from the following sources:

| Source | Type | Description |
|--------|------|-------------|
| **Smithery** | Web API | Community-driven MCP server registry |
| **Glama** | Web API | AI tool and skill marketplace |
| **SkillsMP** | Web API | Multi-provider skills platform |
| **ClawdHub** | Web API | Claude-focused tool ecosystem |

Each source provides different types of tools:
- **MCP Servers** - Model Context Protocol implementations
- **Skills** - Pre-built integrations for Claude and other models

### Environment Variables

- `CUB_TOOLSMITH_DB` - Path to SQLite database (default: `~/.cub/toolsmith.db`)
- `CUB_TOOLSMITH_DEBUG` - Set to `1` for verbose logging

---

## Common Use Cases

### 1. Finding a tool for a specific task

```bash
# Search for database tools
cub toolsmith search "database"

# Search for web/HTTP tools
cub toolsmith search "http"

# Search for file system tools
cub toolsmith search "file"
```

### 2. Discovering tools from a specific provider

```bash
# See what Smithery offers
cub toolsmith search "database" --source smithery

# See what Glama offers
cub toolsmith search "database" --source glama
```

### 3. Updating your catalog

```bash
# First time setup - sync everything
cub toolsmith sync

# Later - sync just one source to check for updates
cub toolsmith sync --source smithery

# View updated stats
cub toolsmith stats
```

### 4. Researching available tools

```bash
# View what's in your catalog
cub toolsmith stats

# Search broadly for a capability
cub toolsmith search "automation"

# Drill down to specific tools
cub toolsmith search "browser"
```

---

## Troubleshooting

### Issue: "No tools found" when searching

**Cause:** The catalog is empty (not synced yet)

**Solution:**
```bash
# Sync from all sources
cub toolsmith sync

# Then try searching again
cub toolsmith search "database"
```

---

### Issue: `sync` command fails with network error

**Example error:**
```
Error: Failed to sync from smithery: Connection timeout
```

**Causes:**
- Network connectivity issue
- Tool source is temporarily unavailable
- Rate limiting from source API

**Solutions:**

1. **Check network connectivity:**
   ```bash
   ping google.com
   ```

2. **Try syncing a specific source:**
   ```bash
   cub toolsmith sync --source glama
   ```

3. **Retry after a delay:**
   ```bash
   sleep 30
   cub toolsmith sync
   ```

4. **Check source status:**
   - Smithery: https://github.com/modelcontextprotocol/servers
   - Glama: Check their status page
   - SkillsMP: https://skillsmp.com

5. **Get more details:**
   ```bash
   cub toolsmith sync --debug
   ```

---

### Issue: Search returns too many results

**Problem:** Query is too broad

**Solutions:**

1. **Use more specific search terms:**
   ```bash
   # Too broad
   cub toolsmith search "api"

   # Better
   cub toolsmith search "rest api"
   cub toolsmith search "openapi"
   ```

2. **Filter by source:**
   ```bash
   cub toolsmith search "database" --source smithery
   ```

3. **Check what's available:**
   ```bash
   cub toolsmith stats
   ```

---

### Issue: Tool not found in catalog

**Problem:** Tool exists but isn't in your catalog

**Solutions:**

1. **Try live search:**
   ```bash
   cub toolsmith search "tool-name" --live
   ```

2. **Sync all sources:**
   ```bash
   cub toolsmith sync
   cub toolsmith search "tool-name"
   ```

3. **Check if tool is under a different name:**
   ```bash
   cub toolsmith search "similar-term"
   ```

4. **Check source availability:**
   ```bash
   cub toolsmith stats  # See which sources are synced
   cub toolsmith sync --source smithery  # Sync specific source
   ```

---

### Issue: "Run with --debug for full traceback"

**Meaning:** A command failed with an internal error

**Solutions:**

1. **Get full error details:**
   ```bash
   cub toolsmith sync --debug
   # or
   cub toolsmith search "term" --debug
   ```

2. **Check your system:**
   - Disk space: `df -h`
   - Home directory permissions: `ls -la ~`
   - SQLite database: `file ~/.cub/toolsmith.db`

3. **Reset the catalog (if corrupted):**
   ```bash
   rm ~/.cub/toolsmith.db
   cub toolsmith sync
   ```

4. **Report the issue with debug output:**
   ```bash
   cub toolsmith sync --debug 2>&1 | tee toolsmith-error.log
   # Share toolsmith-error.log with support
   ```

---

### Issue: Sync is slow

**Cause:** First-time sync or syncing from slow sources

**Expected behavior:**
- First sync: 2-5 seconds (depends on source availability)
- Subsequent syncs: 1-2 seconds
- With `--debug`: May be slower due to verbose logging

**To optimize:**

1. **Sync specific sources instead of all:**
   ```bash
   # Instead of:
   cub toolsmith sync

   # Do:
   cub toolsmith sync --source smithery
   cub toolsmith sync --source glama
   ```

2. **Check network:**
   ```bash
   ping -c 1 github.com  # Check latency
   ```

3. **Run during off-peak hours:**
   - Tool sources may be slower during peak usage

---

### Issue: "Invalid catalog database"

**Meaning:** The SQLite database is corrupted

**Solutions:**

1. **Backup and reset:**
   ```bash
   cp ~/.cub/toolsmith.db ~/.cub/toolsmith.db.backup
   rm ~/.cub/toolsmith.db
   cub toolsmith sync
   ```

2. **Restore from backup:**
   ```bash
   cp ~/.cub/toolsmith.db.backup ~/.cub/toolsmith.db
   ```

---

## Advanced: Understanding the Tool Catalog

### Tool Metadata

Each tool in the catalog contains:

- **id** - Unique identifier (format: `source:name`)
- **name** - Human-readable name
- **source** - Tool source (smithery, glama, etc.)
- **source_url** - URL to documentation/repository
- **tool_type** - MCP_SERVER or SKILL
- **description** - What the tool does
- **install_hint** - How to install/use it
- **tags** - Keywords for discovery
- **last_seen** - When tool was last verified

### Evaluating Tools

When evaluating tools, consider:

1. **Maturity**
   - Active development (recent commits)
   - Community adoption (stars, usage)
   - Release history and versioning

2. **Integration Complexity**
   - Standardized interfaces (MCP, CLI)
   - Authentication requirements
   - Dependencies

3. **Fit for Your Use Case**
   - Exact vs partial match
   - Language/platform requirements
   - Performance characteristics

4. **Cost**
   - Free vs paid
   - API rate limits
   - Hosting requirements

---

## More Information

### Related Documentation

- [Cub Tools Registry](../specs/tools-registry.md) - Tool execution infrastructure
- [Cub Workflow Management](../specs/workflow-management.md) - Tool orchestration
- [Cub Architecture](../README.md#architecture) - System overview

### External Resources

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) - Standardized tool protocol
- [Smithery](https://github.com/modelcontextprotocol/servers) - MCP server registry
- [Glama](https://glama.ai/) - AI tool marketplace
- [SkillsMP](https://skillsmp.com/) - Skills platform

### Getting Help

If you encounter issues:

1. **Check this guide** - Troubleshooting section above
2. **Run with `--debug`** - Get detailed error information
3. **Check online resources** - Tool documentation, GitHub issues
4. **Report bugs** - Include `--debug` output in issue reports

---

## Quick Reference

### Command Cheat Sheet

```bash
# Sync tools (populate catalog)
cub toolsmith sync

# Search for tools
cub toolsmith search "keyword"

# View catalog statistics
cub toolsmith stats

# Search with filters
cub toolsmith search "keyword" --source smithery
cub toolsmith search "keyword" --live

# Debug mode (for troubleshooting)
cub toolsmith sync --debug
cub toolsmith search "keyword" --debug
cub toolsmith stats --debug
```

### File Locations

```
~/.cub/toolsmith.db          # SQLite catalog database
~/.cub/toolsmith/            # Toolsmith configuration
.cub/hooks/                  # Custom hooks (if any)
```

### Environment Setup

```bash
# View default settings
cub toolsmith stats

# Check if catalog is populated
cub toolsmith stats | grep "Total tools"

# Reset catalog (if needed)
rm ~/.cub/toolsmith.db && cub toolsmith sync
```

---

## Version Information

Toolsmith is included with Cub. To check your version:

```bash
cub --version
```

To check toolsmith CLI version:

```bash
cub toolsmith --help
```

---

**Last updated:** 2026-01-24
**Toolsmith version:** 1.0.0+
**Status:** Stable

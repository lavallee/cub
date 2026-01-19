---
status: researching
priority: medium
complexity: medium
dependencies:
  - toolsmith.md
  - tools-registry.md
created: 2026-01-19
updated: 2026-01-19
readiness:
  score: 4
  blockers:
    - Tool packaging format not defined
    - Distribution mechanism unclear
    - Quality standards not established
  questions:
    - Separate marketplace or integrate with ClawdHub?
    - How to ensure tool quality and security?
    - Who maintains/curates the collection?
    - How to handle versioning and updates?
  decisions_needed:
    - Choose distribution model (central registry, git-based, hybrid)
    - Define tool packaging standard
    - Establish quality/security review process
    - Decide on ClawdHub integration vs separate registry
  tools_needed:
    - Competitive Analysis Tool (how others do tool marketplaces: npm, PyPI, Homebrew, ClawdHub)
    - Design Pattern Matcher (marketplace patterns, package management)
    - API Design Validator (registry API, package manifest format)
notes: |
  Vision for a ClawdHub-style collection of cub tools.
  Complements toolsmith: toolsmith discovers external tools, marketplace publishes our own.
  Could be part of ClawdHub or separate cub-specific registry.
---

# Tool Marketplace: ClawdHub-Style Collection for Cub Tools

## Overview

A curated marketplace/registry for cub tools—particularly the research/design/decision tools from TOOLS-WISHLIST.md that get implemented. Provides discovery, installation, updates, and community contributions for tools that enhance cub's capabilities.

**Relationship to other specs:**
- **Toolsmith** discovers and adopts *external* tools (MCP servers, Claude skills, npm packages)
- **Tool Marketplace** publishes and distributes *our own* tools (wishlist implementations, cub extensions)
- **Tools Registry** (local) tracks installed tools from any source

## Problem Statement

As cub's tool ecosystem grows:
1. **No central catalog** of available cub tools
2. **Hard to discover** what tools exist beyond core cub
3. **Manual installation** of community tools
4. **No update mechanism** for installed tools
5. **Quality varies** - no curation or standards
6. **Duplication** - multiple implementations of same need

A marketplace solves this by providing:
- Central discovery
- Easy installation
- Automated updates
- Quality assurance
- Community contributions

## Goals

1. **Discoverability** - Browse/search available cub tools
2. **Easy installation** - One-command install with dependency handling
3. **Versioning** - Track tool versions, support upgrades/downgrades
4. **Quality assurance** - Review process, security scanning, testing
5. **Community contributions** - Anyone can submit tools
6. **Documentation** - Clear usage examples and integration guides
7. **Metrics** - Track usage, ratings, effectiveness

## Non-Goals (v1)

- Paid tools (start with free/open source only)
- Complex dependency resolution (keep it simple)
- Tool hosting (tools live in git repos, registry points to them)
- Binary distribution (source/scripts only initially)

---

## Architecture

### Marketplace Structure

```
cub-tools-marketplace/
  registry/
    index.json              # Master catalog of all tools
    tools/
      {tool-id}/
        manifest.json       # Tool metadata
        versions.json       # Version history
        reviews.json        # Community reviews
        metrics.json        # Usage statistics
  
  tools/                    # Tool source repositories (links)
    design-pattern-matcher/ # Git submodule or external repo
    trade-off-analyzer/
    competitive-analysis/
    ...
  
  docs/
    submission-guide.md     # How to submit a tool
    quality-standards.md    # Requirements for acceptance
    api-reference.md        # Registry API docs
```

### Tool Package Format

Each tool is a git repository with standard structure:

```
my-cub-tool/
  manifest.json           # Tool metadata
  README.md               # Documentation
  src/                    # Implementation
  tests/                  # Test suite
  examples/               # Usage examples
  LICENSE                 # License (must be OSI-approved)
```

**manifest.json:**
```json
{
  "id": "design-pattern-matcher",
  "name": "Design Pattern Matcher",
  "version": "1.2.0",
  "description": "Find proven design patterns for common problems",
  "author": {
    "name": "Cub Community",
    "email": "community@cub.dev",
    "url": "https://github.com/cubdev/design-pattern-matcher"
  },
  "license": "MIT",
  "repository": "https://github.com/cubdev/design-pattern-matcher",
  "homepage": "https://cub.dev/tools/design-pattern-matcher",
  
  "category": "research",
  "tags": ["patterns", "architecture", "design"],
  
  "entry_point": {
    "type": "cli",
    "command": "cub-tool-patterns",
    "install": "npm install -g @cub/pattern-matcher"
  },
  
  "requirements": {
    "cub_version": ">=0.26.0",
    "runtime": "node>=18 || python>=3.9",
    "dependencies": [
      "github-api",
      "sourcegraph-client"
    ],
    "optional": [
      "sourcegraph-api-key"  # For enhanced results
    ]
  },
  
  "capabilities": [
    "search_patterns",
    "compare_implementations",
    "suggest_improvements"
  ],
  
  "auth": {
    "required": false,
    "optional": [
      {
        "service": "sourcegraph",
        "type": "api_key",
        "env_var": "SOURCEGRAPH_API_KEY",
        "signup_url": "https://sourcegraph.com/signup"
      }
    ]
  },
  
  "pricing": {
    "model": "free",
    "api_costs": "Optional Sourcegraph API: ~$0.001 per query"
  },
  
  "quality": {
    "test_coverage": 85,
    "last_tested": "2026-01-19",
    "security_scan": "passed",
    "reviewed_by": "cub-team",
    "rating": 4.7,
    "downloads": 1523
  }
}
```

---

## Discovery & Installation

### CLI Interface

```bash
# Search for tools
cub tools search "design patterns"
cub tools search --category research
cub tools search --tag architecture

# Show tool details
cub tools info design-pattern-matcher

# Install a tool
cub tools install design-pattern-matcher
cub tools install design-pattern-matcher@1.2.0  # Specific version

# List installed tools
cub tools list
cub tools list --outdated

# Update tools
cub tools update design-pattern-matcher
cub tools update --all

# Uninstall
cub tools uninstall design-pattern-matcher

# Submit a tool (for contributors)
cub tools submit ./my-tool --test
cub tools submit ./my-tool --publish
```

### Search Interface

**Web UI** (optional, future):
```
https://cub.dev/tools/

Categories:
- Research & Discovery (7 tools)
- Design & Architecture (5 tools)
- Decision Support (4 tools)
- Scoping & Prioritization (6 tools)
- Validation & Testing (3 tools)

Sort by:
- Most popular
- Recently updated
- Highest rated
- Best for beginners
```

**CLI Output:**
```
$ cub tools search "patterns"

Found 3 tools:

1. design-pattern-matcher (v1.2.0) ★★★★★ 4.7/5 (152 reviews)
   Find proven design patterns for common problems
   Category: Research & Discovery
   Downloads: 1,523 | Last updated: 2 days ago
   $ cub tools install design-pattern-matcher

2. anti-pattern-detector (v0.8.1) ★★★★☆ 4.2/5 (64 reviews)
   Detect common anti-patterns in code and architecture
   Category: Validation & Testing
   Downloads: 842 | Last updated: 1 week ago
   $ cub tools install anti-pattern-detector

3. architecture-pattern-generator (v2.0.0) ★★★★☆ 4.5/5 (203 reviews)
   Generate architecture diagrams from patterns
   Category: Design & Architecture
   Downloads: 2,145 | Last updated: 3 weeks ago
   $ cub tools install architecture-pattern-generator
```

---

## Tool Categories

Align with TOOLS-WISHLIST.md structure:

### 1. Research & Discovery
- Competitive Analysis Tool
- Technical Feasibility Checker
- User Research Summarizer
- Integration Point Mapper
- Spec Search & Navigation

### 2. Design & Architecture
- Design Pattern Matcher
- API Design Validator
- Schema Evolution Checker

### 3. Decision Support
- Trade-off Analyzer
- Assumption Validator
- Constraint Checker

### 4. Scoping & Prioritization
- Complexity Estimator
- Impact Analyzer
- Risk Scorer
- Dependency Analyzer
- Readiness Score Calculator

### 5. Validation & Testing
- Test Coverage Planner
- Smoke Test Generator
- Backward Compatibility Checker

### 6. Documentation & Communication
- Spec Clarity Checker
- Changelog Generator
- Stakeholder Impact Notifier

### 7. Meta / Process
- Implementation Path Generator
- Decision Log Extractor
- Spec Health Monitor

---

## Quality Standards

### Acceptance Criteria

For a tool to be accepted into the marketplace:

**Must have:**
- ✅ Clear README with usage examples
- ✅ Test suite with >70% coverage
- ✅ Valid manifest.json
- ✅ OSI-approved license
- ✅ Works on cub >=0.26.0
- ✅ Passes security scan
- ✅ Reviewed by maintainer

**Should have:**
- ⭐ Documentation site or comprehensive guide
- ⭐ Example projects showing usage
- ⭐ CI/CD pipeline
- ⭐ Semantic versioning
- ⭐ Changelog

**Nice to have:**
- 💡 Video walkthrough
- 💡 Integration tests with cub
- 💡 Performance benchmarks
- 💡 Community support channel

### Review Process

1. **Submission:** Developer submits tool via `cub tools submit`
2. **Automated checks:** CI runs tests, security scan, manifest validation
3. **Manual review:** Maintainer reviews code, docs, quality
4. **Feedback:** Reviewer comments, requests changes if needed
5. **Acceptance:** Approved tools added to registry
6. **Publication:** Tool appears in marketplace within 24h

### Security

- **Automated scanning:** Snyk, npm audit, bandit (Python)
- **Dependency check:** Known vulnerabilities in dependencies
- **Code review:** Manual review for suspicious patterns
- **Sandboxing:** Tools run in restricted environment (future)
- **Reporting:** Security issues can be reported privately

---

## Versioning & Updates

### Semantic Versioning

All tools must follow semver:
- **Major (1.0.0 → 2.0.0):** Breaking changes
- **Minor (1.0.0 → 1.1.0):** New features, backward compatible
- **Patch (1.0.0 → 1.0.1):** Bug fixes

### Update Notifications

```bash
$ cub tools list

Installed tools (3):

✅ design-pattern-matcher  v1.2.0 (latest)
⚠️  trade-off-analyzer     v0.9.5 (v1.0.0 available!)
❌ api-validator           v0.3.2 (deprecated, use api-design-validator)

Run 'cub tools update --all' to update outdated tools.
```

### Auto-updates

Optional configuration:

```yaml
# .cub/config.yaml
tools:
  auto_update:
    enabled: true
    schedule: weekly
    strategy: minor  # major | minor | patch | none
    exclude: []      # Tools to skip
```

---

## Community Contributions

### Submitting a Tool

1. **Develop:** Create tool following package format
2. **Test:** Run `cub tools validate ./my-tool`
3. **Document:** Write clear README and examples
4. **Submit:** Run `cub tools submit ./my-tool`

**Submission workflow:**
```bash
$ cub tools submit ./design-pattern-matcher

Validating tool...
✅ manifest.json valid
✅ README.md exists
✅ Tests found (coverage: 87%)
✅ License: MIT (acceptable)
⚠️  No CHANGELOG.md (recommended)

Running tests...
✅ All tests passed (24/24)

Running security scan...
✅ No vulnerabilities found

Uploading for review...
✅ Submitted successfully!

Your tool will be reviewed within 3-5 business days.
Track status: https://cub.dev/tools/submissions/abc123
```

### Contributor Recognition

- **Author attribution** in marketplace listing
- **Contributor badge** on profile
- **Download stats** visible to authors
- **Hall of fame** for most popular tools

---

## Integration Points

### With Toolsmith

Toolsmith can search the marketplace as a discovery source:

```python
# Toolsmith searches marketplace first (fast, curated)
marketplace_results = cub_marketplace.search("design patterns")

# Then searches external sources if needed
external_results = toolsmith.search_external(
    ["github", "npm", "mcp_registry"],
    query="design patterns"
)

# Combine and rank
all_options = marketplace_results + external_results
ranked = toolsmith.evaluate(all_options)
```

### With Tools Registry

Installed marketplace tools auto-register:

```yaml
# .cub/tools-registry.yaml (auto-updated)
tools:
  - id: design-pattern-matcher
    source:
      type: marketplace
      tool_id: design-pattern-matcher
      version: 1.2.0
    installed_at: 2026-01-19
    installed_from: cub-tools-marketplace
    auto_update: true
```

### With Workflows

Tools can be invoked in workflows:

```yaml
# workflow: review-spec.yaml
steps:
  - id: find_patterns
    tool: design-pattern-matcher  # From marketplace
    params:
      problem: "{{ spec.problem_domain }}"
    outputs:
      patterns: "{{ tool_output }}"
```

---

## Metrics & Analytics

Track tool effectiveness:

```yaml
metrics:
  per_tool:
    downloads: 1523
    active_users: 342
    rating: 4.7
    reviews: 152
    issues_reported: 8
    issues_resolved: 7
    
  usage:
    calls_per_day: 45
    avg_duration_ms: 234
    success_rate: 0.94
    
  quality:
    test_coverage: 87
    security_score: 9.5
    last_updated_days: 2
```

**Tool Dashboard** (for authors):
```
Design Pattern Matcher (v1.2.0)

Downloads:     1,523 total | 45 this week
Active Users:  342 in last 30 days
Rating:        ★★★★★ 4.7/5 (152 reviews)

Usage:
- 45 calls/day average
- 94% success rate
- 234ms average duration

Quality:
- Test coverage: 87%
- Security score: 9.5/10
- Last updated: 2 days ago

Top Questions:
1. How to use with custom patterns?
2. Can it search private repos?
3. Integration with IDE?
```

---

## Distribution Models

### Option A: Central Registry (npm-style)

**Pros:**
- Single source of truth
- Easy discovery
- Version management built-in
- Dependency resolution

**Cons:**
- Requires hosting infrastructure
- Central point of failure
- Approval bottleneck

### Option B: Git-Based (Homebrew-style)

**Pros:**
- No infrastructure needed
- Tools live in their own repos
- Easy to contribute
- Decentralized

**Cons:**
- Slower discovery
- Manual dependency tracking
- Version management harder

### Option C: Hybrid (Recommended)

**Registry:** Central index (JSON files in git repo)
**Tools:** Distributed (each tool in own repo)
**Installation:** CLI fetches from registry, clones tool repo

```
cub-tools-registry/         # Central index (GitHub repo)
  index.json                # Tool catalog
  tools/{id}/manifest.json  # Tool metadata

Individual tool repos:
  github.com/cubdev/design-pattern-matcher
  github.com/cubdev/trade-off-analyzer
  ...
```

**Pros:**
- No hosting infrastructure (uses GitHub)
- Decentralized tools
- Centralized discovery
- Community-friendly (fork registry to add tools)

---

## Relationship to ClawdHub

### Option 1: Separate Registry

**Cub Tools Marketplace** is separate from ClawdHub:
- Focused on cub-specific tools
- Tighter integration with cub
- Specialized review process

**Pros:**
- Full control
- Cub-optimized experience
- Faster iteration

**Cons:**
- Splits ecosystem
- More maintenance burden
- Less discoverability

### Option 2: ClawdHub Integration (Recommended)

**Cub tools** live in ClawdHub as a category:
- `clawdhub search --category cub-tools`
- Leverage existing infrastructure
- Unified discovery experience

**Manifest additions:**
```json
{
  "clawdhub": {
    "category": "cub-tools",
    "subcategory": "research",
    "compatible_with": ["cub", "clawdbot"],
    "cub_version": ">=0.26.0"
  }
}
```

**Pros:**
- Leverage existing marketplace
- Broader audience
- Shared infrastructure
- Natural fit (cub + clawdbot synergy)

**Cons:**
- Less cub-specific features
- Depends on ClawdHub development

### Recommendation: Start Separate, Integrate Later

**Phase 1:** Build cub-tools-marketplace as standalone
- Proves concept
- Develops standards
- Builds tool library

**Phase 2:** Integrate with ClawdHub when mature
- Migrate tools to ClawdHub category
- Keep cub-specific CLI
- Benefit from shared infrastructure

---

## Example Tools in Marketplace

Based on TOOLS-PRIORITY.md, first tools to publish:

### 1. Design Pattern Matcher
**ID:** `design-pattern-matcher`
**Version:** 1.0.0
**Author:** Cub Team
**Implementation:** GitHub search + Sourcegraph + LLM
**Status:** Ready (from toolsmith bootstrap)

### 2. Trade-off Analyzer
**ID:** `trade-off-analyzer`
**Version:** 1.0.0
**Author:** Cub Team
**Implementation:** LLM-based with structured scoring
**Status:** Ready (from toolsmith bootstrap)

### 3. API Design Validator
**ID:** `api-design-validator`
**Version:** 1.0.0
**Author:** Cub Team
**Implementation:** OpenAPI + LLM review
**Status:** Ready (from toolsmith bootstrap)

### 4. Competitive Analysis Tool
**ID:** `competitive-analysis`
**Version:** 1.0.0
**Author:** Cub Team
**Implementation:** Multi-source search + comparison
**Status:** Ready (from toolsmith bootstrap)

### 5. Technical Feasibility Checker
**ID:** `tech-feasibility-checker`
**Version:** 1.0.0
**Author:** Cub Team
**Implementation:** Registry APIs + GitHub status
**Status:** Ready (from toolsmith bootstrap)

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- Define package format
- Create registry structure
- Build basic CLI (search, install, list)
- Publish first 3 tools

### Phase 2: Community (Weeks 3-4)
- Submission workflow
- Review process
- Quality standards
- Documentation

### Phase 3: Discovery (Weeks 5-6)
- Enhanced search
- Categories and tags
- Ratings and reviews
- Usage metrics

### Phase 4: Integration (Weeks 7-8)
- Toolsmith integration
- Workflow support
- Auto-updates
- ClawdHub exploration

---

## Open Questions

1. **Hosting:** GitHub-based registry or separate infrastructure?
2. **Curation:** Who reviews submissions? (Core team only, or community reviewers?)
3. **Monetization:** Always free, or allow paid tools later? (Start free)
4. **Breaking changes:** How to handle tools that break cub compatibility?
5. **Deprecation:** When to remove abandoned tools? (No updates in 1 year?)
6. **ClawdHub timing:** When to integrate vs stay separate?

---

## Success Metrics

Track marketplace health:

```yaml
metrics:
  ecosystem:
    total_tools: 25
    active_tools: 22  # Updated in last 90 days
    categories_covered: 7  # All wishlist categories
    
  adoption:
    total_installs: 5842
    active_users: 421
    tools_per_user: 3.2
    
  quality:
    avg_rating: 4.5
    avg_test_coverage: 82
    security_issues: 0
    
  community:
    contributors: 18
    submissions_per_month: 4
    review_time_days: 3
```

**Success = Healthy ecosystem where:**
- New tools published regularly
- High quality maintained
- Active community contributions
- Tools actually used (not just downloaded)

---

## Future Enhancements

- **Premium tools** - Optional paid tools for specialized needs
- **Tool bundles** - Install related tools together
- **Private registries** - Enterprise customers host own tools
- **Tool templates** - Scaffolding for creating new tools
- **Integration marketplace** - Tools that connect cub to external services
- **Plugin system** - Tools that extend cub core functionality

---

**Related:**
- `toolsmith.md` - Discovers external tools, publishes to marketplace
- `tools-registry.md` - Local tracking of installed tools
- `TOOLS-WISHLIST.md` - Source of initial marketplace tools
- `TOOLS-PRIORITY.md` - Which tools to build/publish first

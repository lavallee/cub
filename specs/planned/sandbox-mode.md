---
status: planned
priority: medium
complexity: high
dependencies: []
created: 2026-01-10
updated: 2026-01-19
readiness:
  score: 6
  blockers:
    - Requires Docker setup and security model
  questions:
    - What level of isolation is needed?
    - How to handle network/file access?
  decisions_needed:
    - Choose containerization approach (Docker, other)
    - Define security model and escape hatches
  tools_needed:
    - Technical Feasibility Checker (Docker approach viable?)
    - Risk Scorer (security implications)
    - Complexity Estimator (scope this properly)
notes: |
  Requires Docker setup and security model.
  High complexity, significant infrastructure work.
source: ralph
---

# Sandbox Mode

**Source:** Original feature for cub
**Dependencies:** None (but pairs well with Live Dashboard)
**Complexity:** Medium-High

## Overview

Execute cub runs in isolated sandbox environments for safe autonomous execution. Users can confidently run in "yolo mode" knowing changes are contained, reversible, and observable.

**Key design principle:** Provider-agnostic abstraction supporting multiple sandbox backends.

## Problem Statement

Running AI harnesses autonomously creates anxiety:
- What if it deletes important files?
- What if it installs malicious packages?
- What if it modifies system configuration?
- What if it runs destructive commands?
- What if it accesses secrets/credentials?

Current mitigations:
- Git provides some rollback capability
- Harness permission systems (limited)
- Manual review (defeats autonomous purpose)

These aren't enough for true "set it and forget it" confidence.

## Proposed Solution

Run cub inside an isolated sandbox with:
- Isolated filesystem (copy of project)
- No network access (optional)
- Resource limits (CPU, memory, time)
- Real-time output streaming
- Easy artifact extraction
- One-command cleanup

**Multiple provider backends** with unified interface.

## Provider Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        cub sandbox CLI                          │
│                     (provider-agnostic)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ Sandbox Provider │
                    │    Interface     │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    Docker     │   │  Sprites.dev  │   │    Future     │
│   Provider    │   │   Provider    │   │   Providers   │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Provider Interface

All sandbox providers must implement this interface:

```bash
# lib/sandbox/provider.sh - Abstract interface

# Required functions every provider must implement
sandbox_provider_init()      # Initialize provider (check deps, auth, etc.)
sandbox_provider_start()     # Start sandbox with project
sandbox_provider_stop()      # Stop running sandbox
sandbox_provider_status()    # Get sandbox status
sandbox_provider_logs()      # Stream logs
sandbox_provider_exec()      # Execute command in sandbox
sandbox_provider_diff()      # Get changes made
sandbox_provider_export()    # Export changed files
sandbox_provider_cleanup()   # Full cleanup

# Provider capabilities (for feature detection)
sandbox_provider_capabilities() {
  echo "network_isolation:true"
  echo "resource_limits:true"
  echo "snapshots:false"
  echo "remote:false"
}
```

### Provider Contract

```bash
# lib/sandbox/interface.sh

# Start sandbox - all providers must support these options
# Returns: sandbox_id
sandbox_provider_start() {
  local project_dir=$1      # Required: project to sandbox
  local options=$2          # JSON options object

  # Options schema:
  # {
  #   "memory": "4g",
  #   "cpus": 2,
  #   "timeout": "4h",
  #   "network": true|false,
  #   "env": {"KEY": "value"},
  #   "cub_args": ["--epic", "abc"]
  # }
}

# Get status - standardized response format
# Returns: JSON status object
sandbox_provider_status() {
  local sandbox_id=$1

  # Response schema:
  # {
  #   "id": "sandbox-123",
  #   "provider": "docker",
  #   "status": "running|stopped|failed",
  #   "started_at": "ISO8601",
  #   "resources": {
  #     "memory_used": "1.2g",
  #     "cpu_percent": 45
  #   },
  #   "cub_status": { ... }  # from status.json
  # }
}

# Get diff - standardized format
# Returns: unified diff
sandbox_provider_diff() {
  local sandbox_id=$1
  # Returns git-style unified diff
}

# Export changes - copy to local path
sandbox_provider_export() {
  local sandbox_id=$1
  local dest_path=$2
  # Copies changed files to dest_path
}
```

## Snapshots (Provider Capability)

Inspired by Ramp's use of Modal: "near-instant startup with file system snapshots"

### What Snapshots Enable

1. **Instant restore** - Return to known-good state without re-copying project
2. **Checkpoint/rollback** - Save state mid-task, rollback if needed
3. **Reproducibility** - Share exact state for debugging
4. **Branching** - Fork sandbox state to try multiple approaches

### Snapshot Interface

Providers that support snapshots implement additional methods:

```bash
# Optional snapshot methods (check capabilities first)
sandbox_provider_snapshot_create()   # Create named snapshot
sandbox_provider_snapshot_restore()  # Restore from snapshot
sandbox_provider_snapshot_list()     # List available snapshots
sandbox_provider_snapshot_delete()   # Delete snapshot
```

### Snapshot CLI

```bash
# Create snapshot
cub sandbox snapshot create "before-refactor"

# List snapshots
cub sandbox snapshot list

# Restore to snapshot
cub sandbox snapshot restore "before-refactor"

# Delete snapshot
cub sandbox snapshot delete "before-refactor"

# Fork sandbox from snapshot
cub sandbox fork --from "before-refactor" --name "experiment-b"
```

### Automatic Snapshots

Configure automatic snapshots at key points:

```json
{
  "sandbox": {
    "snapshots": {
      "auto_on_task_start": true,
      "auto_on_task_complete": false,
      "max_auto_snapshots": 5,
      "retention": "24h"
    }
  }
}
```

### Provider Support

| Provider | Snapshots | Notes |
|----------|-----------|-------|
| Docker | Limited | Can commit container, but slow |
| Sprites.dev | Full | Native snapshot support |
| Modal | Full | File system snapshots |
| Firecracker | Full | microVM snapshots |

---

## Pre-warming (Latency Optimization)

Inspired by Ramp: "warming sandboxes during prompt typing reduced latency to local development levels"

### The Problem

Sandbox startup adds latency:
- Docker: ~2-5s (pull image, create container, copy files)
- Cloud VMs: ~30-60s (provision, boot, sync)

This friction discourages sandbox use.

### Pre-warming Strategy

Start preparing the sandbox before the user needs it:

```
User starts typing    Sandbox warming     User hits enter    Sandbox ready
      │                    │                    │                │
      ▼                    ▼                    ▼                ▼
    ─────────────────────────────────────────────────────────────>
      │                    │                    │                │
      │    [detect intent] │   [warm sandbox]   │  [instant]     │
      │         1s         │       3-5s         │     0s         │
```

### Warming Triggers

1. **Explicit flag presence** - User types `cub run --sandbox`
2. **Configuration default** - Sandbox mode is default in config
3. **Project detection** - `.cub/sandbox-default` file exists
4. **Heuristic** - Long-running task likely needs sandbox

### Warming Implementation

```bash
# lib/sandbox/prewarm.sh

# Background warming daemon
sandbox_prewarm_daemon() {
  local project_dir=$1
  local provider=$2

  # Create sandbox in background
  local sandbox_id
  sandbox_id=$(sandbox_provider_start "$project_dir" '{"detached": true}')

  # Store for quick attachment
  echo "$sandbox_id" > ".cub-sandbox/prewarmed"

  # Keep warm for N minutes, then cleanup
  (
    sleep ${CUB_PREWARM_TTL:-300}
    if [[ -f ".cub-sandbox/prewarmed" ]]; then
      sandbox_provider_cleanup "$sandbox_id"
      rm -f ".cub-sandbox/prewarmed"
    fi
  ) &
}

# Check for prewarmed sandbox
sandbox_get_prewarmed() {
  if [[ -f ".cub-sandbox/prewarmed" ]]; then
    local sandbox_id
    sandbox_id=$(cat ".cub-sandbox/prewarmed")

    # Verify still running
    if sandbox_provider_status "$sandbox_id" | jq -e '.status == "running"' > /dev/null; then
      rm ".cub-sandbox/prewarmed"  # Claim it
      echo "$sandbox_id"
      return 0
    fi
  fi
  return 1
}

# Modified start that checks for prewarmed first
sandbox_start_smart() {
  local project_dir=$1
  local options=$2

  # Check for prewarmed sandbox
  local prewarmed
  if prewarmed=$(sandbox_get_prewarmed); then
    log_event "sandbox_prewarmed_used" "id=$prewarmed"
    echo "$prewarmed"
    return 0
  fi

  # No prewarmed, start fresh
  sandbox_provider_start "$project_dir" "$options"
}
```

### Pre-warming Configuration

```json
{
  "sandbox": {
    "prewarm": {
      "enabled": true,
      "trigger": "flag_detected",
      "ttl": 300,
      "provider": "docker"
    }
  }
}
```

### Provider-Specific Pre-warming

**Docker:**
- Keep base image pulled and ready
- Pre-create volume with project copy
- Warm container in paused state

**Sprites.dev:**
- Keep warm VM in pool
- Pre-sync project files
- Use regional locality

---

## Supported Providers

### 1. Docker (Local)

**Status:** Primary implementation
**Best for:** Local development, CI/CD, quick iterations

```bash
cub run --sandbox --provider docker
cub run --sandbox  # Default if Docker available
```

Features:
- Full filesystem isolation
- Network isolation
- Resource limits (memory, CPU, PIDs)
- Security hardening (capabilities, seccomp)
- Fast startup (~2s)
- No external dependencies beyond Docker

Limitations:
- Local resources only
- Same architecture as host
- Docker must be installed

### 2. Sprites.dev (Cloud)

**Status:** Future implementation
**Best for:** Long-running jobs, heavy workloads, team sharing

[Sprites.dev](https://sprites.dev) from the makers of Fly.io provides cloud-based disposable VMs.

```bash
cub run --sandbox --provider sprites
cub run --sandbox --provider sprites --machine-size large
```

Features:
- True VM isolation (not containers)
- Scales beyond local resources
- Persistent snapshots
- Team collaboration (share sandbox state)
- No local Docker required
- GPU support

Limitations:
- Requires Sprites.dev account
- Network latency for output
- Cost per usage

### 3. Future Providers

Potential additional providers:

| Provider | Type | Use Case |
|----------|------|----------|
| **Firecracker** | Local microVM | Stronger isolation than Docker |
| **Fly.io Machines** | Cloud VM | Alternative cloud option |
| **AWS CodeBuild** | Cloud | Enterprise/AWS shops |
| **GitHub Codespaces** | Cloud | GitHub-integrated workflows |
| **Local chroot** | Local | Minimal deps, Linux only |
| **nsjail** | Local | Google's sandboxing tool |

## Unified CLI Interface

Provider-agnostic commands:

```bash
# Run in sandbox (auto-detect or specify provider)
cub run --sandbox
cub run --sandbox --provider docker
cub run --sandbox --provider sprites

# Common options (work across providers)
cub run --sandbox --no-network
cub run --sandbox --memory 4g
cub run --sandbox --timeout 2h

# Sandbox management
cub sandbox logs [--follow]
cub sandbox status
cub sandbox diff
cub sandbox export [--path ./output]
cub sandbox apply
cub sandbox stop
cub sandbox clean

# Provider-specific options via passthrough
cub run --sandbox --provider docker --provider-opts '{"image": "cub:dev"}'
cub run --sandbox --provider sprites --provider-opts '{"region": "iad", "size": "large"}'

# List available providers
cub sandbox providers
```

## Provider Detection & Selection

```bash
# lib/sandbox/detect.sh

detect_sandbox_provider() {
  local requested=${1:-auto}

  case "$requested" in
    auto)
      # Priority order
      if command -v docker &>/dev/null && docker info &>/dev/null; then
        echo "docker"
      elif sprites_authenticated; then
        echo "sprites"
      else
        echo "none"
      fi
      ;;
    docker)
      if ! command -v docker &>/dev/null; then
        error "Docker not installed"
        return 1
      fi
      echo "docker"
      ;;
    sprites)
      if ! sprites_authenticated; then
        error "Sprites.dev not configured. Run: sprites auth login"
        return 1
      fi
      echo "sprites"
      ;;
    *)
      error "Unknown provider: $requested"
      return 1
      ;;
  esac
}
```

## Standardized Output Structure

All providers write to the same structure:

```
.cub-sandbox/
├── provider              # Which provider is active
├── sandbox_id            # Provider-specific ID
├── status.json           # Standardized status
├── cub.log               # JSONL event log
├── stdout.log            # Raw stdout
├── stderr.log            # Raw stderr
├── changes.patch         # Cumulative diff
└── artifacts/            # Per-task artifacts
    └── task-123/
        ├── summary.md
        └── changes.patch
```

## Provider: Docker (Detailed)

### Implementation

```bash
# lib/sandbox/providers/docker.sh

source "${CUB_LIB}/sandbox/interface.sh"

DOCKER_PROVIDER_NAME="docker"

docker_provider_init() {
  if ! command -v docker &>/dev/null; then
    error "Docker not installed"
    return 1
  fi

  if ! docker info &>/dev/null; then
    error "Docker daemon not running"
    return 1
  fi

  return 0
}

docker_provider_start() {
  local project_dir=$1
  local options=$2

  local sandbox_id="cub-sandbox-$(date +%s)"
  local memory=$(echo "$options" | jq -r '.memory // "4g"')
  local cpus=$(echo "$options" | jq -r '.cpus // 2')
  local network=$(echo "$options" | jq -r '.network // true')
  local image=$(echo "$options" | jq -r '.image // "cub:latest"')

  # Create volume and copy project
  docker volume create "${sandbox_id}_work"
  docker run --rm \
    -v "${project_dir}:/source:ro" \
    -v "${sandbox_id}_work:/dest" \
    alpine sh -c "cp -a /source/. /dest/"

  # Build run command
  local docker_cmd=(
    docker run
    --name "$sandbox_id"
    --detach
    -v "${sandbox_id}_work:/project"
    -v "$(pwd)/.cub-sandbox:/output"
    --memory "$memory"
    --cpus "$cpus"
    --security-opt no-new-privileges
  )

  if [[ "$network" == "false" ]]; then
    docker_cmd+=(--network none)
  fi

  docker_cmd+=("$image" run)

  # Launch
  "${docker_cmd[@]}"

  echo "$sandbox_id"
}

docker_provider_status() {
  local sandbox_id=$1

  local state
  state=$(docker inspect "$sandbox_id" --format '{{json .State}}')

  local stats
  stats=$(docker stats "$sandbox_id" --no-stream --format '{{json .}}')

  jq -n \
    --arg id "$sandbox_id" \
    --arg provider "docker" \
    --argjson state "$state" \
    --argjson stats "$stats" \
    '{
      id: $id,
      provider: $provider,
      status: $state.Status,
      started_at: $state.StartedAt,
      resources: {
        memory_used: $stats.MemUsage,
        cpu_percent: $stats.CPUPerc
      }
    }'
}

docker_provider_logs() {
  local sandbox_id=$1
  local follow=${2:-false}

  if [[ "$follow" == "true" ]]; then
    docker logs -f "$sandbox_id" 2>&1
  else
    docker logs "$sandbox_id" 2>&1
  fi
}

docker_provider_diff() {
  local sandbox_id=$1
  docker exec "$sandbox_id" git diff HEAD 2>/dev/null || cat ".cub-sandbox/changes.patch"
}

docker_provider_export() {
  local sandbox_id=$1
  local dest=$2

  mkdir -p "$dest"
  docker exec "$sandbox_id" sh -c '
    git diff --name-only HEAD | while read f; do
      mkdir -p "/export/$(dirname "$f")"
      cp "$f" "/export/$f"
    done
  '
  docker cp "${sandbox_id}:/export/." "$dest/"
}

docker_provider_cleanup() {
  local sandbox_id=$1
  docker rm -f "$sandbox_id" 2>/dev/null || true
  docker volume rm "${sandbox_id}_work" 2>/dev/null || true
}

docker_provider_capabilities() {
  cat <<EOF
network_isolation:true
resource_limits:true
snapshots:false
remote:false
gpu:false
EOF
}
```

### Docker Images

```
cub:latest          # Full image with all harnesses
cub:claude          # Claude Code only
cub:minimal         # Just cub, user installs harness
cub:dev             # With development tools
```

## Provider: Sprites.dev (Detailed)

### Implementation

```bash
# lib/sandbox/providers/sprites.sh

source "${CUB_LIB}/sandbox/interface.sh"

SPRITES_PROVIDER_NAME="sprites"

sprites_provider_init() {
  if ! command -v sprites &>/dev/null; then
    error "Sprites CLI not installed. See: https://sprites.dev/docs/install"
    return 1
  fi

  if ! sprites auth status &>/dev/null; then
    error "Not authenticated. Run: sprites auth login"
    return 1
  fi

  return 0
}

sprites_provider_start() {
  local project_dir=$1
  local options=$2

  local size=$(echo "$options" | jq -r '.size // "medium"')
  local region=$(echo "$options" | jq -r '.region // "iad"')
  local timeout=$(echo "$options" | jq -r '.timeout // "4h"')

  # Create sprite with project uploaded
  local sandbox_id
  sandbox_id=$(sprites create \
    --size "$size" \
    --region "$region" \
    --timeout "$timeout" \
    --upload "$project_dir" \
    --command "cub run" \
    --json | jq -r '.id')

  echo "$sandbox_id"
}

sprites_provider_status() {
  local sandbox_id=$1
  sprites status "$sandbox_id" --json
}

sprites_provider_logs() {
  local sandbox_id=$1
  local follow=${2:-false}

  if [[ "$follow" == "true" ]]; then
    sprites logs "$sandbox_id" --follow
  else
    sprites logs "$sandbox_id"
  fi
}

sprites_provider_diff() {
  local sandbox_id=$1
  sprites exec "$sandbox_id" -- git diff HEAD
}

sprites_provider_export() {
  local sandbox_id=$1
  local dest=$2
  sprites download "$sandbox_id" --changed-only --dest "$dest"
}

sprites_provider_cleanup() {
  local sandbox_id=$1
  sprites destroy "$sandbox_id" --force
}

sprites_provider_capabilities() {
  cat <<EOF
network_isolation:true
resource_limits:true
snapshots:true
remote:true
gpu:true
EOF
}
```

### Sprites-Specific Features

Features unique to Sprites that could be exposed:

```bash
# Snapshot current state
cub sandbox snapshot --name "before-refactor"

# Restore from snapshot
cub sandbox restore --snapshot "before-refactor"

# Share sandbox with team
cub sandbox share --user teammate@example.com

# Clone sandbox for A/B testing
cub sandbox clone --as "experiment-b"
```

## Configuration

```json
{
  "sandbox": {
    "default_provider": "auto",
    "providers": {
      "docker": {
        "image": "cub:latest",
        "memory": "4g",
        "cpus": 2,
        "security": {
          "no_new_privileges": true,
          "drop_capabilities": true
        }
      },
      "sprites": {
        "size": "medium",
        "region": "iad",
        "org": "my-org"
      }
    },
    "common": {
      "timeout": "4h",
      "network": true,
      "preserve_on_failure": true,
      "auto_cleanup": false
    }
  }
}
```

## Use Cases

### 1. Safe YOLO Mode (Any Provider)

```bash
cub run --sandbox --yolo
cub sandbox diff
cub sandbox apply
```

### 2. Local Quick Iteration (Docker)

```bash
cub run --sandbox --provider docker
# Fast startup, local resources
```

### 3. Long-Running Heavy Job (Sprites)

```bash
cub run --sandbox --provider sprites --provider-opts '{"size": "large"}'
# Cloud resources, survives laptop sleep
```

### 4. CI/CD Pipeline (Docker)

```bash
cub run --sandbox --no-network --timeout 30m
cub sandbox export --path ./artifacts
```

### 5. Team Collaboration (Sprites)

```bash
# Start sandbox
cub run --sandbox --provider sprites

# Share with teammate for debugging
cub sandbox share --user alice@team.com

# They can attach
cub sandbox attach abc123
```

## Acceptance Criteria

### Core (All Providers)
- [ ] `cub run --sandbox` launches isolated execution
- [ ] Provider auto-detection
- [ ] Real-time log streaming with `cub sandbox logs`
- [ ] Status with `cub sandbox status`
- [ ] Diff viewing with `cub sandbox diff`
- [ ] Change export with `cub sandbox export`
- [ ] Change application with `cub sandbox apply`
- [ ] Cleanup with `cub sandbox clean`
- [ ] Standardized output structure

### Docker Provider
- [ ] Full implementation of provider interface
- [ ] Network isolation option
- [ ] Resource limits (memory, CPU)
- [ ] Security hardening
- [ ] Official Docker images

### Sprites Provider
- [ ] Full implementation of provider interface
- [ ] Authentication flow
- [ ] Remote log streaming
- [ ] Snapshot support (provider-specific)

### Integration
- [ ] Works with all harnesses
- [ ] Integration with dashboard
- [ ] Provider capability detection

## Future Enhancements

- Additional providers (Firecracker, Fly.io, etc.)
- Web dashboard for sandbox monitoring
- Snapshot/restore (providers that support it)
- Multi-sandbox coordination
- Cost estimation for cloud providers
- Automatic provider selection based on workload
- Sandbox templates per project type

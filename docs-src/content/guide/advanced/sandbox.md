# Sandbox Mode

Sandbox mode runs Cub inside a Docker container, providing complete filesystem and network isolation. This is ideal for running untrusted code, testing destructive operations, or ensuring reproducible builds.

## What Sandbox Does

When you run `cub run --sandbox`, Cub:

1. **Creates a Docker volume** - Copies your project to an isolated volume
2. **Starts a container** - Runs cub inside the container
3. **Isolates execution** - Container has limited access to host
4. **Captures changes** - All file changes stay in the container
5. **Reports diff** - Shows what changed when the run completes
6. **Cleans up** - Removes container and volume (unless `--sandbox-keep`)

```
+----------------+     +------------------------+
|   Host System  |     |   Docker Container     |
|                |     |                        |
|  Your Project  | --> |  Copy of Project       |
|                |     |  (isolated volume)     |
|                |     |                        |
|  cub run       | --> |  cub run (inside)      |
|  --sandbox     |     |                        |
+----------------+     +------------------------+
                              |
                              v
                       Changes captured
                       in container only
```

## Enabling Sandbox Mode

### Basic Usage

```bash
# Run in sandbox
cub run --sandbox

# Single task in sandbox
cub run --sandbox --task cub-054

# Stream output from sandbox
cub run --sandbox --stream
```

### Without Network Access

For maximum isolation, disable network access:

```bash
cub run --sandbox --no-network
```

This prevents:

- API calls to external services
- Package installations from internet
- Any network communication

### Keeping the Sandbox

By default, sandboxes are cleaned up after the run. Keep them for inspection:

```bash
cub run --sandbox --sandbox-keep
```

The sandbox ID is saved to `.cub/sandbox.json` for later commands.

## Sandbox Commands

Once a sandbox exists (via `--sandbox-keep`), manage it with:

### View Logs

```bash
# Show all logs
cub sandbox logs

# Follow logs in real-time
cub sandbox logs -f
```

### Check Status

```bash
cub sandbox status
```

Output:

```
Sandbox Status: cub-sandbox-1737120000
+----------+------------------+
| Property | Value            |
+----------+------------------+
| Provider | docker           |
| State    | stopped          |
| Started  | 2026-01-17 10:30 |
| Stopped  | 2026-01-17 10:45 |
| Exit     | 0                |
| Memory   | 1.2GiB / 4GiB    |
+----------+------------------+
```

### View Changes

```bash
cub sandbox diff
```

Shows a git-style unified diff of all changes made in the sandbox.

### Export Changes

```bash
# Export changed files to a directory
cub sandbox export /tmp/sandbox-output

# Export all files (not just changed)
cub sandbox export /tmp/sandbox-output --all
```

### Apply Changes

Copy changes from sandbox back to your project:

```bash
# Preview and confirm
cub sandbox apply

# Skip confirmation
cub sandbox apply -y
```

!!! warning "Overwrites Local Files"
    `cub sandbox apply` overwrites local files with sandbox versions. Review the diff first.

### Clean Up

Remove the sandbox and free resources:

```bash
# With confirmation
cub sandbox clean

# Without confirmation
cub sandbox clean -y
```

## Docker Configuration

### Resource Limits

Default resource limits:

| Resource | Default | Description |
|----------|---------|-------------|
| Memory | 4GB | Maximum container memory |
| CPUs | 2.0 | CPU limit (as fraction of cores) |
| PIDs | 256 | Maximum process count |

### Custom Image

By default, Cub uses `cub:latest`. Specify a custom image:

```json
{
  "sandbox": {
    "image": "my-org/cub-custom:v1"
  }
}
```

### Building the Image

If you need to build the cub image:

```bash
# From the cub repository
docker build -t cub:latest .
```

Or use a pre-built image if available from your organization.

## Security Features

Sandbox mode includes security hardening:

| Feature | Description |
|---------|-------------|
| **no-new-privileges** | Prevents privilege escalation |
| **Network isolation** | Optional network disable |
| **PID limits** | Prevents fork bombs |
| **Memory limits** | Prevents resource exhaustion |
| **Volume isolation** | Project copied, not mounted |

### What Sandbox Protects Against

| Threat | Protection |
|--------|------------|
| File system damage | Changes isolated to container |
| Network attacks | Optional network disable |
| Resource exhaustion | Memory and CPU limits |
| Privilege escalation | Security options enabled |
| Data exfiltration | Network isolation |

### What Sandbox Does NOT Protect Against

| Threat | Notes |
|--------|-------|
| Docker escape vulnerabilities | Keep Docker updated |
| Secrets in environment | Still passed to container |
| Host Docker access | Container can't access host Docker |

## Use Cases

### Testing Destructive Operations

```bash
# Task that might delete files
cub run --sandbox --task cleanup-task
```

If something goes wrong, just clean up the sandbox.

### Running Untrusted Code

```bash
# Generated code that hasn't been reviewed
cub run --sandbox --no-network
```

Network isolation prevents unexpected external calls.

### Reproducible Builds

```bash
# Ensure consistent environment
cub run --sandbox --task build-task
```

Container provides identical environment each time.

### Safe Experimentation

```bash
# Try experimental changes
cub run --sandbox --sandbox-keep

# Review results
cub sandbox diff

# If good, apply changes
cub sandbox apply

# If bad, discard
cub sandbox clean
```

## Workflow Examples

### Review-Before-Apply

```bash
# Run in sandbox, keep for review
cub run --sandbox --sandbox-keep --task cub-054

# Check what changed
cub sandbox diff

# Looks good - apply to project
cub sandbox apply -y

# Clean up
cub sandbox clean -y
```

### Isolated Debugging

```bash
# Run with sandbox for isolation
cub run --sandbox --sandbox-keep --stream --task failing-task

# Check logs
cub sandbox logs

# Inspect container state
docker exec -it cub-sandbox-... /bin/bash

# Clean up when done
cub sandbox clean
```

### Network-Isolated Testing

```bash
# Run without network (safe from external calls)
cub run --sandbox --no-network --task api-task

# Task will fail if it tries to make network calls
# This verifies the task doesn't have hidden dependencies
```

## Troubleshooting

### Docker Not Available

```
Docker is not available.
Please install Docker and ensure the daemon is running.
```

**Solution**: Install Docker Desktop or Docker Engine and start the daemon.

### Image Not Found

```
Unable to find image 'cub:latest' locally
```

**Solution**: Build the cub image or configure a custom image in config.

### Sandbox Not Found

```
No active sandbox found
```

**Solution**: Start a sandbox with `--sandbox-keep` or specify the sandbox ID.

### Out of Memory

```
Container killed: out of memory
```

**Solution**: Increase memory limit in config or reduce task scope.

### Network Calls Failing

If tasks fail with network errors when using `--no-network`:

- Expected behavior for network-dependent tasks
- Use without `--no-network` if network is required
- Or mock network dependencies

## Performance Considerations

Sandbox mode adds overhead:

| Operation | Overhead |
|-----------|----------|
| Startup | ~2-5 seconds (container creation) |
| File copy | Depends on project size |
| Execution | ~5-10% slower than native |
| Cleanup | ~1-2 seconds |

For quick iterations, consider native execution. Use sandbox for:

- Final testing
- Untrusted operations
- Reproducibility requirements

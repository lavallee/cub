# Cub Alpha Release Notes

**Status:** Alpha (v0.30+)
**Last Updated:** February 2026

This document describes known limitations, stability concerns, and experimental features in the Cub alpha release.

## ⚠️ Stability & Breaking Changes

### What to Expect

Cub is actively under development. The following may change in future releases:

- **CLI commands** may be renamed or reorganized
- **Configuration file formats** may change
- **Task backend schemas** may be updated (migrations will be provided)
- **API contracts** between components may evolve
- **Feature availability** may be restricted based on backend

### Backup Your Work

Before using Cub in a production environment:

1. **Ensure git history is clean** - Cub commits task completion. Corrupted history can lead to data loss.
2. **Test in a staging branch first** - Run `cub` on a non-critical branch before deploying to main.
3. **Monitor git state** - Verify branches, commits, and reflog after each session.
4. **Keep task state backups** - The `.cub/` directory contains all task metadata. Back it up regularly.

## Known Limitations

### Backend Limitations

#### JSONL Backend (Default, Recommended for Alpha)

- ✅ Suitable for alpha testing
- ✅ No external dependencies
- ✅ Git-based persistence via cub-sync
- ⚠️ Manual merge conflicts if multiple team members edit tasks offline
- ⚠️ No real-time conflict detection

#### Beads Backend

- ✅ Advanced task management features
- ⚠️ Adds external CLI dependency
- ⚠️ Beads is actively developed; breaking changes possible
- ❌ Beads git support is experimental

#### JSON Backend

- ✅ Legacy support (v0.20 and earlier)
- ⚠️ Not recommended for new projects
- ⚠️ Auto-migration to JSONL not yet implemented

### Planning Pipeline `[EXPERIMENTAL]`

The `cub plan` commands (orient, architect, itemize) are under active development. The full pipeline can be run with `cub plan run`, which executes orient, architect, and itemize in sequence. Use `cub stage` to import planned tasks into the task backend.

**Known issues:**

- Command output format may change
- Error handling is incomplete
- Some edge cases not covered
- `cub interview` lacks refinement options

**Recommendation:** Use for exploration; review all generated tasks before running execution loop.

### Dashboard `[EXPERIMENTAL]`

The integrated dashboard is a new feature with rough edges.

**Known issues:**

- Slow with 1000+ tasks
- Kanban column calculations may be incorrect with complex dependencies
- Real-time updates lag when running parallel tasks
- Export functionality not yet implemented
- Mobile view not optimized

**Recommendation:** Use for status visibility; don't rely on metrics for decision-making yet.

### Task State Sync `[EXPERIMENTAL]`

Git-based sync to `cub-sync` branch enables persistence but has limitations.

**Known issues:**

- No real-time conflict detection when multiple users edit tasks
- Merge conflicts use "last-write-wins" strategy (no semantic merge)
- Large task files (1000+ tasks) may hit git performance limits
- Sync failures are logged but don't block task execution
- `cub sync pull` doesn't merge gracefully (hard replace)

**Recommendation:** Safe for single-user workflows; use caution with teams.

### Git Integration

**Potential issues:**

- Auto-branch creation may fail with unusual remote configs
- Commit messages may be too short on large refactors
- Force push is dangerous; use `--require-clean` to be safe
- Worktree mode (`--worktree`) is not tested on Windows

## Security Considerations for Alpha Users

### 1. Permissions Skipping

Cub includes flags that bypass git safety hooks:

```bash
cub run --no-verify      # Skips pre-commit hooks
cub run --no-gpg-sign    # Skips GPG signing
```

**Risk:** Unsigned commits, bypassed validation
**Mitigation:** Use only in private/staging repos; enable `require_commit` and `require_tests` in config

### 2. AI Code Execution

Cub runs AI-generated code directly in your environment:

```bash
cub run    # Generates code → commits → can modify files
```

**Risk:** Malicious or broken code execution
**Mitigation:**
- Use in isolated environments first
- Review git diffs before finalizing
- Use `--sandbox` for untrusted workflows
- Keep recovery procedures in place

### 3. Repository Access

Multi-task sessions modify git branches and push to remotes:

```bash
cub run --stream --push   # Creates branch, commits, pushes
```

**Risk:** Leaked credentials, compromised branches
**Mitigation:**
- Use SSH keys with restricted scopes
- Enable branch protection on main
- Use `--use-current-branch` to avoid branch creation
- Monitor git history for unexpected changes

### 4. Task State Storage

Task descriptions are stored in plaintext:

```
.cub/tasks.jsonl       # Unencrypted
cub-sync branch        # Git history, not encrypted
```

**Risk:** Secrets in task descriptions exposed in git history
**Mitigation:**
- Never include API keys, passwords, or PII in task descriptions
- Use environment variables for sensitive config
- Audit task history before pushing to public repos

### 5. Sandbox Isolation

The `--sandbox` mode uses Docker but isn't hardened:

```bash
cub run --sandbox      # Docker container, but not fully isolated
```

**Risk:** Container escape, resource exhaustion
**Mitigation:**
- Use on machines without sensitive data
- Set resource limits in Docker config
- Monitor container logs for suspicious activity
- Don't run untrusted code even in sandbox mode

### 6. Nesting Detection

Cub detects when it is invoked inside another `cub run` session via the `CUB_RUN_ACTIVE` environment variable. This prevents infinite loops and double-tracking. Hooks automatically skip certain operations when nesting is detected.

**Risk:** Bypassed nesting detection if env var is manually unset
**Mitigation:**
- Do not unset `CUB_RUN_ACTIVE` during a `cub run` session
- If hooks appear to double-track, check for env var propagation issues

### 7. Secret Redaction

Task descriptions and ledger entries are stored in plaintext JSONL files. Cub does not perform automatic secret redaction.

**Risk:** Secrets (API keys, tokens, passwords) captured in task descriptions, forensic logs, or ledger entries
**Mitigation:**
- Never include secrets in task descriptions or commit messages
- Use environment variables for sensitive configuration
- Audit `.cub/ledger/` and `.cub/tasks.jsonl` before pushing to public repos
- Review forensic logs in `.cub/ledger/forensics/` for accidental secret capture

## Experimental Features Matrix

| Feature | Status | Stability | Recommendation |
|---------|--------|-----------|-----------------|
| Task creation/management | Stable | ✅ Production-ready | Use with confidence |
| Run loop (execution) | Stable | ✅ Production-ready | Use with confidence |
| Service layer (`core/services/`) | Stable | ✅ Production-ready | New features should use services |
| Symbiotic workflow (hooks) | Stable | ✅ Production-ready | Recommended for direct sessions |
| JSONL backend | Beta | ⚠️ Generally safe | Recommended for alpha |
| Beads backend | Stable | ✅ Try it | Optional, external deps |
| JSON backend | Deprecated | ❌ Don't use | Use JSONL instead |
| Planning pipeline (orient/architect/itemize) | Experimental | ❓ Very rough | Exploration only |
| Dashboard (Kanban) | Experimental | ❓ Rough edges | Status visibility only |
| Task sync (cub-sync) | Experimental | ⚠️ Single-user safe | Use cautiously |
| Tool runtime (HTTP/CLI/MCP adapters) | Experimental | ❓ API may change | Early adopters only |
| Hooks system | Beta | ⚠️ Generally safe | Use with testing |
| Streaming output | Stable | ✅ Works well | Safe to use |
| Budget management | Stable | ✅ Works well | Safe to use |
| Ledger (verify/learn/retro/release) | Beta | ⚠️ Generally safe | Use for insights |
| Suggestions engine | Beta | ⚠️ Generally safe | Helpful for task discovery |
| Session reconciliation | Beta | ⚠️ Generally safe | Use for post-hoc tracking |

## Reporting Issues

Please report bugs and stability concerns:

1. **Reproduce** the issue in a fresh project
2. **Capture** git history and task state (`.cub/` directory)
3. **Open issue** on GitHub with:
   - Cub version (`cub version`)
   - Python version (`python --version`)
   - OS and platform
   - Reproduction steps
   - Error logs (`.local/share/cub/logs/`)

Sensitive information (API keys, private repo URLs) should be redacted.

## Timeline

**Alpha Phase (Current):**
- Focus on stability and core features
- Breaking changes may occur with migration support
- Expect frequent updates

**Beta Phase (Q2 2026):**
- Stabilized APIs
- Reduced breaking changes
- All experimental features documented

**1.0 Release (Q3+ 2026):**
- Stable APIs and guarantees
- Full backwards compatibility

## Feedback

Cub is shaped by user feedback. Please share:

- Feature requests
- Stability concerns
- Documentation gaps
- Integration ideas

Open an issue or discussion on GitHub. Alpha users help make Cub better for everyone.

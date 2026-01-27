# Shell Installer Best Practices Analysis

**Date:** 2026-01-27
**Sources Analyzed:**
1. **uv installer** (Astral.sh) - https://astral.sh/uv/install.sh
2. **rustup installer** (Rust) - https://raw.githubusercontent.com/rust-lang/rustup/master/rustup-init.sh
3. **nvm installer** (Node Version Manager) - https://raw.githubusercontent.com/nvm-sh/nvm/master/install.sh

---

## Executive Summary

All three installers demonstrate production-grade defensive programming with distinct philosophies:

- **rustup**: Most security-hardened (TLS enforcement, cipher suite control, ELF inspection)
- **uv**: Most ergonomic (color output, verbose/quiet modes, extensive platform support)
- **nvm**: Most idempotent (safe re-runs, profile guard checks, git-based updates)

---

## 1. Shell Compatibility Techniques

### Common Ground: POSIX Targeting with Extensions

All three scripts target POSIX sh while strategically using `local` (non-POSIX):

| Script | Shebang | `local` Handling | Shell Detection |
|--------|---------|------------------|-----------------|
| **rustup** | `#!/bin/sh` | `has_local 2>/dev/null \|\| alias local=typeset` | `is_zsh()` for word-splitting |
| **uv** | `#!/bin/sh` | Same as rustup | None (pure POSIX) |
| **nvm** | `#!/usr/bin/env bash` | Native bash support | Enforces bash, rejects zsh |

**Key Pattern:**
```bash
# Detect local support, fallback to typeset for ksh
has_local() {
    local _has_local
}
has_local 2>/dev/null || alias local=typeset
```

**NVM's Enforcement Approach:**
```bash
if [ -z "${BASH_VERSION}" ] || [ -n "${ZSH_VERSION}" ]; then
  echo >&2 'Error: pipe the install script to `bash`'
  exit 1
fi
```

### Recommendation for Cub
- **Use `#!/bin/sh` shebang** for POSIX compatibility
- **Add `local` fallback** for ksh variants
- **Add shellcheck directives**: `# shellcheck shell=dash` and `# shellcheck disable=SC2039`
- **Document bash requirement** if using bash-specific features (arrays, `[[`, `read -r`)

---

## 2. Error Handling Patterns

### Set Strict Mode

| Script | `-e` | `-u` | `-o pipefail` | Philosophy |
|--------|------|------|---------------|------------|
| **rustup** | ❌ | ✅ | ❌ | Explicit checks via `ensure()` |
| **uv** | ❌ | ✅ | ❌ | Same as rustup |
| **nvm** | ❌ | ❌ | ❌ | Manual validation per operation |

**Why no `set -e`?** All scripts avoid `set -e` because:
1. Unpredictable behavior with command substitution
2. Doesn't catch errors in pipelines without `pipefail`
3. Harder to provide helpful error messages

**Rustup's `ensure()` Wrapper:**
```bash
ensure() {
    if ! "$@"; then
        err "command failed: $*"
        exit 1
    fi
}

# Usage
ensure mktemp -d
ensure chmod u+x "$file"
```

**Uv's Similar Pattern:**
```bash
ensure() {
    if ! "$@"; then err "command failed: $*"; fi
}
```

**NVM's Inline Checks:**
```bash
command git init "${INSTALL_DIR}" || {
  nvm_echo >&2 'Failed to initialize nvm repo. Please report this!'
  exit 2
}
```

### Error Reporting

All three use colored error output:

**Rustup/Uv (tput-based):**
```bash
err() {
    if [ "0" = "$PRINT_QUIET" ]; then
        local red reset
        red=$(tput setaf 1 2>/dev/null || echo '')
        reset=$(tput sgr0 2>/dev/null || echo '')
        say "${red}ERROR${reset}: $1" >&2
    fi
    exit 1
}
```

**NVM (command printf):**
```bash
nvm_echo() {
    command printf %s\\n "$*" 2>&1
}
```

### Recommendation for Cub
1. **Use `set -u`** to catch undefined variables
2. **Wrap critical commands with `ensure()`**
3. **Use distinct exit codes** for different failure modes (like NVM: 1, 2, 3)
4. **Add `ignore()` wrapper** for cleanup operations where failure is acceptable
5. **Color errors with tput fallback** to plain text

---

## 3. Security Practices

### HTTPS Enforcement

| Script | HTTPS Only | TLS Version | Cipher Suites | Checksum Verification |
|--------|------------|-------------|---------------|----------------------|
| **rustup** | ✅ | TLS 1.2+ | Hardcoded (Firefox 68 ESR) | ❌ (relies on HTTPS) |
| **uv** | ✅ | Default | Default | ✅ (sha256/sha512) |
| **nvm** | ✅ | Default | Default | ❌ (relies on HTTPS) |

**Rustup's Hardened curl Invocation:**
```bash
curl $_retry --proto '=https' --tlsv1.2 \
  --ciphers "TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256:..." \
  -fsSL "$url"
```

**Uv's Checksum Verification:**
```bash
verify_checksum() {
    local _file="$1"
    local _checksum_style="$2"
    local _checksum_value="$3"

    case "$_checksum_style" in
        sha256)
            if ! check_cmd sha256sum; then
                say "skipping sha256 checksum (requires sha256sum)"
                return 0
            fi
            _calculated=$(sha256sum -b "$_file" | awk '{printf $1}')
            if [ "$_calculated" != "$_checksum_value" ]; then
                err "checksum mismatch"
            fi
            ;;
    esac
}
```

### Snap curl Vulnerability Detection

Both rustup and uv check for broken snap curl:

```bash
_curl_path=$(command -v curl)
if echo "$_curl_path" | grep "/snap/" > /dev/null 2>&1; then
    err "curl installed with snap cannot be used to install..."
    exit 1
fi
```

**Context:** Snap-packaged curl has network isolation bugs that break HTTPS downloads.

### Custom Repository Warnings (NVM)

```bash
if [ "${NVM_GITHUB_REPO}" != 'nvm-sh/nvm' ]; then
  { nvm_echo >&2 "$(cat)" ; } << EOF
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE REPO IDENTIFICATION HAS CHANGED!
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
```

This warns users when installing from forks or mirrors.

### Recommendation for Cub
1. **Add checksum verification** for downloaded binaries (like uv)
2. **Enforce TLS 1.2+ with `--proto '=https' --tlsv1.2`** (like rustup)
3. **Detect snap curl** and error out
4. **Warn on custom GitHub repos** if downloading from configurable sources
5. **Consider GPG signature verification** for maximum security (none of the three do this)

---

## 4. Platform/Architecture Detection

### Comprehensive Detection Logic

**Rustup's Approach (most thorough):**
```bash
_ostype="$(uname -s)"
_cputype="$(uname -m)"
_clibtype="gnu"

# Handle macOS Rosetta 2
if [ "$_ostype" = Darwin ]; then
    if sysctl hw.optional.arm64 2>&1 | grep -q ': 1$'; then
        _cputype=arm64
    fi
fi

# Detect musl vs glibc
if ldd --version 2>&1 | grep -q 'musl'; then
    _clibtype="musl"
fi

# ELF binary inspection for bitness
get_bitness() {
    local _current_exe_head
    _current_exe_head=$(head -c 5 "$_current_exe")
    if [ "$_current_exe_head" = "$(printf '\177ELF\001')" ]; then
        echo 32
    elif [ "$_current_exe_head" = "$(printf '\177ELF\002')" ]; then
        echo 64
    fi
}
```

**Key Techniques:**
1. **Rosetta 2 detection** via `sysctl hw.optional.arm64`
2. **libc detection** via `ldd --version | grep musl`
3. **ELF header parsing** to detect 32 vs 64-bit without `file` command
4. **Android detection** via `uname -o`

**Uv's Similar Approach:**
```bash
get_architecture() {
    local _ostype="$(uname -s)"
    local _cputype="$(uname -m)"
    local _clibtype="gnu"

    if [ "$_ostype" = Linux ]; then
        if [ "$(uname -o)" = Android ]; then
            _ostype=Android
        fi
        if ldd --version 2>&1 | grep -q 'musl'; then
            _clibtype="musl-dynamic"
        fi
    fi

    # Normalize architecture names
    case "$_cputype" in
        x86_64|x86-64|x64|amd64)
            _cputype=x86_64
            ;;
        aarch64|arm64)
            _cputype=aarch64
            ;;
    esac
}
```

### NVM's Simpler Approach

NVM only detects shell profiles based on `$SHELL`:

```bash
if [ "${SHELL#*bash}" != "$SHELL" ]; then
  DETECTED_PROFILE="$HOME/.bashrc"
elif [ "${SHELL#*zsh}" != "$SHELL" ]; then
  DETECTED_PROFILE="${ZDOTDIR:-${HOME}}/.zshrc"
fi
```

### Recommendation for Cub
1. **Implement comprehensive OS/arch detection** (copy rustup's approach)
2. **Handle musl vs glibc** if distributing static binaries
3. **Normalize architecture names** (`x86_64`, `x86-64`, `amd64` → `x86_64`)
4. **Detect Rosetta 2** on macOS ARM
5. **Use parameter expansion** for shell detection: `${SHELL#*bash}` vs `echo $SHELL | grep`

---

## 5. Privilege Handling

### No Sudo Philosophy

**All three scripts avoid sudo entirely.** They install to user-writable directories:

| Script | Default Install Location | Override Env Var |
|--------|--------------------------|------------------|
| **rustup** | `$HOME/.cargo/bin` | `CARGO_HOME` |
| **uv** | `$XDG_BIN_HOME` → `$HOME/.local/bin` | `UV_INSTALL_DIR` |
| **nvm** | `$HOME/.nvm` or `$XDG_CONFIG_HOME/nvm` | `NVM_DIR` |

**Why No Sudo?**
1. Safer (no system-wide modifications)
2. No password prompts (better for automation)
3. Easier to uninstall (just `rm -rf`)
4. Per-user installations don't conflict

### Execute Permission Checks

**Rustup:**
```bash
ensure chmod u+x "$_file"
if [ ! -x "$_file" ]; then
    err "Cannot execute $_file (likely mounted /tmp as noexec)."
    exit 1
fi
```

### HOME Directory Handling (Uv)

Uv includes a fallback for systems where `$HOME` is unset:

```bash
get_home() {
    if [ -n "${HOME:-}" ]; then
        echo "$HOME"
    elif [ -n "${USER:-}" ]; then
        getent passwd "$USER" | cut -d: -f6
    else
        getent passwd "$(id -un)" | cut -d: -f6
    fi
}
```

This handles minimal container environments and some Linux distributions that don't set `HOME`.

### Recommendation for Cub
1. **Never use sudo** - install to `~/.local/bin` or `~/.cub/bin`
2. **Check execute permissions** after download
3. **Handle missing `$HOME`** using `getent passwd` fallback
4. **Detect noexec `/tmp`** and use alternate tmpdir
5. **Respect XDG Base Directory** specification

---

## 6. Idempotency Features

### NVM: Best-in-Class Idempotency

NVM is the most idempotent installer:

**Existing Installation Detection:**
```bash
if [ -d "$INSTALL_DIR/.git" ]; then
  nvm_echo "=> nvm is already installed, trying to update using git"
  command git -C "$INSTALL_DIR" fetch --tags origin
  command git -C "$INSTALL_DIR" checkout "$(git describe --tags --abbrev=0 origin)"
elif [ -f "$INSTALL_DIR/nvm.sh" ]; then
  nvm_echo "=> nvm is already installed, trying to update the script"
  nvm_download -s "$NVM_SOURCE_URL" -o "$INSTALL_DIR/nvm.sh"
fi
```

**Profile Sourcing Guards:**
```bash
if ! command grep -qc '/nvm.sh' "$NVM_PROFILE"; then
  command printf "${SOURCE_STR}" >> "$NVM_PROFILE"
else
  nvm_echo "=> nvm source string already in ${NVM_PROFILE}"
fi
```

### Rustup/Uv: Update-in-Place

Both rustup and uv re-download and overwrite on re-run. They rely on the main binary's update logic for idempotency.

### Recommendation for Cub
1. **Detect existing installations** and update instead of failing
2. **Guard profile modifications** - check if sourcing line already exists
3. **Use git remotes** if installing via git clone
4. **Preserve user configuration** on upgrade
5. **Print update vs fresh install messages**

---

## 7. User Communication

### Progress & Verbosity

| Script | Quiet Mode | Verbose Mode | Colors | Progress Indicators |
|--------|------------|--------------|--------|---------------------|
| **rustup** | `--quiet`, `RUSTUP_QUIET` | ❌ | ✅ (tput) | Basic text |
| **uv** | `--quiet`, `UV_PRINT_QUIET` | `--verbose`, `UV_PRINT_VERBOSE` | ✅ (tput) | Download progress |
| **nvm** | ❌ | ❌ | ❌ | `=>` prefix for status |

**Uv's Dual Verbosity Control:**
```bash
say() {
    if [ "0" = "$PRINT_QUIET" ]; then
        echo "$1"
    fi
}

say_verbose() {
    if [ "1" = "$PRINT_VERBOSE" ]; then
        echo "$1"
    fi
}

warn() {
    if [ "0" = "$PRINT_QUIET" ]; then
        local red reset
        red=$(tput setaf 1 2>/dev/null || echo '')
        reset=$(tput sgr0 2>/dev/null || echo '')
        say "${red}WARN${reset}: $1" >&2
    fi
}
```

**Rustup's ANSI Detection:**
```bash
_ansi_escapes_are_valid=false
if [ -t 2 ]; then
    if [ "${TERM+set}" = 'set' ]; then
        case "$TERM" in
            xterm*|rxvt*|urxvt*|linux*|vt*)
                _ansi_escapes_are_valid=true
            ;;
        esac
    fi
fi
```

### NVM's Simple Prefix System

```bash
nvm_echo "=> Downloading nvm from git to '$INSTALL_DIR'"
nvm_echo "=> Compressing and cleaning up git repository"
```

Uses `=>` as a consistent status indicator.

### Recommendation for Cub
1. **Support `--quiet` and `--verbose` flags** (env vars too)
2. **Use tput for colors** with fallback to plain text
3. **Detect terminal capabilities** before using colors
4. **Redirect errors to stderr** (`>&2`)
5. **Add spinner/progress bar** for long downloads (optional)
6. **Use consistent prefixes** (`[INFO]`, `[WARN]`, `[ERROR]`)

---

## 8. Rollback/Cleanup on Failure

### Temporary File Handling

All three create temp directories and attempt cleanup:

**Rustup:**
```bash
local _dir
if ! _dir="$(ensure mktemp -d)"; then
    exit 1
fi
# ... download and extract ...
ignore rm "$_file"
ignore rmdir "$_dir"
```

**Uv:**
```bash
_dir="$(ensure mktemp -d)" || return 1
local _file="$_dir/input$_zip_ext"
# ... process ...
ignore rm -rf "$_dir"
```

**NVM:**
```bash
nvm_echo "=> Compressing and cleaning up git repository"
command git reflog expire --expire=now --all
command git gc --auto --aggressive --prune=now
```

### Failure States

- **Rustup/Uv**: Leave temp files on failure (aids debugging)
- **NVM**: Aggressive git pruning after successful clone

### No Trap Handlers

**None of the three scripts use `trap` for cleanup.** They rely on:
1. `ignore rm` at script end
2. OS-level `/tmp` cleanup on reboot
3. User intervention on failure

### Recommendation for Cub
1. **Use `trap 'cleanup' EXIT`** to ensure temp file removal
2. **Keep failed downloads** for debugging (with message telling user where)
3. **Add `--keep-temps` flag** for troubleshooting
4. **Log failures** with actionable error messages
5. **Consider rollback** on partial installation

---

## 9. Environment Detection

### Non-Interactive Mode

**Rustup:**
```bash
if [ "$need_tty" = "yes" ] && [ ! -t 0 ]; then
    if [ ! -t 1 ]; then
        err "Unable to run interactively..."
        exit 1
    fi
    ignore "$_file" < /dev/tty
fi

# -y flag bypasses prompts
for arg in "$@"; do
    case "$arg" in
        -y)
            need_tty=no
            ;;
    esac
done
```

**NVM Testing Mode:**
```bash
[ "_$NVM_ENV" = "_testing" ] || nvm_do_install
```

Prevents execution when sourcing for tests.

### CI Detection

**None of the three explicitly detect CI environments.** They rely on:
1. Flags (`-y`, `--quiet`)
2. Non-interactive stdin detection (`[ ! -t 0 ]`)

### Xcode Command Line Tools (NVM)

```bash
if nvm_has xcode-select && [ "$(xcode-select -p >/dev/null 2>&1 ; echo $?)" = '2' ]
then
  nvm_echo "=> Xcode Command Line Tools not found..."
  exit 1
fi
```

### Recommendation for Cub
1. **Detect CI via env vars**: `CI`, `GITHUB_ACTIONS`, `GITLAB_CI`, etc.
2. **Default to non-interactive in CI** (no prompts, auto-yes)
3. **Check for required tools** before attempting installation
4. **Add `--non-interactive` flag** as explicit override
5. **Test in Docker/minimal containers**

---

## 10. Notable Hardening Patterns

### Defensive Variable Expansion

**Rustup/Uv:**
```bash
${RUSTUP_UPDATE_ROOT:-https://static.rust-lang.org/rustup}
${RUSTUP_VERSION+set}  # Check if variable exists
${TERM+set}
```

**Parameter Expansion Patterns:**
- `${VAR:-default}` - Use default if unset
- `${VAR+set}` - Check existence without triggering `set -u`
- `${VAR#pattern}` - Remove prefix
- `${VAR%pattern}` - Remove suffix

**NVM:**
```bash
DETECTED_PROFILE="${ZDOTDIR:-${HOME}}/.zshrc"
```

### Return Values via RETVAL (Rustup)

Functions return values via global `RETVAL` to avoid subshells:

```bash
get_architecture() {
    # ... detection logic ...
    RETVAL="$_arch"
}

# Usage
get_architecture || return 1
local _arch="$RETVAL"
```

This avoids command substitution overhead.

### Command Wrappers

**NVM's grep Wrapper:**
```bash
nvm_grep() {
    GREP_OPTIONS='' command grep "$@"
}
```

Prevents environment variables from breaking commands.

**Rustup's need_cmd:**
```bash
need_cmd() {
    if ! check_cmd "$1"
    then err "need '$1' (command not found)"
    fi
}

check_cmd() {
    command -v "$1" > /dev/null 2>&1
}
```

### Function Namespace Cleanup (NVM)

```bash
nvm_reset() {
  unset -f nvm_has nvm_install_dir nvm_latest_version ...
}
# At script end
nvm_reset
```

Prevents polluting the user's shell namespace.

### wget Busybox Detection (Rustup)

```bash
if [ "$(wget -V 2>&1|head -2|tail -1|cut -f1 -d" ")" = "BusyBox" ]; then
    warn "using BusyBox version of wget (limited features)..."
fi
```

### Recommendation for Cub
1. **Use parameter expansion** for defaults and existence checks
2. **Wrap external commands** to neutralize environment variables
3. **Return values via RETVAL** for performance-critical functions
4. **Add busybox detection** for limited command environments
5. **Unset helper functions** at script end
6. **Prefix all functions** with `cub_` to avoid namespace collisions

---

## Comparative Summary Table

| Feature | Rustup | Uv | NVM | Recommendation for Cub |
|---------|--------|-----|-----|------------------------|
| **POSIX Compliance** | ✅ (sh + local alias) | ✅ (sh + local alias) | ❌ (bash-only) | Use sh + local alias |
| **Error Handling** | `set -u` + `ensure()` | `set -u` + `ensure()` | Manual checks | `set -u` + `ensure()` |
| **Checksum Verification** | ❌ | ✅ | ❌ | ✅ (sha256) |
| **TLS Hardening** | ✅ (explicit ciphers) | ✅ (defaults) | ✅ (defaults) | Enforce TLS 1.2+ |
| **Snap curl Detection** | ✅ | ✅ | ❌ | ✅ |
| **Platform Detection** | ✅✅ (ELF parsing) | ✅✅ (musl detection) | ❌ (shell only) | Copy rustup's approach |
| **Sudo Usage** | ❌ | ❌ | ❌ | ❌ (user install only) |
| **Idempotency** | Partial | Partial | ✅✅ | Guard profile mods |
| **Color Output** | ✅ (tput) | ✅ (tput) | ❌ | ✅ (with ANSI detection) |
| **Quiet/Verbose Modes** | Quiet only | Both | ❌ | Both |
| **Cleanup on Failure** | `ignore rm` | `ignore rm` | Git gc | Add trap handler |
| **CI Detection** | Via stdin | Via stdin | Testing mode | Explicit env var check |
| **Custom Repo Warning** | ❌ | ❌ | ✅ | ✅ (if applicable) |
| **Function Cleanup** | ❌ | ❌ | ✅ | ✅ (unset helpers) |

---

## Recommended Implementation Plan for Cub

### Phase 1: Foundation
1. Start with POSIX sh + local alias pattern
2. Implement `set -u`, `ensure()`, `ignore()` error handling
3. Add tput-based colored output with ANSI detection
4. Implement `--quiet` and `--verbose` flags with env var support

### Phase 2: Security
5. Add checksum verification for downloads
6. Enforce TLS 1.2+ with `curl --proto '=https' --tlsv1.2`
7. Detect and reject snap curl
8. Add `HOME` fallback using getent passwd

### Phase 3: Platform Detection
9. Implement comprehensive OS/arch detection (copy rustup)
10. Handle musl vs glibc for Linux
11. Detect macOS Rosetta 2
12. Normalize architecture names

### Phase 4: Robustness
13. Add idempotency checks for existing installations
14. Guard profile modifications (check if already sourced)
15. Add trap handler for cleanup on failure
16. Implement CI detection (GitHub Actions, GitLab CI, etc.)

### Phase 5: Polish
17. Add detailed progress messages
18. Implement `--non-interactive` and `-y` flags
19. Add function namespace cleanup
20. Add comprehensive usage/help documentation

---

## Code Templates

### Recommended Error Handling Pattern

```bash
#!/bin/sh
# shellcheck shell=dash
# shellcheck disable=SC2039  # local is non-POSIX

# Ensure local keyword exists
has_local() {
    local _has_local
}
has_local 2>/dev/null || alias local=typeset

set -u

# Color detection
_ansi_escapes_are_valid=false
if [ -t 2 ]; then
    if [ "${TERM+set}" = 'set' ]; then
        case "$TERM" in
            xterm*|rxvt*|urxvt*|linux*|vt*)
                _ansi_escapes_are_valid=true
            ;;
        esac
    fi
fi

# Output helpers
say() {
    if [ "${QUIET:-0}" = "0" ]; then
        echo "$1"
    fi
}

say_verbose() {
    if [ "${VERBOSE:-0}" = "1" ]; then
        echo "$1"
    fi
}

err() {
    if [ "${QUIET:-0}" = "0" ]; then
        local red reset
        if [ "$_ansi_escapes_are_valid" = "true" ]; then
            red=$(tput setaf 1 2>/dev/null || echo '')
            reset=$(tput sgr0 2>/dev/null || echo '')
        else
            red=""
            reset=""
        fi
        echo "${red}ERROR${reset}: $1" >&2
    fi
    exit 1
}

warn() {
    if [ "${QUIET:-0}" = "0" ]; then
        local yellow reset
        if [ "$_ansi_escapes_are_valid" = "true" ]; then
            yellow=$(tput setaf 3 2>/dev/null || echo '')
            reset=$(tput sgr0 2>/dev/null || echo '')
        else
            yellow=""
            reset=""
        fi
        echo "${yellow}WARN${reset}: $1" >&2
    fi
}

# Command helpers
check_cmd() {
    command -v "$1" > /dev/null 2>&1
}

need_cmd() {
    if ! check_cmd "$1"; then
        err "need '$1' (command not found)"
    fi
}

ensure() {
    if ! "$@"; then
        err "command failed: $*"
    fi
}

ignore() {
    "$@"
}
```

### Recommended Checksum Verification

```bash
verify_checksum() {
    local _file="$1"
    local _expected="$2"
    local _calculated

    if [ -z "$_expected" ]; then
        say_verbose "No checksum provided, skipping verification"
        return 0
    fi

    if ! check_cmd sha256sum; then
        warn "sha256sum not found, skipping checksum verification"
        return 0
    fi

    say_verbose "Verifying checksum..."
    _calculated="$(sha256sum "$_file" | awk '{print $1}')"

    if [ "$_calculated" != "$_expected" ]; then
        err "Checksum mismatch! Expected: $_expected, Got: $_calculated"
    fi

    say_verbose "Checksum verified"
}
```

### Recommended Platform Detection

```bash
get_platform() {
    local _ostype="$(uname -s)"
    local _cputype="$(uname -m)"
    local _clibtype="gnu"

    # Normalize OS
    case "$_ostype" in
        Linux)
            if [ "$(uname -o 2>/dev/null)" = "Android" ]; then
                _ostype="Android"
            fi
            # Detect musl vs glibc
            if ldd --version 2>&1 | grep -q 'musl'; then
                _clibtype="musl"
            fi
            ;;
        Darwin)
            # Detect Rosetta 2 on ARM Mac
            if [ "$_cputype" = "x86_64" ]; then
                if sysctl hw.optional.arm64 2>&1 | grep -q ': 1$'; then
                    _cputype="aarch64"
                fi
            fi
            ;;
    esac

    # Normalize CPU architecture
    case "$_cputype" in
        x86_64|x86-64|x64|amd64)
            _cputype="x86_64"
            ;;
        aarch64|arm64)
            _cputype="aarch64"
            ;;
    esac

    echo "${_cputype}-${_ostype}-${_clibtype}"
}
```

### Recommended Idempotency Pattern

```bash
install_or_update() {
    if [ -f "$INSTALL_DIR/cub" ]; then
        say "cub is already installed at $INSTALL_DIR"
        say "Updating to version $VERSION..."
        # Perform update logic
    else
        say "Installing cub $VERSION to $INSTALL_DIR..."
        # Perform fresh install logic
    fi
}

add_to_profile() {
    local _profile="$1"
    local _source_line='export PATH="$HOME/.cub/bin:$PATH"'

    if grep -q "\.cub/bin" "$_profile" 2>/dev/null; then
        say_verbose "PATH already configured in $_profile"
        return 0
    fi

    say "Adding cub to PATH in $_profile"
    echo "" >> "$_profile"
    echo "# Added by cub installer" >> "$_profile"
    echo "$_source_line" >> "$_profile"
}
```

---

## Additional Resources

- **Rustup Install Script Source**: https://github.com/rust-lang/rustup/blob/master/rustup-init.sh
- **Uv Install Script Source**: https://github.com/astral-sh/uv/releases/latest/download/uv-installer.sh
- **NVM Install Script Source**: https://github.com/nvm-sh/nvm/blob/master/install.sh
- **ShellCheck**: https://www.shellcheck.net/
- **POSIX Shell Guide**: https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html
- **XDG Base Directory Spec**: https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html

---

## Conclusion

The analyzed scripts demonstrate converging best practices:

1. **POSIX sh targeting** with minimal extensions (local)
2. **Explicit error handling** over `set -e`
3. **User-space installation** (no sudo)
4. **Comprehensive platform detection**
5. **Colored, quiet-able output**
6. **Idempotency through checks**
7. **Security through HTTPS and checksums**

For Cub, adopting these patterns will produce an installer that is:
- **Robust** across diverse Unix environments
- **Secure** through cryptographic verification
- **User-friendly** with clear progress and colors
- **Automatable** via flags and CI detection
- **Maintainable** through defensive programming

# Gemini CLI Research Spike

**Date:** 2026-01-10
**Version Tested:** 0.1.9
**Purpose:** Understand Gemini CLI interface for curb harness implementation

## Executive Summary

Gemini CLI is an open-source AI agent from Google that brings Gemini directly into the terminal. It's installed via npm/homebrew and uses a ReAct (reason and act) loop with built-in tools. The CLI differs significantly from Claude Code in its interaction model - it's more interactive by default and requires explicit YOLO mode (`-y`) for autonomous operation.

## Installation

### Methods Available
1. **NPX** (No installation): `npx @google/gemini-cli`
2. **NPM Global**: `npm install -g @google/gemini-cli`
3. **Homebrew**: `brew install gemini-cli` (macOS/Linux)
4. **Cloud Shell**: Pre-installed in Google Cloud Shell

### Current Installation Status
```bash
$ which gemini
/opt/homebrew/bin/gemini

$ gemini --version
0.1.9
```

## Basic Invocation

### Command Pattern
```bash
echo "prompt text" | gemini -p "additional prompt" [flags]
```

### Example
```bash
$ echo "What is 2+2? Please respond in one sentence." | gemini -p "Answer the question"
The sum of 2+2 is 4.
```

## Key Flags Mapped to Curb Needs

### Auto Mode (YOLO)
- **Flag**: `-y` or `--yolo`
- **Default**: `false`
- **Description**: Automatically accept all actions without user confirmation
- **Curb Requirement**: ✅ CRITICAL - Required for autonomous operation
- **Example**:
  ```bash
  $ echo "Calculate 5+5" | gemini -p "Answer" -y
  10
  ```

### Model Selection
- **Flag**: `-m` or `--model`
- **Default**: `gemini-2.5-pro`
- **Description**: Specify which Gemini model to use
- **Curb Requirement**: ✅ Useful for model switching
- **Example**: `gemini -m gemini-2.5-flash`

### Debug Mode
- **Flag**: `-d` or `--debug`
- **Default**: `false`
- **Description**: Run in debug mode with verbose output
- **Curb Requirement**: ✅ Needed for troubleshooting

### Prompt Input
- **Flag**: `-p` or `--prompt`
- **Description**: Appended to input on stdin
- **Curb Requirement**: ✅ Used to provide task prompt
- **Note**: Works with piped stdin for combined prompts

### Other Notable Flags
- `--sandbox`: Run in sandbox environment (boolean)
- `--sandbox-image`: Specify sandbox image URI
- `-a` / `--all_files`: Include ALL files in context (default: false)
- `--show_memory_usage`: Display memory usage in status bar
- `-c` / `--checkpointing`: Enable checkpointing of file edits
- `--telemetry`: Enable/disable telemetry reporting

## System Prompt

### In-session Commands
- `/memory` command: Adds text to AI's memory (via GEMINI.md files)
- No direct `--system-prompt` flag like Claude Code

### Implementation Strategy for Curb
Since there's no `--system-prompt` flag:
1. **Option A**: Use `-p` flag to prepend system prompt to task prompt
   ```bash
   combined="$system_prompt\n\n---\n\n$task_prompt"
   echo "" | gemini -p "$combined" -y
   ```
2. **Option B**: Use GEMINI.md file in project root (permanent context)
3. **Option C**: Concatenate and pipe entire prompt via stdin

**Recommended**: Option A (inline concatenation) matches Codex pattern

## Streaming

### Available Options
- **Flag**: None found in v0.1.9
- **Status**: ❌ NOT AVAILABLE in command-line flags
- **Documentation Reference**: GitHub README mentions `--output-format stream-json` for "newline-delimited JSON events"
- **Reality**: Testing shows `--output-format` is NOT recognized in v0.1.9

### Testing Results
```bash
$ gemini -p "test" -y --output-format json
Unknown arguments: output-format, outputFormat
```

### Conclusion
- Streaming may be available in newer versions or different installation methods
- Current homebrew version (0.1.9) does NOT support `--output-format`
- For curb integration: Use non-streaming mode initially

## Token and Usage Reporting

### Testing Results
```bash
$ cd /tmp && timeout 10 gemini -p "What is 1+1?" -y 2>&1 | grep -E "(Usage|Token|Cost|Statistics)"
No usage information in output
```

### In-Session Commands
- `/stats`: Display statistics including token usage, cached token savings, session duration
- **Limitation**: Only accessible in interactive mode, NOT in automated invocations

### Token Caching
- Documented feature to "optimize token usage"
- Cached token savings available with API key authentication (not OAuth)

### Conclusion for Curb
- ❌ **NO token reporting in stdout for scripted usage**
- ❌ Cannot extract usage from command-line invocations
- Possible workarounds:
  1. Parse session files if Gemini CLI creates them
  2. Use Gemini API directly with SDK for usage tracking
  3. Estimate based on input/output length
  4. Leave as 0 until API integration available

## Significant Differences from Claude/Codex

### 1. Interactive by Default
- Gemini CLI is designed for interactive terminal sessions
- Requires `-y` (YOLO) flag for autonomous operation
- Claude Code has `--dangerously-skip-permissions` (similar concept)

### 2. No Explicit System Prompt Flag
- Claude Code: `--append-system-prompt "..."`
- Codex: Combined prompts
- Gemini CLI: Must use GEMINI.md or concatenate prompts

### 3. No Token Reporting in Stdout
- Claude Code: Returns usage in stream-json events
- Gemini CLI: Only accessible via `/stats` in interactive mode
- **Impact**: Cannot track budget accurately without API integration

### 4. File Context Behavior
- Gemini CLI scans working directory by default
- Prints warnings for inaccessible directories (can be noisy)
- `-a` flag includes ALL files (potentially expensive)

### 5. MCP (Model Context Protocol) Support
- Unique feature: supports local/remote MCP servers
- Allows custom tool integrations
- Not present in Claude Code or Codex

### 6. Built-in Tools
- grep, terminal, file read/write built-in
- Web search and web fetch capabilities
- More integrated than Claude Code's tool system

### 7. Checkpointing
- `-c` flag enables checkpointing of file edits
- Could be useful for state management
- Would need testing for curb integration

## Recommendations for Curb Harness Implementation

### Minimum Viable Implementation

```bash
gemini_invoke() {
    local system_prompt="$1"
    local task_prompt="$2"
    local debug="${3:-false}"

    # Combine prompts (no --append-system-prompt available)
    local combined_prompt="${system_prompt}

---

${task_prompt}"

    local flags="-y"  # YOLO mode required for automation
    [[ "$debug" == "true" ]] && flags="$flags -d"

    # Add model flag if specified
    [[ -n "${CURB_MODEL:-}" ]] && flags="$flags -m $CURB_MODEL"

    # Invoke with combined prompt
    echo "" | gemini -p "$combined_prompt" $flags
}
```

### Challenges to Address

1. **No Token Reporting**:
   - Return 0 for tokens_used initially
   - Document limitation in code comments
   - Consider API integration for accurate tracking

2. **Directory Scanning Warnings**:
   - Gemini prints warnings for inaccessible directories
   - May pollute output in `/tmp` or other shared directories
   - Solution: Redirect stderr or filter warnings

3. **No Streaming Support** (in v0.1.9):
   - Use non-streaming mode only
   - Check for `--output-format` in future versions

4. **System Prompt Concatenation**:
   - Must combine system + task prompts manually
   - Same pattern as Codex harness

### Future Enhancements

1. **Investigate newer versions** for `--output-format stream-json`
2. **Test GEMINI.md files** for persistent system prompts
3. **Explore MCP integration** for custom tools
4. **Parse session artifacts** if Gemini CLI creates usage logs
5. **Consider Gemini API SDK** for direct API calls with better usage tracking

## Testing Checklist

- [x] Installation method documented (Homebrew)
- [x] Basic invocation working (`echo | gemini -p`)
- [x] Flags mapped to curb needs (-y for auto, -m for model, -d for debug)
- [x] Token reporting capability assessed (NOT available in stdout)
- [x] Findings written to .chopshop/spikes/gemini.md

## References

- [Gemini CLI GitHub](https://github.com/google-gemini/gemini-cli)
- [Gemini CLI Documentation](https://geminicli.com/docs/)
- [Google Developers: Gemini CLI](https://developers.google.com/gemini-code-assist/docs/gemini-cli)
- [Google Blog: Introducing Gemini CLI](https://blog.google/technology/developers/introducing-gemini-cli-open-source-ai-agent/)

## Next Steps

Task curb-3s0 (Implement Gemini harness) can proceed with:
1. Basic non-streaming implementation following Claude/Codex patterns
2. Use `-y` flag for autonomous operation
3. Concatenate system + task prompts
4. Return 0 for token usage (document limitation)
5. Add TODO comments for future streaming/usage support

# End-to-End Tests

This directory contains end-to-end tests for cub that verify the full loop execution with all features working together.

## Overview

The e2e test creates a minimal test project with 3 simple tasks and runs cub with a budget to verify:

- ✓ Full loop runs to completion or budget limit
- ✓ All hooks fire at the right times (pre-loop, pre-task, post-task, post-loop)
- ✓ Logs are created with expected events
- ✓ Clean state is enforced
- ✓ Budget tracking stops the loop correctly
- ✓ Task dependencies are respected

## Running the Test

### Prerequisites

1. **Claude CLI installed**: The test requires the `claude` command-line tool
2. **API Key**: Set your `ANTHROPIC_API_KEY` environment variable
3. **jq installed**: For JSON processing

### Execute the test

```bash
# From the cub root directory
./tests/e2e/run.sh
```

Or from the tests/e2e directory:

```bash
cd tests/e2e
./run.sh
```

### Running without API Key

If you don't have an API key, the test will simulate the execution and verify the test infrastructure works:

```bash
# Test will skip actual cub execution but verify test logic
./tests/e2e/run.sh
```

## Test Project Structure

```
tests/e2e/
├── run.sh              # Main test script
├── README.md           # This file
└── project/            # Test project
    ├── prd.json        # 3 simple tasks
    ├── PROMPT.md       # Agent prompt
    ├── .cub/
    │   ├── agent.md    # Build instructions
    │   └── prompt.md   # Agent prompt
    └── .cub/
        ├── hooks/      # Test hooks
        │   ├── pre-loop.d/
        │   ├── pre-task.d/
        │   ├── post-task.d/
        │   ├── post-loop.d/
        │   └── on-error.d/
        └── config.json # Test configuration
```

## Test Tasks

The test project includes 3 simple tasks:

1. **e2e-001**: Create hello.txt with "Hello from task 1"
2. **e2e-002**: Create world.txt with "World from task 2"
3. **e2e-003**: Create merged.txt by combining hello.txt and world.txt (depends on 1 & 2)

## Verification Checks

The test verifies:

1. **Generated Files**: All expected output files are created
2. **Task Status**: Tasks are marked as closed in prd.json
3. **Hooks**: All hooks executed and logged to hook_events.log
4. **Logs**: Structured logs created in ~/.local/share/cub/logs/
5. **Budget**: Loop stops when budget is exceeded

## CI Integration

This test can be run in CI environments:

```yaml
- name: Run e2e tests
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: ./tests/e2e/run.sh
```

Note: Without an API key, the test will skip cub execution but still verify test infrastructure.

## Cleanup

The test automatically cleans up after itself:

- Removes generated files (hello.txt, world.txt, merged.txt)
- Removes hook logs
- Resets prd.json to original state
- Removes git repository

## Troubleshooting

### Test fails with "claude not found"

Install Claude CLI: https://claude.ai/download

### Test fails with API authentication error

Ensure your `ANTHROPIC_API_KEY` is set:

```bash
export ANTHROPIC_API_KEY="your-key-here"
./tests/e2e/run.sh
```

### Test times out

The budget is set to 100,000 tokens which should be enough for 3 simple tasks. If tasks are taking too long:

- Check the .cub/prompt.md and .cub/agent.md are clear
- Verify Claude is not stuck waiting for user input
- Check the cub logs for errors

### Hooks not executing

Ensure hook scripts are executable:

```bash
chmod +x tests/e2e/project/.cub/hooks/*/*.sh
```

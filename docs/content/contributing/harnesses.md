---
title: Adding Harnesses
description: How to add support for new AI coding assistants to Cub.
---

# Adding AI Harnesses

Harnesses are pluggable backends that wrap AI coding CLI tools. This guide shows you how to add support for a new AI coding assistant.

## What is a Harness?

A harness adapts an AI coding CLI to work with Cub's autonomous loop. It handles:

- **Detection** - Checking if the CLI is installed
- **Invocation** - Running the AI with prompts
- **Streaming** - Real-time output capture
- **Token tracking** - Usage reporting for budgets

---

## The HarnessBackend Protocol

All harnesses implement the `HarnessBackend` protocol:

```python
from typing import Protocol, runtime_checkable
from collections.abc import Callable
from cub.core.harness.models import HarnessCapabilities, HarnessResult

@runtime_checkable
class HarnessBackend(Protocol):
    """Protocol for harness backend implementations."""

    @property
    def name(self) -> str:
        """Harness name (e.g., 'claude', 'codex')."""
        ...

    @property
    def capabilities(self) -> HarnessCapabilities:
        """Harness capabilities (streaming, tokens, etc.)."""
        ...

    def is_available(self) -> bool:
        """Check if harness CLI is installed."""
        ...

    def invoke(
        self,
        system_prompt: str,
        task_prompt: str,
        model: str | None = None,
        debug: bool = False,
    ) -> HarnessResult:
        """Invoke harness with blocking execution."""
        ...

    def invoke_streaming(
        self,
        system_prompt: str,
        task_prompt: str,
        model: str | None = None,
        debug: bool = False,
        callback: Callable[[str], None] | None = None,
    ) -> HarnessResult:
        """Invoke harness with streaming output."""
        ...

    def get_version(self) -> str:
        """Get harness CLI version."""
        ...
```

---

## Step-by-Step Guide

### Step 1: Create the Backend Module

Create a new file at `src/cub/core/harness/myharness.py`:

```python
"""MyHarness backend implementation."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable

from .backend import register_backend
from .models import HarnessCapabilities, HarnessResult, TokenUsage


@register_backend("myharness")
class MyHarnessBackend:
    """MyHarness AI coding assistant backend."""

    @property
    def name(self) -> str:
        """Return harness name."""
        return "myharness"

    @property
    def capabilities(self) -> HarnessCapabilities:
        """Return harness capabilities."""
        return HarnessCapabilities(
            streaming=True,           # Supports real-time output
            token_reporting=True,     # Reports token usage
            system_prompt=False,      # No separate system prompt flag
            auto_mode=True,           # Supports autonomous execution
            json_output=True,         # Supports JSON output format
            model_selection=True,     # Supports --model flag
        )

    def is_available(self) -> bool:
        """Check if myharness CLI is installed."""
        return shutil.which("myharness") is not None

    def get_version(self) -> str:
        """Get myharness version string."""
        try:
            result = subprocess.run(
                ["myharness", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() or "unknown"
        except (subprocess.SubprocessError, FileNotFoundError):
            return "unknown"

    def invoke(
        self,
        system_prompt: str,
        task_prompt: str,
        model: str | None = None,
        debug: bool = False,
    ) -> HarnessResult:
        """Invoke myharness with blocking execution."""
        start_time = time.time()

        # Combine prompts (if no system prompt support)
        combined_prompt = f"{system_prompt}\n\n---\n\n{task_prompt}"

        # Build command
        cmd = ["myharness", "run", "--auto", "--json"]
        if model:
            cmd.extend(["--model", model])

        # Run harness
        result = subprocess.run(
            cmd,
            input=combined_prompt,
            capture_output=True,
            text=True,
        )

        duration = time.time() - start_time

        # Parse output
        output = result.stdout
        usage = self._parse_usage(output)

        return HarnessResult(
            output=output,
            exit_code=result.returncode,
            duration_seconds=duration,
            usage=usage,
        )

    def invoke_streaming(
        self,
        system_prompt: str,
        task_prompt: str,
        model: str | None = None,
        debug: bool = False,
        callback: Callable[[str], None] | None = None,
    ) -> HarnessResult:
        """Invoke myharness with streaming output."""
        start_time = time.time()

        combined_prompt = f"{system_prompt}\n\n---\n\n{task_prompt}"

        cmd = ["myharness", "run", "--auto", "--stream"]
        if model:
            cmd.extend(["--model", model])

        # Start process
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Send input
        if proc.stdin:
            proc.stdin.write(combined_prompt)
            proc.stdin.close()

        # Stream output
        output_lines = []
        if proc.stdout:
            for line in proc.stdout:
                output_lines.append(line)
                if callback:
                    callback(line)

        proc.wait()
        duration = time.time() - start_time

        output = "".join(output_lines)
        usage = self._parse_usage(output)

        return HarnessResult(
            output=output,
            exit_code=proc.returncode,
            duration_seconds=duration,
            usage=usage,
        )

    def _parse_usage(self, output: str) -> TokenUsage | None:
        """Parse token usage from output."""
        try:
            # Look for JSON usage block in output
            # Adjust parsing based on your harness's output format
            data = json.loads(output)
            if "usage" in data:
                return TokenUsage(
                    input_tokens=data["usage"].get("input_tokens", 0),
                    output_tokens=data["usage"].get("output_tokens", 0),
                    total_tokens=data["usage"].get("total_tokens", 0),
                )
        except (json.JSONDecodeError, KeyError):
            pass
        return None
```

### Step 2: Register the Import

Add the import to `src/cub/core/harness/__init__.py`:

```python
"""Harness backends for AI coding assistants."""

from .backend import (
    HarnessBackend,
    detect_harness,
    get_backend,
    get_capabilities,
    is_backend_available,
    list_available_backends,
    list_backends,
    register_backend,
)
from .models import HarnessCapabilities, HarnessResult, TokenUsage

# Import backends to trigger registration
from . import claude
from . import codex
from . import gemini
from . import opencode
from . import myharness  # Add your backend

__all__ = [
    "HarnessBackend",
    "HarnessCapabilities",
    "HarnessResult",
    "TokenUsage",
    "detect_harness",
    "get_backend",
    "get_capabilities",
    "is_backend_available",
    "list_available_backends",
    "list_backends",
    "register_backend",
]
```

### Step 3: Add Auto-Detection (Optional)

If your harness should be auto-detected, update the detection order in `backend.py`:

```python
def detect_harness(priority_list: list[str] | None = None) -> str | None:
    """Auto-detect which harness to use."""
    # ...

    # Default detection order - add your harness
    for harness in ["claude", "opencode", "codex", "gemini", "myharness"]:
        if harness in _backends and shutil.which(harness):
            return harness

    return None
```

---

## Capabilities Reference

Declare what your harness supports:

```python
HarnessCapabilities(
    streaming=True,        # Real-time output as AI generates
    token_reporting=True,  # Accurate token usage in output
    system_prompt=True,    # Separate --system-prompt flag
    auto_mode=True,        # Autonomous execution without prompts
    json_output=True,      # Structured JSON response format
    model_selection=True,  # Runtime --model flag support
)
```

| Capability | Description | Cub Behavior if False |
|------------|-------------|----------------------|
| `streaming` | Real-time output | Output shown after completion |
| `token_reporting` | Token counts in output | Budget tracking uses estimates |
| `system_prompt` | Separate system prompt flag | Prompts concatenated |
| `auto_mode` | No user confirmation needed | Required for autonomous operation |
| `json_output` | JSON response format | Raw text parsed as-is |
| `model_selection` | `--model` flag support | `model:` task labels ignored |

---

## Testing Your Harness

### Unit Tests

Create `tests/test_harness_myharness.py`:

```python
"""Tests for MyHarness backend."""

import pytest
from unittest.mock import patch, MagicMock
from cub.core.harness.myharness import MyHarnessBackend


class TestMyHarnessBackend:
    """Test MyHarness backend implementation."""

    def test_name(self):
        """Test harness name."""
        backend = MyHarnessBackend()
        assert backend.name == "myharness"

    def test_capabilities(self):
        """Test capabilities declaration."""
        backend = MyHarnessBackend()
        caps = backend.capabilities
        assert caps.streaming is True
        assert caps.auto_mode is True

    @patch("shutil.which")
    def test_is_available_installed(self, mock_which):
        """Test availability when CLI is installed."""
        mock_which.return_value = "/usr/local/bin/myharness"
        backend = MyHarnessBackend()
        assert backend.is_available() is True

    @patch("shutil.which")
    def test_is_available_not_installed(self, mock_which):
        """Test availability when CLI is not installed."""
        mock_which.return_value = None
        backend = MyHarnessBackend()
        assert backend.is_available() is False

    @patch("subprocess.run")
    def test_invoke_basic(self, mock_run):
        """Test basic invocation."""
        mock_run.return_value = MagicMock(
            stdout='{"result": "success", "usage": {"input_tokens": 100}}',
            returncode=0,
        )

        backend = MyHarnessBackend()
        result = backend.invoke("system", "task")

        assert result.exit_code == 0
        assert "success" in result.output

    @patch("subprocess.run")
    def test_invoke_with_model(self, mock_run):
        """Test invocation with model selection."""
        mock_run.return_value = MagicMock(stdout="{}", returncode=0)

        backend = MyHarnessBackend()
        backend.invoke("system", "task", model="fast")

        # Verify --model flag was passed
        call_args = mock_run.call_args[0][0]
        assert "--model" in call_args
        assert "fast" in call_args
```

### Integration Tests

Test with the actual CLI (requires harness installed):

```python
@pytest.mark.integration
@pytest.mark.skipif(
    not MyHarnessBackend().is_available(),
    reason="myharness CLI not installed"
)
def test_real_invocation():
    """Test real harness invocation."""
    backend = MyHarnessBackend()
    result = backend.invoke(
        "You are a helpful assistant.",
        "Say hello in 5 words or less.",
    )
    assert result.exit_code == 0
    assert len(result.output) > 0
```

---

## Environment Variables

Document environment variables for your harness:

| Variable | Purpose | Example |
|----------|---------|---------|
| `MYHARNESS_FLAGS` | Extra CLI flags | `--verbose --timeout 60` |
| `MYHARNESS_MODEL` | Default model override | `fast` |

In your backend:

```python
import os

def invoke(self, ...):
    cmd = ["myharness", "run", "--auto"]

    # Add extra flags from environment
    extra_flags = os.environ.get("MYHARNESS_FLAGS", "")
    if extra_flags:
        cmd.extend(extra_flags.split())

    # Model from env or parameter
    model = model or os.environ.get("MYHARNESS_MODEL")
    if model:
        cmd.extend(["--model", model])
```

---

## Documentation

Update documentation:

1. **User Guide** - Add `docs-site/docs/guide/harnesses/myharness.md`
2. **Harness Index** - Update `docs-site/docs/guide/harnesses/index.md`
3. **README** - Add to supported harnesses list

---

## Example: Claude Backend

For reference, here's a simplified view of the Claude backend:

```python
@register_backend("claude")
class ClaudeBackend:
    """Claude Code AI coding assistant backend."""

    @property
    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            streaming=True,
            token_reporting=True,
            system_prompt=True,  # Has --append-system-prompt
            auto_mode=True,
            json_output=True,
            model_selection=True,
        )

    def invoke(self, system_prompt, task_prompt, model=None, debug=False):
        cmd = [
            "claude", "-p",
            "--append-system-prompt", system_prompt,
            "--dangerously-skip-permissions",
            "--output-format", "json",
        ]
        if model:
            cmd.extend(["--model", model])

        result = subprocess.run(cmd, input=task_prompt, ...)
        # ...
```

---

## Checklist

Before submitting your harness:

- [ ] Implements all `HarnessBackend` protocol methods
- [ ] Registered with `@register_backend` decorator
- [ ] Import added to `__init__.py`
- [ ] Capabilities accurately declared
- [ ] Token parsing implemented (if supported)
- [ ] Unit tests written
- [ ] Integration test (optional, requires CLI)
- [ ] Documentation added
- [ ] Environment variables documented

---

## Next Steps

<div class="grid cards" markdown>

-   :material-database: **Adding Backends**

    ---

    Create task storage backends.

    [:octicons-arrow-right-24: Backend Guide](backends.md)

-   :material-test-tube: **Testing**

    ---

    Run the test suite.

    [:octicons-arrow-right-24: Setup Guide](setup.md)

</div>

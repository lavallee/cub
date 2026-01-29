"""
Interrupt handling for clean shutdown of the run loop.

Provides signal handling (SIGINT/SIGTERM) that works regardless of which interface
is driving the run loop. The InterruptHandler coordinates with the loop state
machine to enable graceful shutdown.

The handler implements a two-stage interrupt model:
1. First interrupt: Sets flag for cooperative shutdown (lets current task finish)
2. Second interrupt: Force exits with SystemExit(130)

Usage:
    >>> from cub.core.run.interrupt import InterruptHandler
    >>> handler = InterruptHandler()
    >>> handler.register()  # Set up signal handlers
    >>> # ... during run loop execution
    >>> if handler.interrupted:
    ...     # Initiate graceful shutdown
    >>> handler.on_interrupt(cleanup_fn)  # Register cleanup callback
"""

from __future__ import annotations

import signal
import sys
from collections.abc import Callable
from typing import Any


class InterruptHandler:
    """
    Handles SIGINT/SIGTERM signals for clean run loop shutdown.

    Implements cooperative interruption: the handler sets a flag that the loop
    checks between tasks. On the first interrupt, it signals graceful shutdown.
    On the second interrupt, it force-exits.

    Attributes:
        interrupted: Boolean flag indicating an interrupt was received.
                    Loop should check this between iterations.
    """

    def __init__(self) -> None:
        """Initialize the interrupt handler with no interrupts received."""
        self._interrupted = False
        self._cleanup_callbacks: list[Callable[[], None]] = []
        self._original_sigint: Any = None
        self._original_sigterm: Any = None

    @property
    def interrupted(self) -> bool:
        """
        Check if an interrupt has been received.

        Returns:
            True if interrupt signal was received, False otherwise.
        """
        return self._interrupted

    def register(self) -> None:
        """
        Register signal handlers for SIGINT and SIGTERM.

        Should be called before starting the run loop. Saves the original
        signal handlers so they can be restored later.
        """
        self._original_sigint = signal.signal(signal.SIGINT, self._handle_signal)
        self._original_sigterm = signal.signal(signal.SIGTERM, self._handle_signal)

    def unregister(self) -> None:
        """
        Restore original signal handlers.

        Should be called after the run loop completes to restore previous
        signal handling behavior.
        """
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
            self._original_sigint = None

        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)
            self._original_sigterm = None

    def on_interrupt(self, callback: Callable[[], None]) -> None:
        """
        Register a cleanup callback to run on graceful shutdown.

        The callback will be invoked when the first interrupt is received,
        allowing for cleanup operations like artifact finalization and
        ledger entry completion.

        Args:
            callback: A callable that takes no arguments and returns None.
                     Should perform cleanup operations (non-blocking preferred).
        """
        self._cleanup_callbacks.append(callback)

    def _handle_signal(self, signum: int, frame: object) -> None:
        """
        Internal signal handler called by the signal module.

        Implements the two-stage interrupt model:
        - First call: Sets interrupted flag and runs cleanup callbacks
        - Second call: Force exits with SystemExit(130)

        Args:
            signum: Signal number (SIGINT=2, SIGTERM=15).
            frame: Current stack frame (unused).
        """
        if self._interrupted:
            # Second interrupt - force exit
            # Using raise SystemExit ensures finally blocks execute
            self._write_to_stderr("\n[Force exiting...]\n")
            raise SystemExit(130)

        # First interrupt - set flag and notify
        self._interrupted = True
        self._write_to_stderr("\n[Interrupt received. Finishing current task...]\n")

        # Run cleanup callbacks (non-blocking preferred)
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception:
                # Silently ignore cleanup errors to avoid disrupting shutdown
                pass

    @staticmethod
    def _write_to_stderr(message: str) -> None:
        """
        Write a message to stderr without using Rich console.

        This avoids dependencies on CLI rendering during signal handling,
        making it safe to use from any context.

        Args:
            message: The message to write to stderr.
        """
        sys.stderr.write(message)
        sys.stderr.flush()

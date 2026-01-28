"""
Unit tests for cub.core.run.interrupt.

Tests the InterruptHandler's signal handling, cooperative shutdown,
and integration with the run loop.
"""

from __future__ import annotations

import signal
from unittest.mock import MagicMock, call, patch

import pytest

from cub.core.run.interrupt import InterruptHandler

# ===========================================================================
# Test InterruptHandler initialization and state
# ===========================================================================


def test_interrupt_handler_initialization():
    """Test that InterruptHandler initializes with correct default state."""
    handler = InterruptHandler()

    assert handler.interrupted is False
    assert handler._interrupted is False
    assert handler._cleanup_callbacks == []
    assert handler._original_sigint is None
    assert handler._original_sigterm is None


def test_interrupt_handler_interrupted_property():
    """Test that the interrupted property reflects internal state."""
    handler = InterruptHandler()

    # Initially not interrupted
    assert handler.interrupted is False

    # Simulate internal flag change
    handler._interrupted = True
    assert handler.interrupted is True


# ===========================================================================
# Test signal registration and unregistration
# ===========================================================================


def test_register_sets_signal_handlers():
    """Test that register() sets up SIGINT and SIGTERM handlers."""
    handler = InterruptHandler()

    with patch("signal.signal") as mock_signal:
        mock_signal.return_value = signal.SIG_DFL

        handler.register()

        # Verify both signals were registered
        assert mock_signal.call_count == 2
        calls = mock_signal.call_args_list

        # Check SIGINT registration
        assert calls[0] == call(signal.SIGINT, handler._handle_signal)

        # Check SIGTERM registration
        assert calls[1] == call(signal.SIGTERM, handler._handle_signal)

        # Verify original handlers were saved
        assert handler._original_sigint == signal.SIG_DFL
        assert handler._original_sigterm == signal.SIG_DFL


def test_unregister_restores_original_handlers():
    """Test that unregister() restores original signal handlers."""
    handler = InterruptHandler()

    with patch("signal.signal") as mock_signal:
        # Set up mock return values for registration
        mock_signal.side_effect = [signal.SIG_DFL, signal.SIG_IGN]

        # Register handlers
        handler.register()

        # Reset mock to track unregister calls
        mock_signal.reset_mock()
        mock_signal.side_effect = None

        # Unregister handlers
        handler.unregister()

        # Verify original handlers were restored
        assert mock_signal.call_count == 2
        calls = mock_signal.call_args_list

        assert calls[0] == call(signal.SIGINT, signal.SIG_DFL)
        assert calls[1] == call(signal.SIGTERM, signal.SIG_IGN)

        # Verify internal state was cleared
        assert handler._original_sigint is None
        assert handler._original_sigterm is None


def test_unregister_safe_when_not_registered():
    """Test that unregister() is safe to call when handlers not registered."""
    handler = InterruptHandler()

    with patch("signal.signal") as mock_signal:
        # Should not raise, should not call signal.signal
        handler.unregister()

        assert mock_signal.call_count == 0


# ===========================================================================
# Test interrupt handling behavior
# ===========================================================================


def test_first_interrupt_sets_flag():
    """Test that first interrupt sets the interrupted flag."""
    handler = InterruptHandler()

    # Simulate first interrupt
    handler._handle_signal(signal.SIGINT, None)

    assert handler.interrupted is True


def test_first_interrupt_calls_cleanup_callbacks():
    """Test that first interrupt executes registered cleanup callbacks."""
    handler = InterruptHandler()

    # Register mock callbacks
    callback1 = MagicMock()
    callback2 = MagicMock()

    handler.on_interrupt(callback1)
    handler.on_interrupt(callback2)

    # Trigger interrupt
    handler._handle_signal(signal.SIGINT, None)

    # Verify both callbacks were called
    callback1.assert_called_once()
    callback2.assert_called_once()


def test_first_interrupt_writes_to_stderr():
    """Test that first interrupt writes message to stderr."""
    handler = InterruptHandler()

    with patch("sys.stderr.write") as mock_write, patch("sys.stderr.flush") as mock_flush:
        handler._handle_signal(signal.SIGINT, None)

        # Verify message was written
        mock_write.assert_called_once()
        message = mock_write.call_args[0][0]
        assert "Interrupt received" in message
        assert "Finishing current task" in message

        # Verify flush was called
        mock_flush.assert_called_once()


def test_second_interrupt_raises_system_exit():
    """Test that second interrupt raises SystemExit with code 130."""
    handler = InterruptHandler()

    # First interrupt
    handler._handle_signal(signal.SIGINT, None)
    assert handler.interrupted is True

    # Second interrupt should raise SystemExit
    with pytest.raises(SystemExit) as exc_info:
        handler._handle_signal(signal.SIGINT, None)

    assert exc_info.value.code == 130


def test_second_interrupt_writes_force_exit_message():
    """Test that second interrupt writes force exit message before raising."""
    handler = InterruptHandler()

    # First interrupt
    handler._handle_signal(signal.SIGINT, None)

    # Second interrupt
    with patch("sys.stderr.write") as mock_write, patch("sys.stderr.flush") as mock_flush:
        with pytest.raises(SystemExit):
            handler._handle_signal(signal.SIGINT, None)

        # Verify force exit message was written
        mock_write.assert_called_once()
        message = mock_write.call_args[0][0]
        assert "Force exiting" in message

        # Verify flush was called
        mock_flush.assert_called_once()


def test_cleanup_callback_exceptions_are_silenced():
    """Test that exceptions in cleanup callbacks don't prevent shutdown."""
    handler = InterruptHandler()

    # Register callbacks, one that raises
    good_callback = MagicMock()
    bad_callback = MagicMock(side_effect=RuntimeError("Test error"))
    another_good_callback = MagicMock()

    handler.on_interrupt(good_callback)
    handler.on_interrupt(bad_callback)
    handler.on_interrupt(another_good_callback)

    # Trigger interrupt - should not raise despite bad callback
    handler._handle_signal(signal.SIGINT, None)

    # Verify all callbacks were attempted
    good_callback.assert_called_once()
    bad_callback.assert_called_once()
    another_good_callback.assert_called_once()

    # Verify interrupt flag was still set
    assert handler.interrupted is True


# ===========================================================================
# Test callback registration
# ===========================================================================


def test_on_interrupt_registers_callback():
    """Test that on_interrupt() adds callback to list."""
    handler = InterruptHandler()
    callback = MagicMock()

    handler.on_interrupt(callback)

    assert callback in handler._cleanup_callbacks


def test_multiple_callbacks_can_be_registered():
    """Test that multiple cleanup callbacks can be registered."""
    handler = InterruptHandler()

    callback1 = MagicMock()
    callback2 = MagicMock()
    callback3 = MagicMock()

    handler.on_interrupt(callback1)
    handler.on_interrupt(callback2)
    handler.on_interrupt(callback3)

    assert len(handler._cleanup_callbacks) == 3
    assert callback1 in handler._cleanup_callbacks
    assert callback2 in handler._cleanup_callbacks
    assert callback3 in handler._cleanup_callbacks


# ===========================================================================
# Test SIGTERM handling
# ===========================================================================


def test_sigterm_handled_same_as_sigint():
    """Test that SIGTERM is handled the same way as SIGINT."""
    handler = InterruptHandler()

    # First SIGTERM
    handler._handle_signal(signal.SIGTERM, None)
    assert handler.interrupted is True

    # Second SIGTERM should raise SystemExit
    with pytest.raises(SystemExit) as exc_info:
        handler._handle_signal(signal.SIGTERM, None)

    assert exc_info.value.code == 130


# ===========================================================================
# Integration tests with RunLoop
# ===========================================================================


def test_interrupt_handler_integration_with_run_loop():
    """Test that InterruptHandler integrates correctly with RunLoop."""
    from cub.core.run.loop import RunLoop
    from cub.core.run.models import RunConfig

    # Create mock backends
    task_backend = MagicMock()
    task_backend.get_ready_tasks.return_value = []
    task_backend.get_task_counts.return_value = MagicMock(remaining=0, total=0, closed=0)

    harness_backend = MagicMock()

    # Create interrupt handler
    interrupt_handler = InterruptHandler()

    # Create run config
    config = RunConfig(
        once=True,
        harness_name="test",
        project_dir="/tmp/test",
    )

    # Create run loop with interrupt handler
    run_loop = RunLoop(
        config=config,
        task_backend=task_backend,
        harness_backend=harness_backend,
        interrupt_handler=interrupt_handler,
    )

    # Verify interrupt handler was set
    assert run_loop.interrupt_handler is interrupt_handler

    # Simulate interrupt
    interrupt_handler._interrupted = True

    # Execute loop and collect events
    events = list(run_loop.execute())

    # Verify interrupt was detected
    event_types = [e.event_type for e in events]
    from cub.core.run.models import RunEventType

    assert RunEventType.INTERRUPT_RECEIVED in event_types


def test_run_loop_backward_compatibility_without_interrupt_handler():
    """Test that RunLoop still works without interrupt_handler for backward compatibility."""
    from cub.core.run.loop import RunLoop
    from cub.core.run.models import RunConfig

    # Create mock backends
    task_backend = MagicMock()
    task_backend.get_ready_tasks.return_value = []
    task_backend.get_task_counts.return_value = MagicMock(remaining=0, total=0, closed=0)

    harness_backend = MagicMock()

    # Create run config
    config = RunConfig(
        once=True,
        harness_name="test",
        project_dir="/tmp/test",
    )

    # Create run loop WITHOUT interrupt handler (old way)
    run_loop = RunLoop(
        config=config,
        task_backend=task_backend,
        harness_backend=harness_backend,
    )

    # Verify it still works with the old interrupted flag
    assert run_loop.interrupt_handler is None
    assert run_loop.interrupted is False

    # Simulate interrupt the old way
    run_loop.interrupted = True

    # Execute loop and collect events
    events = list(run_loop.execute())

    # Verify interrupt was detected
    event_types = [e.event_type for e in events]
    from cub.core.run.models import RunEventType

    assert RunEventType.INTERRUPT_RECEIVED in event_types

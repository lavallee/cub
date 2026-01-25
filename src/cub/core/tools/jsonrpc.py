"""
JSON-RPC 2.0 protocol helpers for MCP and other JSON-RPC communication.

This module provides utilities for building, parsing, and validating JSON-RPC 2.0
messages. It's extracted from the MCP stdio adapter for reuse across different
adapters and contexts.

Reference: https://www.jsonrpc.org/specification
"""

from __future__ import annotations

import json
from typing import Any


class JSONRPCError(Exception):
    """Base exception for JSON-RPC protocol errors."""

    def __init__(self, message: str, code: int | None = None, data: Any = None):
        """
        Initialize JSON-RPC error.

        Args:
            message: Error message
            code: JSON-RPC error code (optional)
            data: Additional error data (optional)
        """
        super().__init__(message)
        self.code = code
        self.data = data


class JSONRPCParseError(JSONRPCError):
    """Raised when JSON-RPC message cannot be parsed."""

    def __init__(self, message: str, raw_data: str | None = None):
        super().__init__(message, code=-32700, data=raw_data)


class JSONRPCInvalidRequestError(JSONRPCError):
    """Raised when JSON-RPC request is invalid."""

    def __init__(self, message: str, data: Any = None):
        super().__init__(message, code=-32600, data=data)


class JSONRPCResponse:
    """
    Represents a parsed JSON-RPC 2.0 response.

    Attributes:
        id: Request identifier (must match the request)
        result: Result data (present on success)
        error: Error object (present on error)
        is_success: Whether this is a success response
    """

    def __init__(
        self,
        response_id: str | int | None,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ):
        """
        Initialize JSON-RPC response.

        Args:
            response_id: The response ID (must match request ID)
            result: The result data (for success responses)
            error: The error object (for error responses)
        """
        self.id = response_id
        self.result = result
        self.error = error

    @property
    def is_success(self) -> bool:
        """Return True if this is a success response (has result, no error)."""
        return self.error is None

    @property
    def error_code(self) -> int | str | None:
        """Get error code from error object, if present."""
        if self.error:
            return self.error.get("code")
        return None

    @property
    def error_message(self) -> str | None:
        """Get error message from error object, if present."""
        if self.error:
            return self.error.get("message")
        return None

    @property
    def error_data(self) -> Any:
        """Get error data from error object, if present."""
        if self.error:
            return self.error.get("data")
        return None

    def __repr__(self) -> str:
        """Return string representation of response."""
        if self.is_success:
            return f"JSONRPCResponse(id={self.id}, result={self.result!r})"
        else:
            return f"JSONRPCResponse(id={self.id}, error={self.error!r})"


def build_request(
    method: str,
    params: dict[str, Any] | list[Any] | None = None,
    request_id: str | int | None = None,
) -> str:
    """
    Build a JSON-RPC 2.0 request message.

    Args:
        method: The method name to call
        params: Method parameters (dict for named params, list for positional)
        request_id: Request identifier (None for notifications)

    Returns:
        JSON-RPC request as string with newline terminator

    Example:
        >>> build_request("tools/call", {"name": "read_file", "path": "/tmp/test"}, "1")
        '{"jsonrpc": "2.0", "id": "1", "method": "tools/call", "params": {...}}\\n'
    """
    request: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
    }

    # Only include params if provided
    if params is not None:
        request["params"] = params

    # Only include id if provided (notifications have no id)
    if request_id is not None:
        request["id"] = request_id

    # JSON-RPC messages are newline-delimited
    return json.dumps(request) + "\n"


def parse_response(
    raw_output: str,
    expected_id: str | int | None = None,
) -> JSONRPCResponse:
    """
    Parse a JSON-RPC 2.0 response from raw output.

    Handles:
    - Empty responses
    - Newline-delimited JSON (multiple messages)
    - ID validation (if expected_id provided)
    - Malformed JSON
    - Invalid JSON-RPC format

    Args:
        raw_output: Raw output string from JSON-RPC server
        expected_id: Expected request ID for validation (optional)

    Returns:
        Parsed JSONRPCResponse object

    Raises:
        JSONRPCParseError: If response cannot be parsed
        JSONRPCInvalidRequestError: If response format is invalid

    Example:
        >>> parse_response('{"jsonrpc": "2.0", "id": "1", "result": {"status": "ok"}}')
        JSONRPCResponse(id='1', result={'status': 'ok'})
    """
    raw_output = raw_output.strip()

    if not raw_output:
        raise JSONRPCParseError("Empty response from JSON-RPC server")

    # Handle newline-delimited JSON - split by lines
    lines = [line.strip() for line in raw_output.split("\n") if line.strip()]

    if not lines:
        raise JSONRPCParseError("No valid response lines in JSON-RPC output")

    # Try to find a response matching the expected ID (if provided)
    response_obj: dict[str, Any] | None = None

    if expected_id is not None:
        # Look for response with matching ID
        for line in lines:
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict) and parsed.get("id") == expected_id:
                    response_obj = parsed
                    break
            except json.JSONDecodeError:
                continue

    # If no matching response found (or no expected_id), use the last valid JSON object
    if response_obj is None:
        for line in reversed(lines):
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    response_obj = parsed
                    break
            except json.JSONDecodeError:
                continue

    if response_obj is None:
        raise JSONRPCParseError(
            "No valid JSON-RPC response found in output",
            raw_data=raw_output[:500],
        )

    # Validate JSON-RPC 2.0 format
    if not validate_response_format(response_obj):
        raise JSONRPCInvalidRequestError(
            "Invalid JSON-RPC 2.0 response format",
            data=response_obj,
        )

    # Extract fields
    response_id = response_obj.get("id")
    result = response_obj.get("result")
    error = response_obj.get("error")

    return JSONRPCResponse(response_id=response_id, result=result, error=error)


def validate_response_format(response: dict[str, Any]) -> bool:
    """
    Validate that a response object conforms to JSON-RPC 2.0 format.

    A valid response must:
    - Have "jsonrpc": "2.0"
    - Have an "id" field
    - Have either "result" OR "error" (but not both, not neither)

    Args:
        response: Response object to validate

    Returns:
        True if response format is valid, False otherwise

    Example:
        >>> validate_response_format({"jsonrpc": "2.0", "id": "1", "result": {}})
        True
        >>> validate_response_format({"jsonrpc": "2.0", "id": "1"})  # Missing result/error
        False
    """
    if not isinstance(response, dict):
        return False

    # Must have jsonrpc version
    if response.get("jsonrpc") != "2.0":
        return False

    # Must have id field (can be null for some error cases)
    if "id" not in response:
        return False

    # Must have exactly one of result or error
    has_result = "result" in response
    has_error = "error" in response

    if has_result == has_error:  # Both true or both false is invalid
        return False

    # If error is present, validate error object structure
    if has_error:
        error = response.get("error")
        if not isinstance(error, dict):
            return False
        # Error must have code and message
        if "code" not in error or "message" not in error:
            return False

    return True


def classify_error(error_code: int | str) -> str:
    """
    Classify JSON-RPC error code to error type category.

    Maps JSON-RPC 2.0 standard error codes to semantic error types
    used by the tool execution system.

    Args:
        error_code: JSON-RPC error code (integer or string)

    Returns:
        Error type: "protocol", "validation", "execution", or "unknown"

    Error code mapping:
        -32700: Parse error → protocol
        -32600: Invalid Request → validation
        -32601: Method not found → validation
        -32602: Invalid params → validation
        -32603: Internal error → execution
        -32000 to -32099: Server error (reserved) → execution
        Others: unknown

    Example:
        >>> classify_error(-32602)
        'validation'
        >>> classify_error(-32603)
        'execution'
    """
    try:
        code = int(error_code)
    except (TypeError, ValueError):
        return "unknown"

    # JSON-RPC 2.0 standard error codes
    if code == -32700:  # Parse error
        return "protocol"
    elif code == -32600:  # Invalid Request
        return "validation"
    elif code == -32601:  # Method not found
        return "validation"
    elif code == -32602:  # Invalid params
        return "validation"
    elif code == -32603:  # Internal error
        return "execution"
    elif -32099 <= code <= -32000:  # Server error (reserved range)
        return "execution"
    else:
        return "unknown"


def filter_internal_params(params: dict[str, Any], prefix: str = "_") -> dict[str, Any]:
    """
    Filter out internal parameters from params dict.

    Internal parameters (prefixed with underscore by default) are used for
    adapter configuration and should not be sent in JSON-RPC requests.

    Args:
        params: Parameters dictionary
        prefix: Prefix marking internal params (default: "_")

    Returns:
        Filtered params dict without internal parameters

    Example:
        >>> filter_internal_params({"_config": {...}, "name": "test", "_debug": True})
        {"name": "test"}
    """
    return {k: v for k, v in params.items() if not k.startswith(prefix)}

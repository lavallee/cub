#!/usr/bin/env python3
"""
Mock MCP server for testing.

A simple JSON-RPC 2.0 server that reads from stdin and writes to stdout,
implementing a minimal subset of the MCP protocol for testing purposes.
"""

import json
import sys
from typing import Any


def send_response(
    response_id: str | int | None, result: Any = None, error: dict[str, Any] | None = None
) -> None:
    """Send a JSON-RPC 2.0 response to stdout."""
    response: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": response_id,
    }

    if error:
        response["error"] = error
    else:
        response["result"] = result

    # Write response as newline-delimited JSON
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def send_error(response_id: str | int | None, code: int, message: str, data: Any = None) -> None:
    """Send a JSON-RPC 2.0 error response."""
    error = {
        "code": code,
        "message": message,
    }
    if data is not None:
        error["data"] = data

    send_response(response_id, error=error)


def handle_initialize(request_id: str | int, params: dict[str, Any]) -> None:
    """Handle initialize request."""
    send_response(
        request_id,
        result={
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": "mock-mcp-server",
                "version": "1.0.0",
            },
        },
    )


def handle_tools_list(request_id: str | int, params: dict[str, Any]) -> None:
    """Handle tools/list request."""
    send_response(
        request_id,
        result={
            "tools": [
                {
                    "name": "read_file",
                    "description": "Read contents of a file",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path to read",
                            },
                        },
                        "required": ["path"],
                    },
                },
                {
                    "name": "write_file",
                    "description": "Write contents to a file",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path to write",
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to write",
                            },
                        },
                        "required": ["path", "content"],
                    },
                },
            ]
        },
    )


def handle_tools_call(request_id: str | int, params: dict[str, Any]) -> None:
    """Handle tools/call request."""
    name = params.get("name")
    arguments = params.get("arguments", {})

    if name == "read_file":
        path = arguments.get("path")
        if not path:
            send_error(
                request_id,
                -32602,
                "Invalid params",
                "Missing required parameter: path",
            )
            return

        # Mock file read response
        send_response(
            request_id,
            result={
                "content": [
                    {
                        "type": "text",
                        "text": f"Mock content of {path}",
                    }
                ]
            },
        )

    elif name == "write_file":
        path = arguments.get("path")
        content = arguments.get("content")

        if not path or not content:
            send_error(
                request_id,
                -32602,
                "Invalid params",
                "Missing required parameters: path and content",
            )
            return

        # Mock file write response
        send_response(
            request_id,
            result={
                "content": [
                    {
                        "type": "text",
                        "text": f"Successfully wrote {len(content)} bytes to {path}",
                    }
                ]
            },
        )

    elif name == "error_test":
        # Simulate an error for testing
        send_error(
            request_id,
            -32000,
            "Server error",
            "Simulated error for testing",
        )

    else:
        send_error(
            request_id,
            -32601,
            "Method not found",
            f"Unknown tool: {name}",
        )


def handle_request(request: dict[str, Any]) -> None:
    """Handle a JSON-RPC request."""
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    # Validate request_id is the correct type (for type checker)
    if request_id is not None and not isinstance(request_id, (str, int)):
        send_error(None, -32600, "Invalid Request", "Invalid request ID type")
        return

    # Handle different methods
    if method == "initialize":
        handle_initialize(request_id, params)  # type: ignore[arg-type]
    elif method == "tools/list":
        handle_tools_list(request_id, params)  # type: ignore[arg-type]
    elif method == "tools/call":
        handle_tools_call(request_id, params)  # type: ignore[arg-type]
    else:
        send_error(
            request_id,
            -32601,
            "Method not found",
            f"Unknown method: {method}",
        )


def main() -> None:
    """Main server loop - read JSON-RPC requests from stdin and respond on stdout."""
    # Optional: Send initialization message (some MCP servers do this)
    # sys.stdout.write('{"jsonrpc": "2.0", "method": "server/ready", "params": {}}\n')
    # sys.stdout.flush()

    # Read requests from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)

            # Validate basic JSON-RPC structure
            if request.get("jsonrpc") != "2.0":
                send_error(
                    request.get("id"),
                    -32600,
                    "Invalid Request",
                    "JSON-RPC version must be 2.0",
                )
                continue

            if "method" not in request:
                send_error(
                    request.get("id"),
                    -32600,
                    "Invalid Request",
                    "Missing method field",
                )
                continue

            # Handle the request
            handle_request(request)

        except json.JSONDecodeError as e:
            send_error(
                None,
                -32700,
                "Parse error",
                str(e),
            )
        except Exception as e:
            send_error(
                None,
                -32603,
                "Internal error",
                str(e),
            )


if __name__ == "__main__":
    main()

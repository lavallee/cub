"""
Tests for JSON-RPC 2.0 protocol helpers.
"""

import json

import pytest

from cub.core.tools.jsonrpc import (
    JSONRPCError,
    JSONRPCInvalidRequestError,
    JSONRPCParseError,
    JSONRPCResponse,
    build_request,
    classify_error,
    filter_internal_params,
    parse_response,
    validate_response_format,
)


class TestBuildRequest:
    """Tests for build_request function."""

    def test_build_request_with_dict_params(self):
        """Test building request with dict params."""
        request = build_request("tools/call", {"name": "test", "value": 123}, "req-1")

        # Parse and validate
        parsed = json.loads(request.strip())
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == "req-1"
        assert parsed["method"] == "tools/call"
        assert parsed["params"] == {"name": "test", "value": 123}
        assert request.endswith("\n")

    def test_build_request_with_list_params(self):
        """Test building request with list params."""
        request = build_request("subtract", [42, 23], 1)

        parsed = json.loads(request.strip())
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == 1
        assert parsed["method"] == "subtract"
        assert parsed["params"] == [42, 23]

    def test_build_request_without_params(self):
        """Test building request without params."""
        request = build_request("getInfo", None, "info-1")

        parsed = json.loads(request.strip())
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == "info-1"
        assert parsed["method"] == "getInfo"
        assert "params" not in parsed  # Should not include params if None

    def test_build_request_notification(self):
        """Test building notification (no id)."""
        request = build_request("notify", {"event": "update"}, None)

        parsed = json.loads(request.strip())
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["method"] == "notify"
        assert parsed["params"] == {"event": "update"}
        assert "id" not in parsed  # Notifications don't have id

    def test_build_request_empty_params(self):
        """Test building request with empty params dict."""
        request = build_request("noArgs", {}, "empty-1")

        parsed = json.loads(request.strip())
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == "empty-1"
        assert parsed["method"] == "noArgs"
        assert parsed["params"] == {}


class TestParseResponse:
    """Tests for parse_response function."""

    def test_parse_success_response(self):
        """Test parsing successful response."""
        raw = '{"jsonrpc": "2.0", "id": "1", "result": {"status": "ok"}}\n'

        response = parse_response(raw, "1")

        assert response.id == "1"
        assert response.result == {"status": "ok"}
        assert response.error is None
        assert response.is_success is True

    def test_parse_error_response(self):
        """Test parsing error response."""
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "2",
                "error": {"code": -32602, "message": "Invalid params"},
            }
        )

        response = parse_response(raw, "2")

        assert response.id == "2"
        assert response.result is None
        assert response.error == {"code": -32602, "message": "Invalid params"}
        assert response.is_success is False
        assert response.error_code == -32602
        assert response.error_message == "Invalid params"

    def test_parse_error_response_with_data(self):
        """Test parsing error response with additional data."""
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "3",
                "error": {
                    "code": -32600,
                    "message": "Invalid Request",
                    "data": {"details": "Missing required field"},
                },
            }
        )

        response = parse_response(raw, "3")

        assert response.error_code == -32600
        assert response.error_message == "Invalid Request"
        assert response.error_data == {"details": "Missing required field"}

    def test_parse_multiline_response(self):
        """Test parsing newline-delimited multiple JSON objects."""
        # Simulate MCP server outputting multiple messages
        raw = (
            '{"jsonrpc": "2.0", "method": "initialized", "params": {}}\n'
            '{"jsonrpc": "2.0", "id": "test-1", "result": {"data": "response"}}\n'
        )

        response = parse_response(raw, "test-1")

        assert response.id == "test-1"
        assert response.result == {"data": "response"}
        assert response.is_success is True

    def test_parse_response_with_matching_id(self):
        """Test that parser finds response with matching ID."""
        raw = (
            '{"jsonrpc": "2.0", "id": "other", "result": "wrong"}\n'
            '{"jsonrpc": "2.0", "id": "correct", "result": "right"}\n'
        )

        response = parse_response(raw, "correct")

        assert response.id == "correct"
        assert response.result == "right"

    def test_parse_response_no_expected_id(self):
        """Test parsing response without expected ID (uses last valid JSON)."""
        raw = (
            '{"jsonrpc": "2.0", "id": "1", "result": "first"}\n'
            '{"jsonrpc": "2.0", "id": "2", "result": "second"}\n'
        )

        response = parse_response(raw)

        # Should use the last valid response
        assert response.id == "2"
        assert response.result == "second"

    def test_parse_empty_response(self):
        """Test parsing empty response raises error."""
        with pytest.raises(JSONRPCParseError) as exc_info:
            parse_response("")

        assert "Empty response" in str(exc_info.value)

    def test_parse_whitespace_only_response(self):
        """Test parsing whitespace-only response raises error."""
        with pytest.raises(JSONRPCParseError) as exc_info:
            parse_response("   \n  \n  ")

        assert "Empty response" in str(exc_info.value)

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON raises error."""
        with pytest.raises(JSONRPCParseError) as exc_info:
            parse_response("not valid json {")

        assert "No valid JSON-RPC response" in str(exc_info.value)

    def test_parse_malformed_json_mixed_with_valid(self):
        """Test parsing output with some invalid JSON lines."""
        raw = (
            "some random text\n"
            '{"jsonrpc": "2.0", "id": "1", "result": "valid"}\n'
            "more garbage\n"
        )

        response = parse_response(raw, "1")

        assert response.id == "1"
        assert response.result == "valid"

    def test_parse_response_missing_jsonrpc_field(self):
        """Test parsing response without jsonrpc field raises error."""
        raw = '{"id": "1", "result": "data"}\n'

        with pytest.raises(JSONRPCInvalidRequestError) as exc_info:
            parse_response(raw, "1")

        assert "Invalid JSON-RPC 2.0 response format" in str(exc_info.value)

    def test_parse_response_wrong_jsonrpc_version(self):
        """Test parsing response with wrong version raises error."""
        raw = '{"jsonrpc": "1.0", "id": "1", "result": "data"}\n'

        with pytest.raises(JSONRPCInvalidRequestError) as exc_info:
            parse_response(raw, "1")

        assert "Invalid JSON-RPC 2.0 response format" in str(exc_info.value)

    def test_parse_response_missing_id(self):
        """Test parsing response without id field raises error."""
        raw = '{"jsonrpc": "2.0", "result": "data"}\n'

        with pytest.raises(JSONRPCInvalidRequestError) as exc_info:
            parse_response(raw)

        assert "Invalid JSON-RPC 2.0 response format" in str(exc_info.value)

    def test_parse_response_with_both_result_and_error(self):
        """Test parsing response with both result and error raises error."""
        raw = (
            '{"jsonrpc": "2.0", "id": "1", "result": "ok", '
            '"error": {"code": -1, "message": "err"}}\n'
        )

        with pytest.raises(JSONRPCInvalidRequestError) as exc_info:
            parse_response(raw, "1")

        assert "Invalid JSON-RPC 2.0 response format" in str(exc_info.value)

    def test_parse_response_with_neither_result_nor_error(self):
        """Test parsing response with neither result nor error raises error."""
        raw = '{"jsonrpc": "2.0", "id": "1"}\n'

        with pytest.raises(JSONRPCInvalidRequestError) as exc_info:
            parse_response(raw, "1")

        assert "Invalid JSON-RPC 2.0 response format" in str(exc_info.value)


class TestValidateResponseFormat:
    """Tests for validate_response_format function."""

    def test_validate_valid_success_response(self):
        """Test validation of valid success response."""
        response = {"jsonrpc": "2.0", "id": "1", "result": {"data": "test"}}
        assert validate_response_format(response) is True

    def test_validate_valid_error_response(self):
        """Test validation of valid error response."""
        response = {
            "jsonrpc": "2.0",
            "id": "1",
            "error": {"code": -32600, "message": "Invalid Request"},
        }
        assert validate_response_format(response) is True

    def test_validate_null_id(self):
        """Test validation with null id (allowed in spec for some errors)."""
        response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Invalid Request"},
        }
        assert validate_response_format(response) is True

    def test_validate_missing_jsonrpc(self):
        """Test validation fails without jsonrpc field."""
        response = {"id": "1", "result": "data"}
        assert validate_response_format(response) is False

    def test_validate_wrong_jsonrpc_version(self):
        """Test validation fails with wrong version."""
        response = {"jsonrpc": "1.0", "id": "1", "result": "data"}
        assert validate_response_format(response) is False

    def test_validate_missing_id(self):
        """Test validation fails without id field."""
        response = {"jsonrpc": "2.0", "result": "data"}
        assert validate_response_format(response) is False

    def test_validate_both_result_and_error(self):
        """Test validation fails with both result and error."""
        response = {
            "jsonrpc": "2.0",
            "id": "1",
            "result": "ok",
            "error": {"code": -1, "message": "err"},
        }
        assert validate_response_format(response) is False

    def test_validate_neither_result_nor_error(self):
        """Test validation fails without result or error."""
        response = {"jsonrpc": "2.0", "id": "1"}
        assert validate_response_format(response) is False

    def test_validate_error_missing_code(self):
        """Test validation fails if error missing code."""
        response = {
            "jsonrpc": "2.0",
            "id": "1",
            "error": {"message": "Error without code"},
        }
        assert validate_response_format(response) is False

    def test_validate_error_missing_message(self):
        """Test validation fails if error missing message."""
        response = {"jsonrpc": "2.0", "id": "1", "error": {"code": -32600}}
        assert validate_response_format(response) is False

    def test_validate_error_not_dict(self):
        """Test validation fails if error is not a dict."""
        response = {"jsonrpc": "2.0", "id": "1", "error": "string error"}
        assert validate_response_format(response) is False

    def test_validate_non_dict_response(self):
        """Test validation fails for non-dict response."""
        assert validate_response_format("not a dict") is False
        assert validate_response_format([1, 2, 3]) is False
        assert validate_response_format(None) is False


class TestClassifyError:
    """Tests for classify_error function."""

    def test_classify_parse_error(self):
        """Test classification of parse error."""
        assert classify_error(-32700) == "protocol"

    def test_classify_invalid_request(self):
        """Test classification of invalid request."""
        assert classify_error(-32600) == "validation"

    def test_classify_method_not_found(self):
        """Test classification of method not found."""
        assert classify_error(-32601) == "validation"

    def test_classify_invalid_params(self):
        """Test classification of invalid params."""
        assert classify_error(-32602) == "validation"

    def test_classify_internal_error(self):
        """Test classification of internal error."""
        assert classify_error(-32603) == "execution"

    def test_classify_server_error_range(self):
        """Test classification of server error range."""
        assert classify_error(-32000) == "execution"
        assert classify_error(-32050) == "execution"
        assert classify_error(-32099) == "execution"

    def test_classify_unknown_error_code(self):
        """Test classification of unknown error codes."""
        assert classify_error(0) == "unknown"
        assert classify_error(100) == "unknown"
        assert classify_error(-100) == "unknown"
        assert classify_error(-33000) == "unknown"

    def test_classify_string_error_code(self):
        """Test classification of string error code (invalid)."""
        assert classify_error("not_a_number") == "unknown"

    def test_classify_convertible_string(self):
        """Test classification of string that can be converted to int."""
        assert classify_error("-32602") == "validation"
        assert classify_error("-32603") == "execution"


class TestFilterInternalParams:
    """Tests for filter_internal_params function."""

    def test_filter_internal_params_default_prefix(self):
        """Test filtering params with default _ prefix."""
        params = {
            "_mcp_config": {"command": "test"},
            "_internal": True,
            "name": "test",
            "value": 123,
        }

        filtered = filter_internal_params(params)

        assert filtered == {"name": "test", "value": 123}
        assert "_mcp_config" not in filtered
        assert "_internal" not in filtered

    def test_filter_internal_params_custom_prefix(self):
        """Test filtering params with custom prefix."""
        params = {
            "internal_config": {"command": "test"},
            "internal_debug": True,
            "name": "test",
            "value": 123,
        }

        filtered = filter_internal_params(params, prefix="internal_")

        assert filtered == {"name": "test", "value": 123}
        assert "internal_config" not in filtered
        assert "internal_debug" not in filtered

    def test_filter_internal_params_no_internal(self):
        """Test filtering when there are no internal params."""
        params = {"name": "test", "value": 123}

        filtered = filter_internal_params(params)

        assert filtered == params

    def test_filter_internal_params_all_internal(self):
        """Test filtering when all params are internal."""
        params = {"_config": {}, "_debug": True, "_test": "value"}

        filtered = filter_internal_params(params)

        assert filtered == {}

    def test_filter_internal_params_empty_dict(self):
        """Test filtering empty params dict."""
        filtered = filter_internal_params({})
        assert filtered == {}


class TestJSONRPCResponse:
    """Tests for JSONRPCResponse class."""

    def test_response_success(self):
        """Test success response properties."""
        response = JSONRPCResponse(response_id="1", result={"data": "test"})

        assert response.id == "1"
        assert response.result == {"data": "test"}
        assert response.error is None
        assert response.is_success is True
        assert response.error_code is None
        assert response.error_message is None
        assert response.error_data is None

    def test_response_error(self):
        """Test error response properties."""
        error_obj = {"code": -32602, "message": "Invalid params", "data": "extra"}
        response = JSONRPCResponse(response_id="2", error=error_obj)

        assert response.id == "2"
        assert response.result is None
        assert response.error == error_obj
        assert response.is_success is False
        assert response.error_code == -32602
        assert response.error_message == "Invalid params"
        assert response.error_data == "extra"

    def test_response_repr_success(self):
        """Test string representation of success response."""
        response = JSONRPCResponse(response_id="1", result="ok")
        repr_str = repr(response)

        assert "JSONRPCResponse" in repr_str
        assert "id=1" in repr_str or "id='1'" in repr_str
        assert "result='ok'" in repr_str

    def test_response_repr_error(self):
        """Test string representation of error response."""
        response = JSONRPCResponse(
            response_id="2", error={"code": -1, "message": "err"}
        )
        repr_str = repr(response)

        assert "JSONRPCResponse" in repr_str
        assert "id=2" in repr_str or "id='2'" in repr_str
        assert "error=" in repr_str


class TestJSONRPCExceptions:
    """Tests for JSON-RPC exception classes."""

    def test_jsonrpc_error_base(self):
        """Test base JSONRPCError exception."""
        error = JSONRPCError("Test error", code=-1, data={"info": "test"})

        assert str(error) == "Test error"
        assert error.code == -1
        assert error.data == {"info": "test"}

    def test_jsonrpc_parse_error(self):
        """Test JSONRPCParseError exception."""
        error = JSONRPCParseError("Parse failed", raw_data="bad json")

        assert str(error) == "Parse failed"
        assert error.code == -32700
        assert error.data == "bad json"

    def test_jsonrpc_invalid_request(self):
        """Test JSONRPCInvalidRequestError exception."""
        error = JSONRPCInvalidRequestError(
            "Invalid format", data={"field": "missing"}
        )

        assert str(error) == "Invalid format"
        assert error.code == -32600
        assert error.data == {"field": "missing"}

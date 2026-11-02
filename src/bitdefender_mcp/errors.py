"""Structured error envelope shared by every tool.

GravityZone signals failures two ways: an HTTP status code, or a JSON-RPC
2.0 `error` object in an HTTP 200 body. Both get mapped onto the same fixed
vocabulary so agents can branch on `code` without knowing which transport
layer the failure came from.
"""

from __future__ import annotations

import json
from typing import Literal

ErrorCode = Literal[
    "not_configured",
    "unauthorized",
    "not_found",
    "invalid_argument",
    "rate_limited",
    "upstream_error",
]

# GravityZone JSON-RPC error codes (API Guide, JSON-RPC 2.0 reserved range
# plus the vendor's own -32000 "Server error").
_JSONRPC_CODE_MAP: dict[int, ErrorCode] = {
    -32700: "upstream_error",  # Parse error
    -32600: "invalid_argument",  # Invalid Request
    -32601: "not_found",  # Method not found (used for unknown ids by GravityZone)
    -32602: "invalid_argument",  # Invalid params
    -32000: "upstream_error",  # Server error
}

_HTTP_CODE_MAP: dict[int, ErrorCode] = {
    401: "unauthorized",
    403: "unauthorized",
    404: "not_found",
    429: "rate_limited",
}

_RETRYABLE: set[ErrorCode] = {"rate_limited", "upstream_error"}


class GravityZoneError(Exception):
    """Raised by the API client; carries enough detail to map to an envelope."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        jsonrpc_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.http_status = http_status
        self.jsonrpc_code = jsonrpc_code


def classify(http_status: int | None, jsonrpc_code: int | None) -> ErrorCode:
    """Map a GravityZone HTTP status / JSON-RPC code pair to a fixed error code."""
    if http_status is not None and http_status >= 500:
        return "upstream_error"
    if http_status in _HTTP_CODE_MAP:
        return _HTTP_CODE_MAP[http_status]
    if jsonrpc_code is not None and jsonrpc_code in _JSONRPC_CODE_MAP:
        return _JSONRPC_CODE_MAP[jsonrpc_code]
    return "upstream_error"


def error_envelope(code: ErrorCode, message: str) -> str:
    """Build the fixed-shape JSON error envelope as a compact string.

    Never includes the credential or any raw upstream body -- `message` is
    expected to already be a short, sanitized description.
    """
    body = {
        "error": {
            "code": code,
            "message": message,
            "retryable": code in _RETRYABLE,
        }
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def envelope_from_exception(exc: GravityZoneError) -> str:
    code = classify(exc.http_status, exc.jsonrpc_code)
    return error_envelope(code, exc.message)


def not_configured_envelope(missing_header: str) -> str:
    return error_envelope(
        "not_configured",
        f"Missing required credential header: {missing_header}",
    )

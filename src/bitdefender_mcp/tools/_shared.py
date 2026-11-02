"""Shared helpers for tool modules: client construction, pagination, responses."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from ..client import GravityZoneClient
from ..credentials import API_KEY_HEADER, get_credentials
from ..errors import GravityZoneError, envelope_from_exception, not_configured_envelope
from ..logging_context import reset_tool_name, set_tool_name

DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 200
MAX_RESPONSE_CHARS = 20_000


def cap_per_page(per_page: int) -> int:
    """Clamp a client-supplied page size to GravityZone's and this service's limits."""
    if per_page <= 0:
        return DEFAULT_PER_PAGE
    return min(per_page, MAX_PER_PAGE)


def dump(payload: Any) -> str:
    """Serialize a tool result compactly, truncating if it would blow the token budget."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(text) <= MAX_RESPONSE_CHARS:
        return text
    if isinstance(payload, dict) and "items" in payload and isinstance(payload["items"], list):
        truncated = dict(payload)
        items = truncated["items"]
        while items and len(json.dumps(truncated, ensure_ascii=False, separators=(",", ":"))) > MAX_RESPONSE_CHARS:
            items.pop()
        truncated["has_more"] = True
        return json.dumps(truncated, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(
        {"truncated": True, "message": f"Result exceeded {MAX_RESPONSE_CHARS} characters and was dropped."},
        ensure_ascii=False,
        separators=(",", ":"),
    )


async def run_tool(tool_name: str, fn: Callable[[GravityZoneClient], Awaitable[Any]]) -> str:
    """Run a tool body against a per-request GravityZoneClient, mapping errors.

    Builds the client from the current request's credentials (set by
    CredentialMiddleware). Missing credentials here means the tool was
    invoked outside the middleware's scope -- treated the same as a missing
    header rather than raising, so the agent still gets a structured error
    (and nothing is logged, since no GravityZone call was ever made).

    `tool_name` is set into the request-scoped contextvar for the duration
    of the call so `GravityZoneClient.call` can tag its structured log line
    with which tool triggered it (PRD-21222 review round 1, finding 2).
    """
    creds = get_credentials()
    if creds is None:
        return not_configured_envelope(API_KEY_HEADER)

    tool_name_token = set_tool_name(tool_name)
    try:
        async with GravityZoneClient(api_key=creds.api_key, base_url=creds.base_url) as client:
            try:
                result = await fn(client)
            except GravityZoneError as exc:
                return envelope_from_exception(exc)
        return dump(result)
    finally:
        reset_tool_name(tool_name_token)

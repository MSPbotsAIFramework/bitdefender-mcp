"""tools/list snapshot, per-tool behavior, and error mapping.

Mocks GravityZone's JSON-RPC endpoints with respx -- no network, no vendor
account needed. Maps to the automated test cases in
docs/tickets/PRD-21222.ac.json: TC1, TC2, TC4, TC6, TC7, TC13, TC14, TC15, TC16.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from bitdefender_mcp.credentials import reset_credentials, set_credentials
from bitdefender_mcp.server import build_mcp
from tests.conftest import BASE_URL, credentials

JSONRPC_URL_RE = rf"{BASE_URL}/v1.0/jsonrpc/.*"


def _text(result) -> str:
    content, _structured = result
    return content[0].text


# ---------------------------------------------------------------------------
# TC: tools/list snapshot
# ---------------------------------------------------------------------------


async def test_tools_list_snapshot(mcp):
    tools = await mcp.list_tools()
    names = sorted(t.name for t in tools)
    assert names == [
        "bitdefender_assign_incident",
        "bitdefender_change_incident_priority",
        "bitdefender_get_endpoint_details",
        "bitdefender_get_incident",
        "bitdefender_get_policy_details",
        "bitdefender_isolate_endpoint",
        "bitdefender_list_endpoints",
        "bitdefender_list_incidents",
        "bitdefender_list_policies",
        "bitdefender_restore_endpoint_from_isolation",
    ]
    assert len(tools) == 10

    by_name = {t.name: t for t in tools}
    assert by_name["bitdefender_list_policies"].annotations.readOnlyHint is True
    assert by_name["bitdefender_isolate_endpoint"].annotations.destructiveHint is True
    # every description stays within the SOP's token budget
    for tool in tools:
        assert tool.description is not None
        assert len(tool.description) <= 500
        assert len(tool.description.splitlines()[0]) <= 100


# ---------------------------------------------------------------------------
# TC1 / TC2 -- policies
# ---------------------------------------------------------------------------


async def test_list_policies_returns_paginated_items(mcp):
    with respx.mock(assert_all_called=True) as router:
        router.post(url__regex=JSONRPC_URL_RE).mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 1,
                    "result": {
                        "page": 1,
                        "perPage": 50,
                        "pagesCount": 1,
                        "total": 2,
                        "items": [
                            {"id": "p1", "name": "Default policy", "extraField": "ignored"},
                            {"id": "p2", "name": "Servers policy"},
                        ],
                    },
                },
            )
        )
        with credentials():
            result = await mcp.call_tool("bitdefender_list_policies", {})

    body = json.loads(_text(result))
    assert body["items"] == [
        {"id": "p1", "name": "Default policy"},
        {"id": "p2", "name": "Servers policy"},
    ]
    assert body["total"] == 2
    assert body["per_page"] == 50


async def test_list_policies_caps_per_page_at_200(mcp):
    with respx.mock(assert_all_called=True) as router:
        route = router.post(url__regex=JSONRPC_URL_RE).mock(
            return_value=httpx.Response(
                200, json={"id": 1, "result": {"page": 1, "perPage": 200, "pagesCount": 1, "total": 0, "items": []}}
            )
        )
        with credentials():
            await mcp.call_tool("bitdefender_list_policies", {"per_page": 500})

    sent = json.loads(route.calls.last.request.content)
    assert sent["params"]["perPage"] == 200


# ---------------------------------------------------------------------------
# TC4 -- endpoints
# ---------------------------------------------------------------------------


async def test_list_endpoints_returns_paginated_items(mcp):
    with respx.mock(assert_all_called=True) as router:
        router.post(url__regex=JSONRPC_URL_RE).mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 1,
                    "result": {
                        "page": 1,
                        "perPage": 50,
                        "pagesCount": 1,
                        "total": 1,
                        "items": [{"id": "e1", "name": "WIN-DESKTOP-01", "status": "online", "fqdn": "ignored"}],
                    },
                },
            )
        )
        with credentials():
            result = await mcp.call_tool("bitdefender_list_endpoints", {})

    body = json.loads(_text(result))
    assert body["items"] == [{"id": "e1", "name": "WIN-DESKTOP-01", "status": "online"}]


# ---------------------------------------------------------------------------
# TC6 / TC7 -- incidents
# ---------------------------------------------------------------------------


async def test_list_incidents_returns_paginated_items(mcp):
    with respx.mock(assert_all_called=True) as router:
        router.post(url__regex=JSONRPC_URL_RE).mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 1,
                    "result": {
                        "page": 1,
                        "perPage": 50,
                        "pagesCount": 1,
                        "total": 1,
                        "items": [
                            {
                                "id": "i1",
                                "name": "Ransomware detected on WIN-DESKTOP-01",
                                "priority": "high",
                                "status": "open",
                            }
                        ],
                    },
                },
            )
        )
        with credentials():
            result = await mcp.call_tool("bitdefender_list_incidents", {})

    body = json.loads(_text(result))
    assert body["items"] == [
        {"id": "i1", "name": "Ransomware detected on WIN-DESKTOP-01", "priority": "high", "status": "open"}
    ]


async def test_list_incidents_empty_tenant_returns_empty_items(mcp):
    with respx.mock(assert_all_called=True) as router:
        router.post(url__regex=JSONRPC_URL_RE).mock(
            return_value=httpx.Response(
                200, json={"id": 1, "result": {"page": 1, "perPage": 50, "pagesCount": 0, "total": 0, "items": []}}
            )
        )
        with credentials():
            result = await mcp.call_tool("bitdefender_list_incidents", {})

    body = json.loads(_text(result))
    assert body["items"] == []
    assert "error" not in body


# ---------------------------------------------------------------------------
# TC13 -- missing header, exercised at the tool layer (contextvar unset)
# ---------------------------------------------------------------------------


async def test_tool_without_credentials_returns_not_configured_envelope(mcp):
    # No `with credentials()` -- simulates a tool invoked with the contextvar unset.
    result = await mcp.call_tool("bitdefender_list_policies", {})
    body = json.loads(_text(result))
    assert body["error"]["code"] == "not_configured"
    assert "X-Bitdefender-Api-Key" in body["error"]["message"]


# ---------------------------------------------------------------------------
# TC14 -- error mapping
# ---------------------------------------------------------------------------


async def test_jsonrpc_invalid_params_maps_to_invalid_argument(mcp):
    with respx.mock(assert_all_called=True) as router:
        router.post(url__regex=JSONRPC_URL_RE).mock(
            return_value=httpx.Response(
                200, json={"id": 1, "error": {"code": -32602, "message": "Invalid params"}}
            )
        )
        with credentials():
            result = await mcp.call_tool("bitdefender_get_policy_details", {"policy_id": "p1"})

    body = json.loads(_text(result))
    assert body == {"error": {"code": "invalid_argument", "message": "Invalid params", "retryable": False}}


async def test_http_429_maps_to_rate_limited_after_retries_exhausted(mcp, monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    with respx.mock(assert_all_called=True) as router:
        router.post(url__regex=JSONRPC_URL_RE).mock(return_value=httpx.Response(429, headers={"Retry-After": "0"}))
        with credentials():
            result = await mcp.call_tool("bitdefender_list_policies", {})

    body = json.loads(_text(result))
    assert body["error"]["code"] == "rate_limited"
    assert body["error"]["retryable"] is True


async def test_http_401_maps_to_unauthorized(mcp):
    with respx.mock(assert_all_called=True) as router:
        router.post(url__regex=JSONRPC_URL_RE).mock(return_value=httpx.Response(401, json={"message": "bad key"}))
        with credentials(api_key="wrong-key"):
            result = await mcp.call_tool("bitdefender_list_policies", {})

    body = json.loads(_text(result))
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["retryable"] is False


# ---------------------------------------------------------------------------
# TC15 -- concurrent requests never cross tenants (AC13)
# ---------------------------------------------------------------------------


async def test_concurrent_requests_do_not_share_credentials(mcp):
    seen_auth_headers: list[str] = []

    def responder(request: httpx.Request) -> httpx.Response:
        seen_auth_headers.append(request.headers["Authorization"])
        # Echo back which tenant answered, derived from the Authorization header.
        return httpx.Response(
            200,
            json={
                "id": 1,
                "result": {
                    "page": 1,
                    "perPage": 50,
                    "pagesCount": 1,
                    "total": 1,
                    "items": [{"id": "p", "name": request.headers["Authorization"]}],
                },
            },
        )

    async def call_as(api_key: str) -> dict:
        token = set_credentials(api_key, BASE_URL)
        try:
            result = await mcp.call_tool("bitdefender_list_policies", {})
        finally:
            reset_credentials(token)
        return json.loads(_text(result))

    with respx.mock(assert_all_called=True) as router:
        router.post(url__regex=JSONRPC_URL_RE).mock(side_effect=responder)
        result_a, result_b = await asyncio.gather(
            call_as("tenant-a-key"),
            call_as("tenant-b-key"),
        )

    assert result_a["items"][0]["name"] != result_b["items"][0]["name"]
    assert len(set(seen_auth_headers)) == 2


# ---------------------------------------------------------------------------
# TC16 -- rate-limit backoff eventually succeeds (AC14)
# ---------------------------------------------------------------------------


async def test_rate_limit_backoff_then_success(mcp, monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(
                200,
                json={"id": 1, "result": {"page": 1, "perPage": 50, "pagesCount": 1, "total": 0, "items": []}},
            ),
        ]
    )

    with respx.mock(assert_all_called=True) as router:
        router.post(url__regex=JSONRPC_URL_RE).mock(side_effect=lambda request: next(responses))
        with credentials():
            result = await mcp.call_tool("bitdefender_list_policies", {})

    body = json.loads(_text(result))
    assert body["items"] == []
    assert "error" not in body


async def _no_sleep(_seconds: float) -> None:
    return None

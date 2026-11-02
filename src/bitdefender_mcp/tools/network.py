"""Network tools: enough endpoint-inventory visibility to resolve ids for incidents.

GravityZone's Network API (API Guide §2.4) is read-only for this ticket's
scope -- just enough to list endpoints and inspect one (AC3, AC4).
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import GravityZoneClient
from ._shared import cap_per_page, run_tool

SERVICE = "network"


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        description=(
            "List the tenant's managed GravityZone endpoints.\n"
            "Args: page (1-based, default 1), per_page (default 50, capped at 200)."
        ),
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def bitdefender_list_endpoints(page: int = 1, per_page: int = 50) -> str:
        effective_per_page = cap_per_page(per_page)

        async def call(client: GravityZoneClient) -> dict[str, Any]:
            result = await client.call(
                SERVICE,
                "getEndpointsList",
                {"page": page, "perPage": effective_per_page},
            )
            items = [
                {
                    "id": e.get("id"),
                    "name": e.get("name"),
                    "status": e.get("status"),
                }
                for e in result.get("items", [])
            ]
            return {
                "page": result.get("page", page),
                "per_page": effective_per_page,
                "pages_count": result.get("pagesCount"),
                "total": result.get("total"),
                "items": items,
            }

        return await run_tool("bitdefender_list_endpoints", call)

    @mcp.tool(
        description=(
            "Get a GravityZone endpoint's assigned policy and protection status.\n"
            "Args: endpoint_id (from bitdefender_list_endpoints)."
        ),
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def bitdefender_get_endpoint_details(endpoint_id: str) -> str:
        async def call(client: GravityZoneClient) -> dict[str, Any]:
            return await client.call(SERVICE, "getManagedEndpointDetails", {"endpointId": endpoint_id})

        return await run_tool("bitdefender_get_endpoint_details", call)

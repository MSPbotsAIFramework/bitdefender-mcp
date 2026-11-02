"""Policies tools: visibility into a tenant's configured endpoint-protection policies.

GravityZone's public Policies API (API Guide §2.6) is read-only -- there is
no documented method to create a policy or assign one to an endpoint/group,
so this module only exposes listing and detail lookup (AC1, AC2).
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import GravityZoneClient
from ._shared import cap_per_page, run_tool

SERVICE = "policies"


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        description=(
            "List the tenant's configured GravityZone endpoint-protection policies.\n"
            "Args: page (1-based, default 1), per_page (default 50, capped at 200)."
        ),
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def bitdefender_list_policies(page: int = 1, per_page: int = 50) -> str:
        effective_per_page = cap_per_page(per_page)

        async def call(client: GravityZoneClient) -> dict[str, Any]:
            result = await client.call(
                SERVICE,
                "getPoliciesList",
                {"page": page, "perPage": effective_per_page},
            )
            items = [
                {"id": p.get("id"), "name": p.get("name")}
                for p in result.get("items", [])
            ]
            return {
                "page": result.get("page", page),
                "per_page": effective_per_page,
                "pages_count": result.get("pagesCount"),
                "total": result.get("total"),
                "items": items,
            }

        return await run_tool("bitdefender_list_policies", call)

    @mcp.tool(
        description=(
            "Get a GravityZone policy's full configuration by id.\n"
            "Args: policy_id (from bitdefender_list_policies)."
        ),
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def bitdefender_get_policy_details(policy_id: str) -> str:
        async def call(client: GravityZoneClient) -> dict[str, Any]:
            return await client.call(SERVICE, "getPolicyDetails", {"policyId": policy_id})

        return await run_tool("bitdefender_get_policy_details", call)

"""Incidents tools: review and triage GravityZone security events.

Covers listing and inspecting incidents, changing priority, (re)assigning,
and the two endpoint response actions GravityZone exposes for an active
incident -- isolate and restore from isolation (API Guide §2.10).
"""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from ..client import GravityZoneClient
from ._shared import cap_per_page, run_tool

SERVICE = "incidents"

IncidentPriority = Literal["low", "medium", "high"]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        description=(
            "List the tenant's GravityZone security incidents, newest first.\n"
            "Args: page (1-based, default 1), per_page (default 50, capped at 200)."
        ),
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def bitdefender_list_incidents(page: int = 1, per_page: int = 50) -> str:
        effective_per_page = cap_per_page(per_page)

        async def call(client: GravityZoneClient) -> dict[str, Any]:
            result = await client.call(
                SERVICE,
                "getIncidentsList",
                {"page": page, "perPage": effective_per_page},
            )
            items = [
                {
                    "id": i.get("id"),
                    "name": i.get("name"),
                    "priority": i.get("priority"),
                    "status": i.get("status"),
                }
                for i in result.get("items", [])
            ]
            return {
                "page": result.get("page", page),
                "per_page": effective_per_page,
                "pages_count": result.get("pagesCount"),
                "total": result.get("total"),
                "items": items,
            }

        return await run_tool("bitdefender_list_incidents", call)

    @mcp.tool(
        description=(
            "Get a GravityZone incident's affected endpoints and timeline summary.\n"
            "Args: incident_id (from bitdefender_list_incidents)."
        ),
        annotations={"readOnlyHint": True, "idempotentHint": True},
    )
    async def bitdefender_get_incident(incident_id: str) -> str:
        async def call(client: GravityZoneClient) -> dict[str, Any]:
            return await client.call(SERVICE, "getIncident", {"incidentId": incident_id})

        return await run_tool("bitdefender_get_incident", call)

    @mcp.tool(
        description=(
            "Change a GravityZone incident's priority.\n"
            "Args: incident_id, priority (one of: low, medium, high)."
        ),
        annotations={"readOnlyHint": False, "idempotentHint": True},
    )
    async def bitdefender_change_incident_priority(incident_id: str, priority: IncidentPriority) -> str:
        async def call(client: GravityZoneClient) -> dict[str, Any]:
            await client.call(
                SERVICE,
                "changeIncidentPriority",
                {"incidentId": incident_id, "priority": priority},
            )
            return {"incident_id": incident_id, "priority": priority, "status": "updated"}

        return await run_tool("bitdefender_change_incident_priority", call)

    @mcp.tool(
        description=(
            "Assign a GravityZone incident to one or more GravityZone user ids.\n"
            "Args: incident_id, assignee_ids (one or more GravityZone user ids)."
        ),
        annotations={"readOnlyHint": False, "idempotentHint": True},
    )
    async def bitdefender_assign_incident(incident_id: str, assignee_ids: list[str]) -> str:
        async def call(client: GravityZoneClient) -> dict[str, Any]:
            await client.call(
                SERVICE,
                "assignIncident",
                {"incidentId": incident_id, "assigneeIds": assignee_ids},
            )
            return {"incident_id": incident_id, "assignee_ids": assignee_ids, "status": "assigned"}

        return await run_tool("bitdefender_assign_incident", call)

    @mcp.tool(
        description=(
            "Isolate a GravityZone endpoint from the network during an active incident.\n"
            "Disconnects the endpoint except for GravityZone's own management traffic; "
            "use only on an endpoint under active investigation. Args: endpoint_id."
        ),
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
    )
    async def bitdefender_isolate_endpoint(endpoint_id: str) -> str:
        async def call(client: GravityZoneClient) -> dict[str, Any]:
            result = await client.call(SERVICE, "createIsolateEndpointTask", {"endpointId": endpoint_id})
            task_id = result.get("taskId") if isinstance(result, dict) else result
            return {"endpoint_id": endpoint_id, "task_id": task_id, "status": "isolation_requested"}

        return await run_tool("bitdefender_isolate_endpoint", call)

    @mcp.tool(
        description=(
            "Restore a previously isolated GravityZone endpoint to normal network access.\n"
            "Args: endpoint_id (previously isolated)."
        ),
        annotations={"readOnlyHint": False, "idempotentHint": True},
    )
    async def bitdefender_restore_endpoint_from_isolation(endpoint_id: str) -> str:
        async def call(client: GravityZoneClient) -> dict[str, Any]:
            result = await client.call(
                SERVICE, "createRestoreEndpointFromIsolationTask", {"endpointId": endpoint_id}
            )
            task_id = result.get("taskId") if isinstance(result, dict) else result
            return {"endpoint_id": endpoint_id, "task_id": task_id, "status": "restore_requested"}

        return await run_tool("bitdefender_restore_endpoint_from_isolation", call)

"""FastMCP app factory and the Starlette app that wraps it.

Builds a stateless, DNS-rebinding-tolerant FastMCP server, registers every
tool module, and mounts it under `/mcp` alongside a dependency-free
`/health` endpoint. The MCP app's lifespan is hooked into the outer
Starlette app explicitly -- `Mount()` alone does not run a sub-app's
lifespan, and skipping this makes `/mcp` fail with "Task group is not
initialized" while `/health` keeps returning 200.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .middleware import CredentialMiddleware
from .tools import incidents, network, policies

SERVICE_INSTRUCTIONS = (
    "Bitdefender GravityZone endpoint protection and security-event (incident) "
    "management. Use the policies tools to see what protection a tenant has "
    "configured, the network tools to resolve endpoint ids, and the incidents "
    "tools to review, triage, and respond to security events. Typical flow: "
    "list_incidents to find what needs attention, get_incident for detail, "
    "then change_incident_priority / assign_incident for triage, or "
    "isolate_endpoint / restore_endpoint_from_isolation to contain and "
    "recover an affected endpoint. Policy authoring and assignment are not "
    "supported -- GravityZone's public API only exposes policy visibility."
)


def build_mcp() -> FastMCP:
    mcp = FastMCP(
        name="bitdefender-mcp",
        instructions=SERVICE_INSTRUCTIONS,
        stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    policies.register(mcp)
    network.register(mcp)
    incidents.register(mcp)
    return mcp


async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def build_app() -> Starlette:
    mcp = build_mcp()
    mcp_app = mcp.streamable_http_app()

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    # mcp_app already serves its own `/mcp` route internally (FastMCP's
    # default `streamable_http_path`); mount it at "/" rather than "/mcp"
    # again, or requests would need to hit "/mcp/mcp".
    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/", app=mcp_app),
        ],
        lifespan=lifespan,
    )
    app.add_middleware(CredentialMiddleware, mcp_path="/mcp")
    return app

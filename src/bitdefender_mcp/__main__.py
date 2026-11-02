"""Entry point: run the Bitdefender GravityZone MCP server over HTTP."""

from __future__ import annotations

import uvicorn

from .config import settings
from .server import build_app


def main() -> None:
    uvicorn.run(build_app(), host=settings.mcp_http_host, port=settings.mcp_http_port)


if __name__ == "__main__":
    main()

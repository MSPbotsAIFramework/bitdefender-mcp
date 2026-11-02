"""Entry point: run the Bitdefender GravityZone MCP server over HTTP."""

from __future__ import annotations

import logging

import uvicorn

from .config import settings
from .server import build_app


def main() -> None:
    # INFO so the structured per-tool-call log line from client.py reaches
    # stdout; format is just the message since that line is already a JSON
    # object (see client.py's `_logger.info(json.dumps(...))`).
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(build_app(), host=settings.mcp_http_host, port=settings.mcp_http_port)


if __name__ == "__main__":
    main()

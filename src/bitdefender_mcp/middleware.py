"""Per-request credential extraction.

Reads `X-Bitdefender-Api-Key` (required) and `X-Bitdefender-Base-Url`
(optional) from every `/mcp` request, sets them into the request-scoped
ContextVar for the duration of the request, and resets it in `finally`.
Missing the required header short-circuits with HTTP 401 before the request
reaches the MCP app -- GravityZone itself is never called with an empty
credential.

Also mints a per-request id (also request-scoped, also reset in `finally`)
so the structured log line `client.py` emits for each GravityZone call can
be correlated back to the inbound MCP request (SOP Checklist §14:
structured logs must carry a request id).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .credentials import API_KEY_HEADER, BASE_URL_HEADER, reset_credentials, set_credentials
from .logging_context import new_request_id, reset_request_id, set_request_id


class CredentialMiddleware(BaseHTTPMiddleware):
    """Extracts GravityZone credentials from headers for `/mcp` requests only."""

    def __init__(self, app: object, mcp_path: str = "/mcp") -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._mcp_path = mcp_path

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not request.url.path.startswith(self._mcp_path):
            return await call_next(request)

        api_key = request.headers.get(API_KEY_HEADER)
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "not_configured",
                        "message": f"Missing required header: {API_KEY_HEADER}",
                        "retryable": False,
                    },
                    "required_headers": [API_KEY_HEADER],
                },
            )

        base_url = request.headers.get(BASE_URL_HEADER)
        cred_token = set_credentials(api_key, base_url)
        request_id_token = set_request_id(new_request_id())
        try:
            return await call_next(request)
        finally:
            reset_request_id(request_id_token)
            reset_credentials(cred_token)

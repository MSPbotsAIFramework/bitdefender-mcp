"""CredentialMiddleware: missing header -> 401, present header -> request context.

Maps to TC13 / AC11 (missing header never reaches GravityZone, never 500).
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from bitdefender_mcp.config import DEFAULT_GRAVITYZONE_BASE_URL
from bitdefender_mcp.credentials import get_credentials
from bitdefender_mcp.middleware import API_KEY_HEADER, BASE_URL_HEADER, CredentialMiddleware


async def _echo_credentials(_request: Request) -> JSONResponse:
    creds = get_credentials()
    if creds is None:
        return JSONResponse({"credentials": None})
    return JSONResponse({"api_key": creds.api_key, "base_url": creds.base_url})


def _build_app() -> Starlette:
    app = Starlette(routes=[Route("/mcp", _echo_credentials, methods=["POST"]), Route("/health", _echo_credentials)])
    app.add_middleware(CredentialMiddleware, mcp_path="/mcp")
    return app


def test_missing_api_key_header_returns_401_not_500():
    client = TestClient(_build_app())
    response = client.post("/mcp", json={})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "not_configured"
    assert API_KEY_HEADER in body["required_headers"]


def test_present_header_populates_request_context():
    client = TestClient(_build_app())
    response = client.post(
        "/mcp",
        json={},
        headers={API_KEY_HEADER: "a-real-key", BASE_URL_HEADER: "https://onprem.example.test/api"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["api_key"] == "a-real-key"
    assert body["base_url"] == "https://onprem.example.test/api"


def test_default_base_url_used_when_header_absent():
    client = TestClient(_build_app())
    response = client.post("/mcp", json={}, headers={API_KEY_HEADER: "a-real-key"})
    assert response.status_code == 200
    body = response.json()
    assert body["base_url"] == DEFAULT_GRAVITYZONE_BASE_URL


def test_health_endpoint_does_not_require_credential_header():
    client = TestClient(_build_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"credentials": None}


def test_context_reset_after_request_completes():
    client = TestClient(_build_app())
    client.post("/mcp", json={}, headers={API_KEY_HEADER: "a-real-key"})
    # Outside any request, the contextvar must be back to unset.
    assert get_credentials() is None

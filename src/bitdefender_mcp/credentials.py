"""Per-request GravityZone credentials, isolated with contextvars.

Each MCP request carries its own tenant's API key (and optionally a custom
Control Center base URL) in HTTP headers. The middleware sets these into a
ContextVar at the start of the request and resets them in a `finally` block,
so concurrent requests from different tenants never see each other's values.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from .config import DEFAULT_GRAVITYZONE_BASE_URL

API_KEY_HEADER = "X-Bitdefender-Api-Key"
BASE_URL_HEADER = "X-Bitdefender-Base-Url"


@dataclass(frozen=True)
class GravityZoneCredentials:
    api_key: str
    base_url: str


_credentials_var: ContextVar[GravityZoneCredentials | None] = ContextVar(
    "bitdefender_credentials", default=None
)


def set_credentials(api_key: str, base_url: str | None) -> object:
    """Set this request's credentials; returns the token for `reset_credentials`."""
    creds = GravityZoneCredentials(
        api_key=api_key,
        base_url=(base_url or DEFAULT_GRAVITYZONE_BASE_URL).rstrip("/"),
    )
    return _credentials_var.set(creds)


def reset_credentials(token: object) -> None:
    _credentials_var.reset(token)  # type: ignore[arg-type]


def get_credentials() -> GravityZoneCredentials | None:
    """Return the current request's credentials, or None if not set.

    None only happens if a tool is somehow invoked outside the middleware's
    scope -- tools must treat this the same as a missing header.
    """
    return _credentials_var.get()

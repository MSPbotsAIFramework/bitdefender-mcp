"""Non-credential service configuration.

Credentials (the GravityZone API key and the optional per-tenant base URL)
are never read here -- they come from request headers on every call, see
`middleware.py`. This module only holds process-level settings that are the
same for every tenant.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_GRAVITYZONE_BASE_URL = "https://cloud.gravityzone.bitdefender.com/api"


class Settings(BaseSettings):
    """Process-level configuration, tolerant of unknown environment variables."""

    model_config = SettingsConfigDict(extra="ignore")

    mcp_http_host: str = "0.0.0.0"
    mcp_http_port: int = 8080


settings = Settings()

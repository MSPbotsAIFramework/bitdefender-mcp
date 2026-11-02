"""Shared test fixtures."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pytest

from bitdefender_mcp.credentials import reset_credentials, set_credentials
from bitdefender_mcp.server import build_mcp

BASE_URL = "https://cloud.gravityzone.bitdefender.com/api"


@contextmanager
def credentials(api_key: str = "test-api-key", base_url: str = BASE_URL) -> Iterator[None]:
    token = set_credentials(api_key, base_url)
    try:
        yield
    finally:
        reset_credentials(token)


@pytest.fixture
def mcp():
    return build_mcp()

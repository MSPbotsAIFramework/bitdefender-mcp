"""Thin JSON-RPC 2.0 client for GravityZone's Control Center API.

One POST per call, uniform envelope: `{"jsonrpc": "2.0", "id", "method",
"params"}` against `<base_url>/v1.0/jsonrpc/<service>`, HTTP Basic auth with
the API key as the username and an empty password (API Guide p.5).

Bounded retry with backoff on 429 / 5xx, honoring `Retry-After` when present
(GravityZone hard-enforces 10 req/s per key, API Guide p.2, p.6), but always
clamped to `MAX_BACKOFF_S` -- a vendor-supplied `Retry-After` is untrusted
input and must not be allowed to block a tool call past the 120s-per-call
budget (SOP §5, tech design Non-functional section). Each tool call gets its
own client built from the current request's credentials -- never shared
across requests, never module-level.

Emits one structured log line per `call()` (tool name, service.method,
status code, duration, outcome), tagged with the request id set by
`middleware.py` and the tool name set by `tools/_shared.run_tool` -- see
`logging_context.py`. The credential never appears in a log field.
"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import logging
import time
from typing import Any

import httpx

from .errors import GravityZoneError
from .logging_context import get_request_id, get_tool_name

CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 30.0
MAX_ATTEMPTS = 3
MAX_BACKOFF_S = 20.0
DEFAULT_RETRY_AFTER_S = 2.0

_id_counter = itertools.count(1)
_logger = logging.getLogger(__name__)


class GravityZoneClient:
    """Per-request GravityZone API client. Do not reuse across requests."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{api_key}:".encode()).decode("ascii")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=CONNECT_TIMEOUT_S, read=READ_TIMEOUT_S, write=READ_TIMEOUT_S, pool=READ_TIMEOUT_S),
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GravityZoneClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def call(self, service: str, method: str, params: dict[str, Any] | None = None) -> Any:
        """Invoke one JSON-RPC method and return its `result`.

        Raises GravityZoneError on any HTTP error or JSON-RPC `error` object,
        with enough detail (`http_status` / `jsonrpc_code`) for errors.py to
        map onto the fixed envelope vocabulary.
        """
        url = f"{self._base_url}/v1.0/jsonrpc/{service}"
        payload = {
            "jsonrpc": "2.0",
            "id": next(_id_counter),
            "method": method,
            "params": params or {},
        }

        start = time.monotonic()
        status_code: int | None = None
        outcome = "error"
        try:
            last_exc: GravityZoneError | None = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    response = await self._client.post(url, json=payload)
                except httpx.TimeoutException as exc:
                    last_exc = GravityZoneError(f"Timed out calling GravityZone {service}.{method}: {exc}")
                    await self._sleep_before_retry(attempt, None)
                    continue
                except httpx.HTTPError as exc:
                    last_exc = GravityZoneError(f"Network error calling GravityZone {service}.{method}: {exc}")
                    await self._sleep_before_retry(attempt, None)
                    continue

                status_code = response.status_code
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                    last_exc = GravityZoneError(
                        f"GravityZone {service}.{method} returned HTTP {response.status_code}",
                        http_status=response.status_code,
                    )
                    if attempt < MAX_ATTEMPTS:
                        await self._sleep_before_retry(attempt, retry_after)
                        continue
                    raise last_exc

                if response.status_code >= 400:
                    raise GravityZoneError(
                        f"GravityZone {service}.{method} returned HTTP {response.status_code}",
                        http_status=response.status_code,
                    )

                body = response.json()
                error = body.get("error")
                if error is not None:
                    raise GravityZoneError(
                        error.get("message", "GravityZone returned a JSON-RPC error"),
                        jsonrpc_code=error.get("code"),
                    )
                outcome = "ok"
                return body.get("result")

            assert last_exc is not None
            raise last_exc
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            _logger.info(
                json.dumps(
                    {
                        "event": "gravityzone_tool_call",
                        "request_id": get_request_id(),
                        "tool": get_tool_name(),
                        "service": service,
                        "method": method,
                        "status_code": status_code,
                        "outcome": outcome,
                        "duration_ms": duration_ms,
                    },
                    ensure_ascii=False,
                )
            )

    @staticmethod
    async def _sleep_before_retry(attempt: int, retry_after_s: float | None) -> None:
        # retry_after_s comes from the vendor's `Retry-After` header -- untrusted
        # input. Clamp it the same as the exponential-backoff fallback so a large
        # or misconfigured value (e.g. "Retry-After: 100000") can't make a tool
        # call hang past the 120s-per-call budget (PRD-21222 review round 1,
        # finding 1).
        delay = retry_after_s if retry_after_s is not None else 2 ** (attempt - 1)
        await asyncio.sleep(min(delay, MAX_BACKOFF_S))


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return DEFAULT_RETRY_AFTER_S

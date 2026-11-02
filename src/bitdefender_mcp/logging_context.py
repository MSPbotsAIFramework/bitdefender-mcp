"""Request/tool-scoped context for structured logging.

Kept as its own module -- not folded into `credentials.py` or `client.py` --
so neither of those has to import the other: `middleware.py` sets the
request id, `tools/_shared.py` sets the tool name, and `client.py` reads
both when it emits its one structured log line per tool call (PRD-21222
review round 1, finding 2). Same contextvar pattern as
`credentials.py` -- request-scoped, reset in a `finally` block, never a
module-level variable, so concurrent requests never see each other's ids.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_request_id_var: ContextVar[str | None] = ContextVar("bitdefender_request_id", default=None)
_tool_name_var: ContextVar[str | None] = ContextVar("bitdefender_tool_name", default=None)


def new_request_id() -> str:
    """A short, unique-enough id to correlate one inbound request's log lines."""
    return uuid.uuid4().hex[:16]


def set_request_id(value: str) -> object:
    return _request_id_var.set(value)


def reset_request_id(token: object) -> None:
    _request_id_var.reset(token)  # type: ignore[arg-type]


def get_request_id() -> str | None:
    return _request_id_var.get()


def set_tool_name(value: str) -> object:
    return _tool_name_var.set(value)


def reset_tool_name(token: object) -> None:
    _tool_name_var.reset(token)  # type: ignore[arg-type]


def get_tool_name() -> str | None:
    return _tool_name_var.get()

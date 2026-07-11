"""Process-wide HTTP client pool shared by Basic Auth ServiceNow requests."""
from __future__ import annotations

import atexit
import asyncio
from typing import Optional

import httpx


_LIMITS = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=15.0,
)

_pooled_client: Optional[httpx.AsyncClient] = None


def get_pooled_client() -> httpx.AsyncClient:
    """Return a reusable verified HTTP client for ServiceNow API traffic."""
    global _pooled_client
    if _pooled_client is None or getattr(_pooled_client, "is_closed", False):
        _pooled_client = httpx.AsyncClient(
            verify=True,
            limits=_LIMITS,
            timeout=httpx.Timeout(None),
        )
    return _pooled_client


async def shutdown_http_client() -> None:
    """Close the shared client and reset the singleton reference."""
    global _pooled_client
    client = _pooled_client
    _pooled_client = None
    if client is not None and not getattr(client, "is_closed", True):
        await client.aclose()


def _close_pool_at_exit() -> None:
    client = _pooled_client
    if client is None or getattr(client, "is_closed", True):
        return
    try:
        asyncio.run(client.aclose())
    except RuntimeError:
        # The interpreter owns final socket cleanup if its event loop is gone.
        pass


atexit.register(_close_pool_at_exit)

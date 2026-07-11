"""Read/write request dispatcher for the ServiceNow REST API.

Reads and writes share an entry point but their pipelines diverge:

    GET:
        url_builder.ensure_query_encoded
     -> url_builder.add_default_params       (read-only perf params)
     -> Basic Auth client GET request
     -> response_parser.extract_display_values

    POST / PATCH / DELETE:
        Basic Auth client.make_authenticated_request(
            method, url, raise_for_status=True, json=json_data
        )

The write path explicitly skips the read-only param injection and the
display-value flattening — applying either to a write payload would
break the request shape or the response shape (per the token-optimization
invariant memory).
"""
from __future__ import annotations

import os
import sys
from typing import Any, Optional

import anyio

from http_layer.response_parser import extract_display_values
from http_layer.url_builder import add_default_params, ensure_query_encoded
from auth.environment import load_servicenow_environment
from auth.singleton import get_servicenow_client, make_authenticated_get

load_servicenow_environment()
SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE") or os.getenv("SERVICE_NOW_HOST")
NWS_API_BASE = SERVICENOW_INSTANCE


async def make_nws_request(
    url: str,
    display_value: bool = True,
    method: str = "GET",
    json_data: Optional[dict[str, Any]] = None,
) -> dict[str, Any] | None:
    """Make a request to the ServiceNow API using Basic authentication.

    For GET requests, applies query encoding, default performance params
    (sysparm_no_count, sysparm_exclude_reference_link, sysparm_display_value),
    and display-value extraction.

    For non-GET requests (POST, PATCH, DELETE), bypasses read-only param
    injection and propagates ``httpx.HTTPStatusError`` +
    ``httpx.TimeoutException`` so callers can map them to domain-specific
    error messages.

    Wrap calls in ``anyio.fail_after()`` at the call site to enforce
    per-operation deadlines (e.g. ``anyio.fail_after(180.0)`` for KB publish).
    """
    if method == "GET":
        url = ensure_query_encoded(url)
        url = add_default_params(url, display_value)
        try:
            with anyio.fail_after(30.0):  # anyio cancel scope: sync ctx, async-compatible
                result = await make_authenticated_get(url)
            return extract_display_values(result) if result and display_value else result
        except TimeoutError:
            print("[http_layer] GET request timed out", file=sys.stderr)
            return None
        except Exception as e:  # noqa: BLE001
            # stderr only — stdout is reserved for the MCP JSON-RPC frame stream.
            print(f"[http_layer] GET request failed ({type(e).__name__})", file=sys.stderr)
            return None

    # Write path: bypass read-only params + display flattening, raise
    # for status so callers can map HTTP errors to domain errors.
    # Callers wrap in anyio.fail_after() to enforce custom deadlines.
    client = get_servicenow_client()
    return await client.make_authenticated_request(
        method, url, raise_for_status=True, json=json_data
    )


async def test_servicenow_connection() -> dict[str, Any]:
    """Test the configured Basic Auth connection and return a safe status."""
    try:
        client = get_servicenow_client()
        return await client.test_connection()
    except Exception:  # noqa: BLE001
        return {
            "status": "error",
            "message": "Basic Auth configuration is unavailable",
            "basic_auth_available": False,
            "auth_method": "basic",
        }


def get_auth_info() -> dict[str, Any]:
    """Get information about current authentication method."""
    return {
        "basic_auth_enabled": True,
        "instance_url": SERVICENOW_INSTANCE,
        "auth_method": "basic",
    }

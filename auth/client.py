"""ServiceNow REST client authenticated with HTTP Basic Auth.

The client deliberately has no OAuth token endpoint, cache, refresh logic, or
Bearer-header path. Each API request carries the Basic credential header
directly, while the ServiceNow account's roles remain the authorization
boundary for tables and write operations.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from auth.environment import load_servicenow_environment
from auth.http_pool import get_pooled_client
from constants import JSON_HEADERS


def _environment_value(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _validate_instance_url(raw_instance: str) -> str:
    """Allow Basic credentials only on a clean HTTPS ServiceNow origin."""
    parsed = urlparse(raw_instance)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError(
            "ServiceNow Basic Auth requires an HTTPS instance URL without "
            "embedded credentials, paths, queries, or fragments."
        )
    return raw_instance.rstrip("/")


class ServiceNowBasicAuthClient:
    """Make authenticated ServiceNow REST calls with a user/password account."""

    def __init__(
        self,
        instance_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        load_servicenow_environment()

        raw_instance = instance_url or _environment_value(
            "SERVICENOW_INSTANCE", "SERVICE_NOW_HOST"
        )
        self.instance_url = _validate_instance_url(raw_instance) if raw_instance else None
        self._username = username or _environment_value(
            "SERVICENOW_USERNAME", "SERVICE_NOW_USERNAME"
        )
        self._password = password or _environment_value(
            "SERVICENOW_PASSWORD", "SERVICE_NOW_PASSWORD"
        )

        if not all([self.instance_url, self._username, self._password]):
            raise ValueError(
                "Missing Basic Auth configuration. Ensure the ServiceNow instance, "
                "username, and password are set."
            )

    async def get_auth_headers(self) -> dict[str, str]:
        """Return a Basic Authorization header plus the standard JSON headers."""
        credentials = f"{self._username}:{self._password}".encode("utf-8")
        encoded = base64.b64encode(credentials).decode("ascii")
        return {
            "Authorization": f"Basic {encoded}",
            **JSON_HEADERS,
        }

    async def make_authenticated_request(
        self,
        method: str,
        url: str,
        raise_for_status: bool = False,
        **kwargs: Any,
    ) -> Optional[dict[str, Any]]:
        """Make one authenticated ServiceNow REST request.

        Read callers receive ``None`` for connection, parse, and HTTP-status
        failures, preserving the upstream dispatcher contract. Write callers
        request ``raise_for_status=True`` so their tool wrappers can map 401,
        403, and other ServiceNow status errors to useful domain responses.
        """
        headers = await self.get_auth_headers()
        basic_authorization = headers["Authorization"]
        supplied_headers = kwargs.pop("headers", None)
        if supplied_headers:
            headers.update(dict(supplied_headers))
        # Authentication is not caller-overridable: every request from this
        # client must use the configured Basic credentials.
        headers["Authorization"] = basic_authorization

        client = get_pooled_client()
        try:
            response = await client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError:
            if raise_for_status:
                raise
            return None
        except httpx.TimeoutException:
            if raise_for_status:
                raise
            return None
        except (httpx.RequestError, json.JSONDecodeError):
            return None

    async def test_connection(self) -> dict[str, Any]:
        """Perform a read-only CMDB request to verify credentials and access."""
        test_url = f"{self.instance_url}/api/now/table/cmdb_ci?sysparm_limit=1"
        result = await self.make_authenticated_request("GET", test_url)
        if result is not None:
            return {
                "status": "success",
                "message": "Basic authentication successful",
                "auth_method": "basic",
            }
        return {
            "status": "error",
            "message": "Basic authentication failed or CMDB access was denied",
            "auth_method": "basic",
        }

"""Basic-authentication boundary for the ServiceNow MCP server."""

from auth.client import ServiceNowBasicAuthClient
from auth.singleton import get_servicenow_client, make_authenticated_get

__all__ = [
    "ServiceNowBasicAuthClient",
    "get_servicenow_client",
    "make_authenticated_get",
]

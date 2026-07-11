"""Process-wide Basic Auth client singleton and GET convenience helper."""
from __future__ import annotations

from typing import Any, Optional

from auth.client import ServiceNowBasicAuthClient


_servicenow_client: Optional[ServiceNowBasicAuthClient] = None


def get_servicenow_client() -> ServiceNowBasicAuthClient:
    """Get or create the process-wide Basic Auth client."""
    global _servicenow_client
    if _servicenow_client is None:
        _servicenow_client = ServiceNowBasicAuthClient()
    return _servicenow_client


async def make_authenticated_get(url: str) -> Optional[dict[str, Any]]:
    """Make a Basic-authenticated GET request through the global client."""
    return await get_servicenow_client().make_authenticated_request("GET", url)

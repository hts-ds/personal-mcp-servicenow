"""Contract tests for the ServiceNow Basic Auth boundary.

These tests deliberately use ``httpx.MockTransport`` instead of a live
ServiceNow instance.  They validate the request that the real client builds
while keeping credentials and CI data out of the test suite.
"""
from __future__ import annotations

import base64

import httpx
import pytest


@pytest.fixture
def basic_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICENOW_INSTANCE", "https://test.service-now.com/")
    monkeypatch.setenv("SERVICENOW_USERNAME", "h104-test-user")
    monkeypatch.setenv("SERVICENOW_PASSWORD", "not-a-real-password")


def test_client_requires_instance_username_and_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """Basic Auth must fail fast without every required credential field."""
    for variable in (
        "SERVICENOW_INSTANCE",
        "SERVICENOW_USERNAME",
        "SERVICENOW_PASSWORD",
        "SERVICE_NOW_HOST",
        "SERVICE_NOW_USERNAME",
        "SERVICE_NOW_PASSWORD",
    ):
        monkeypatch.delenv(variable, raising=False)

    from auth.client import ServiceNowBasicAuthClient

    with pytest.raises(ValueError, match="Basic Auth configuration"):
        ServiceNowBasicAuthClient()


@pytest.mark.parametrize(
    "instance_url",
    [
        "http://test.service-now.com",
        "https://user:password@test.service-now.com",
        "test.service-now.com",
    ],
)
def test_client_rejects_insecure_or_ambiguous_instance_urls(instance_url: str) -> None:
    """Basic credentials may only be sent to a clean HTTPS instance origin."""
    from auth.client import ServiceNowBasicAuthClient

    with pytest.raises(ValueError, match="HTTPS"):
        ServiceNowBasicAuthClient(instance_url, "test-user", "test-password")


@pytest.mark.asyncio
async def test_get_auth_headers_uses_basic_credentials_and_json_headers(basic_env: None) -> None:
    """The public API request header is Basic, never Bearer."""
    from auth.client import ServiceNowBasicAuthClient

    headers = await ServiceNowBasicAuthClient().get_auth_headers()

    assert headers["Authorization"].startswith("Basic ")
    decoded = base64.b64decode(headers["Authorization"].split(" ", 1)[1]).decode()
    assert decoded == "h104-test-user:not-a-real-password"
    assert headers["Accept"] == "application/json"
    assert headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_authenticated_request_sends_basic_header_without_token_exchange(
    basic_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read request carries the Basic header directly and never calls OAuth."""
    observed: dict[str, object] = {"calls": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        observed["calls"] = int(observed["calls"]) + 1
        observed["path"] = request.url.path
        observed["authorization"] = request.headers["Authorization"]
        observed["request_id"] = request.headers["X-Request-ID"]
        return httpx.Response(200, json={"result": [{"sys_id": "ci-1"}]})

    pooled_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        import auth.client as client_module
        from auth.client import ServiceNowBasicAuthClient

        monkeypatch.setattr(client_module, "get_pooled_client", lambda: pooled_client)

        result = await ServiceNowBasicAuthClient().make_authenticated_request(
            "GET",
            "https://test.service-now.com/api/now/table/cmdb_ci",
            headers={"X-Request-ID": "test-request"},
        )
    finally:
        await pooled_client.aclose()

    assert result == {"result": [{"sys_id": "ci-1"}]}
    assert observed["calls"] == 1
    assert observed["path"] == "/api/now/table/cmdb_ci"
    assert observed["authorization"].startswith("Basic ")
    assert "Bearer" not in observed["authorization"]
    assert observed["request_id"] == "test-request"


@pytest.mark.asyncio
async def test_read_401_returns_none_without_retrying_or_refreshing_token(
    basic_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Basic credentials cannot be refreshed, so an unauthorised read is not retried."""
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"error": {"message": "unauthorised"}})

    pooled_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        import auth.client as client_module
        from auth.client import ServiceNowBasicAuthClient

        monkeypatch.setattr(client_module, "get_pooled_client", lambda: pooled_client)
        result = await ServiceNowBasicAuthClient().make_authenticated_request(
            "GET", "https://test.service-now.com/api/now/table/cmdb_ci"
        )
    finally:
        await pooled_client.aclose()

    assert result is None
    assert calls == 1


@pytest.mark.asyncio
async def test_write_403_propagates_http_status_error(
    basic_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write callers retain the existing ability to map ServiceNow 403 errors."""
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "forbidden"}})

    pooled_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        import auth.client as client_module
        from auth.client import ServiceNowBasicAuthClient

        monkeypatch.setattr(client_module, "get_pooled_client", lambda: pooled_client)
        with pytest.raises(httpx.HTTPStatusError) as error:
            await ServiceNowBasicAuthClient().make_authenticated_request(
                "POST",
                "https://test.service-now.com/api/now/table/vtb_task",
                raise_for_status=True,
                json={"short_description": "test"},
            )
    finally:
        await pooled_client.aclose()

    assert error.value.response.status_code == 403


def test_basic_client_has_no_oauth_token_cache(basic_env: None) -> None:
    """No access token, expiry, or refresh state survives the migration."""
    from auth.client import ServiceNowBasicAuthClient

    client = ServiceNowBasicAuthClient()

    assert not hasattr(client, "_access_token")
    assert not hasattr(client, "_token_expires_at")
    assert not hasattr(client, "token_endpoint")


@pytest.mark.asyncio
async def test_connection_status_never_exposes_password(basic_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Diagnostic output must be safe to return through MCP tools."""
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"result": []})

    pooled_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        import auth.client as client_module
        from auth.client import ServiceNowBasicAuthClient

        monkeypatch.setattr(client_module, "get_pooled_client", lambda: pooled_client)
        status = await ServiceNowBasicAuthClient().test_connection()
    finally:
        await pooled_client.aclose()

    assert status["status"] == "success"
    assert status["auth_method"] == "basic"
    assert "not-a-real-password" not in str(status)

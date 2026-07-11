"""Regression tests for custom ServiceNow CMDB classes without CI numbers."""
from __future__ import annotations

import pytest


CUSTOM_SYS_ID = "0123456789abcdef0123456789abcdef"


@pytest.mark.asyncio
async def test_quick_ci_search_returns_sys_id_for_follow_up_detail_lookup(monkeypatch):
    """Search results must contain a stable identifier even when `number` is absent."""
    import Table_Tools.cmdb_tools as cmdb_tools

    captured_urls: list[str] = []

    async def fake_request(url: str, **_: object):
        captured_urls.append(url)
        return {"result": []}

    monkeypatch.setattr(cmdb_tools, "make_nws_request", fake_request)

    await cmdb_tools.quick_ci_search("H104")

    assert "sysparm_fields=number,sys_id,name" in captured_urls[0]


@pytest.mark.asyncio
async def test_get_ci_details_resolves_custom_class_from_sys_id(monkeypatch):
    """A custom CI class is discovered from the base CMDB row before detail fetch."""
    import Table_Tools.cmdb_tools as cmdb_tools

    calls: list[tuple[str, bool]] = []

    async def fake_request(url: str, display_value: bool = True, **_: object):
        calls.append((url, display_value))
        if "/api/now/table/cmdb_ci?" in url:
            assert f"sysparm_query=sys_id={CUSTOM_SYS_ID}" in url
            assert display_value is False
            return {
                "result": [{
                    "sys_id": CUSTOM_SYS_ID,
                    "sys_class_name": "u_h104_custom_ci",
                }]
            }
        if "/api/now/table/u_h104_custom_ci?" in url:
            assert f"sysparm_query=sys_id={CUSTOM_SYS_ID}" in url
            assert display_value is True
            return {"result": [{"sys_id": CUSTOM_SYS_ID, "name": "H104 CI"}]}
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(cmdb_tools, "make_nws_request", fake_request)

    result = await cmdb_tools.get_ci_details(CUSTOM_SYS_ID)

    assert result == {
        "ci_table": "u_h104_custom_ci",
        "ci_identifier": CUSTOM_SYS_ID,
        "result": {"sys_id": CUSTOM_SYS_ID, "name": "H104 CI"},
    }
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_get_ci_details_rejects_unsafe_custom_table_name(monkeypatch):
    """Table identifiers must not be able to alter the ServiceNow query URL."""
    import Table_Tools.cmdb_tools as cmdb_tools

    called = False

    async def fake_request(*_: object, **__: object):
        nonlocal called
        called = True
        return {"result": []}

    monkeypatch.setattr(cmdb_tools, "make_nws_request", fake_request)

    result = await cmdb_tools.get_ci_details(CUSTOM_SYS_ID, "cmdb_ci^ORsys_idISNOTEMPTY")

    assert result == "Invalid CI table name"
    assert called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ci_identifier",
    [
        "CI001%5EORsys_idISNOTEMPTY",
        "CI001%26sysparm_limit%3D10000",
        "CI001^ORsys_idISNOTEMPTY",
        "CI001&sysparm_limit=10000",
    ],
)
async def test_get_ci_details_rejects_query_shaping_identifier(monkeypatch, ci_identifier):
    """An identifier is data, never an encoded-query fragment or URL parameter."""
    import Table_Tools.cmdb_tools as cmdb_tools

    called = False

    async def fake_request(*_: object, **__: object):
        nonlocal called
        called = True
        return {"result": []}

    monkeypatch.setattr(cmdb_tools, "make_nws_request", fake_request)

    result = await cmdb_tools.get_ci_details(ci_identifier)

    assert result == "Invalid CI identifier"
    assert called is False


@pytest.mark.asyncio
async def test_attribute_search_targets_a_valid_custom_ci_table(monkeypatch):
    """Custom class names must not be discarded merely because they are not upstream defaults."""
    import Table_Tools.cmdb_tools as cmdb_tools

    captured_urls: list[str] = []

    async def fake_request(url: str, **_: object):
        captured_urls.append(url)
        return {"result": []}

    monkeypatch.setattr(cmdb_tools, "make_nws_request", fake_request)

    await cmdb_tools.search_cis_by_attributes(name="H104", ci_type="u_h104_custom_ci")

    assert "/api/now/table/u_h104_custom_ci?" in captured_urls[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "search_value",
    [
        "H104^ORsys_idISNOTEMPTY",
        "H104&sysparm_limit=10000",
        "H104%26sysparm_limit%3D10000",
    ],
)
async def test_public_cmdb_searches_reject_query_shaping_values(monkeypatch, search_value):
    """User-provided search text cannot become a ServiceNow query clause or URL parameter."""
    import Table_Tools.cmdb_tools as cmdb_tools

    called = False

    async def fake_request(*_: object, **__: object):
        nonlocal called
        called = True
        return {"result": []}

    monkeypatch.setattr(cmdb_tools, "make_nws_request", fake_request)

    attribute_result = await cmdb_tools.search_cis_by_attributes(name=search_value)
    quick_result = await cmdb_tools.quick_ci_search(search_value)

    assert attribute_result == "Invalid CI search value"
    assert quick_result == "Invalid CI search value"
    assert called is False

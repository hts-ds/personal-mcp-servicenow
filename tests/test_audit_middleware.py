"""Audit-log redaction contract for MCP tool arguments."""

from audit_middleware import _sanitize


def test_sanitize_redacts_credentials_and_ci_identifiers():
    """Logs must not retain a ServiceNow password or a raw CI sys_id."""
    sanitized = _sanitize({
        "password": "not-a-real-password",
        "ci_identifier": "0123456789abcdef0123456789abcdef",
        "sys_id": "0123456789abcdef0123456789abcdef",
        "search_term": "H104",
    })

    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["ci_identifier"] == "[REDACTED]"
    assert sanitized["sys_id"] == "[REDACTED]"
    assert sanitized["search_term"] == "H104"

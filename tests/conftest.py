"""Shared pytest fixtures.

The Basic Auth client uses a process-wide pooled ``httpx.AsyncClient``. This
fixture drops the pool before and after each test so a mock or a real client
cannot leak into another test.
"""
from __future__ import annotations

import os

import pytest


# Never allow an ignored developer-local .env pointer to inject real ServiceNow
# credentials into a unit-test process during module collection. Individual
# tests explicitly set a temporary SERVICENOW_ENV_FILE when that behaviour is
# under test.
os.environ["SERVICENOW_ENV_FILE"] = ""


@pytest.fixture(autouse=True)
def _reset_http_pool():
    """Drop the cached pooled client before and after each test."""
    import auth.http_pool as http_pool

    http_pool._pooled_client = None
    yield
    http_pool._pooled_client = None

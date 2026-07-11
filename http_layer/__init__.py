"""HTTP layer for the ServiceNow REST API.

The dispatcher keeps URL construction, response transformation, and
Basic-authenticated request dispatch separate:

    url_builder.py        URL encoding + read-only performance params
    response_parser.py    display-value flattening
    request_dispatcher.py make_nws_request (orchestrator)

Public API:
    make_nws_request, NWS_API_BASE     re-exported from request_dispatcher
    test_servicenow_connection, get_auth_info re-exported from request_dispatcher
"""
from http_layer.request_dispatcher import (
    NWS_API_BASE,
    get_auth_info,
    make_nws_request,
    test_servicenow_connection,
)

__all__ = [
    "make_nws_request",
    "test_servicenow_connection",
    "get_auth_info",
    "NWS_API_BASE",
]

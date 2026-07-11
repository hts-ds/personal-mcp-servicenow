#!/usr/bin/env python3

"""
ServiceNow CMDB (Configuration Management Database) Tools
Provides CI discovery, search, and analysis functionality.
"""

import asyncio
import re
from urllib.parse import quote
from http_layer import make_nws_request, NWS_API_BASE
from http_layer.url_builder import encode_query_value
from utils import extract_keywords
from typing import Any, Dict, Optional, List
from constants import (
    NO_CIS_FOUND_FOR_TYPE,
    NO_CIS_FOUND_MATCHING_CRITERIA,
    CI_NOT_FOUND,
    NO_SIMILAR_CIS_FOUND,
    NO_CI_TYPES_FOUND,
    NO_CIS_FOUND_FOR_SEARCH,
    ERROR_SEARCHING_CIS,
    ERROR_SEARCHING_CIS_BY_TYPE,
    ERROR_FINDING_SIMILAR_CIS,
    ERROR_GETTING_CI_TYPES,
    ERROR_QUICK_CI_SEARCH
)

# Common CMDB CI Tables
CI_TABLES = [
    "cmdb_ci",
    "cmdb_ci_acc",
    "cmdb_ci_alias",
    "cmdb_ci_appl",
    "cmdb_ci_application_cluster",
    "cmdb_ci_batch_job",
    "cmdb_ci_business_app",
    "cmdb_ci_business_capability",
    "cmdb_ci_business_process",
    "cmdb_ci_cim_profile",
    "cmdb_ci_circuit",
    "cmdb_ci_cloud_key_pair",
    "cmdb_ci_cloud_resource_base",
    "cmdb_ci_cluster",
    "cmdb_ci_cluster_node",
    "cmdb_ci_cluster_resource",
    "cmdb_ci_cluster_vip",
    "cmdb_ci_comm",
    "cmdb_ci_computer_room",
    "cmdb_ci_config_file",
    "cmdb_ci_crac",
    "cmdb_ci_database",
    "cmdb_ci_datacenter",
    "cmdb_ci_db_catalog",
    "cmdb_ci_disk_partition",
    "cmdb_ci_display_hardware",
    "cmdb_ci_dns_name",
    "cmdb_ci_drs_vm_config",
    "cmdb_ci_endpoint",
    "cmdb_ci_environment",
    "cmdb_ci_facility_hardware",
    "cmdb_ci_fc_port",
    "cmdb_ci_group",
    "cmdb_ci_hardware",
    "cmdb_ci_imaging_hardware",
    "cmdb_ci_information_object",
    "cmdb_ci_ip_address",
    "cmdb_ci_ip_device",
    "cmdb_ci_ip_network",
    "cmdb_ci_ip_phone",
    "cmdb_ci_ip_service",
    "cmdb_ci_lb_interface",
    "cmdb_ci_lb_pool",
    "cmdb_ci_lb_pool_member",
    "cmdb_ci_lb_service",
    "cmdb_ci_lb_vlan",
    "cmdb_ci_lpar",
    "cmdb_ci_memory_module",
    "cmdb_ci_monitoring_hardware",
    "cmdb_ci_net_app_host",
    "cmdb_ci_net_traffic",
    "cmdb_ci_network_adapter",
    "cmdb_ci_network_host",
    "cmdb_ci_os_packages",
    "cmdb_ci_oslv_container",
    "cmdb_ci_oslv_image",
    "cmdb_ci_oslv_image_tag",
    "cmdb_ci_oslv_local_image",
    "cmdb_ci_patches",
    "cmdb_ci_pdu_outlet",
    "cmdb_ci_peripheral",
    "cmdb_ci_port",
    "cmdb_ci_print_queue",
    "cmdb_ci_printing_hardware",
    "cmdb_ci_qualifier",
    "cmdb_ci_rack",
    "cmdb_ci_san",
    "cmdb_ci_san_connection",
    "cmdb_ci_san_endpoint",
    "cmdb_ci_san_fabric",
    "cmdb_ci_san_zone",
    "cmdb_ci_san_zone_alias",
    "cmdb_ci_san_zone_alias_member",
    "cmdb_ci_san_zone_member",
    "cmdb_ci_san_zone_set",
    "cmdb_ci_service",
    "cmdb_ci_spkg",
    "cmdb_ci_storage_controller",
    "cmdb_ci_storage_device",
    "cmdb_ci_storage_export",
    "cmdb_ci_storage_fileshare",
    "cmdb_ci_storage_hba",
    "cmdb_ci_storage_pool",
    "cmdb_ci_storage_pool_member",
    "cmdb_ci_storage_volume",
    "cmdb_ci_subnet",
    "cmdb_ci_tomcat_connector",
    "cmdb_ci_translation_rule",
    "cmdb_ci_ups_alarm",
    "cmdb_ci_ups_bypass",
    "cmdb_ci_ups_input",
    "cmdb_ci_ups_output",
    "cmdb_ci_vcenter_cluster_drs_rule",
    "cmdb_ci_vcenter_datastore_disk",
    "cmdb_ci_vcenter_host_group",
    "cmdb_ci_vcenter_vm_group",
    "cmdb_ci_veritas_disk_group",
    "cmdb_ci_vm_object",
    "cmdb_ci_vpc",
    "cmdb_ci_vpn",
    "cmdb_ci_websphere_cell",
    "cmdb_ci_zone",
]

# Essential fields for CI discovery
ESSENTIAL_CI_FIELDS = [
    "number", "sys_id", "name", "sys_class_name", "operational_status",
    "install_status", "sys_created_on", "sys_updated_on"
]

# Detailed fields for comprehensive CI information
DETAILED_CI_FIELDS = [
    "number", "sys_id", "name", "sys_class_name", "operational_status", "install_status",
    "ip_address", "serial_number", "model_category", "location", "assigned_to", 
    "assignment_group", "sys_created_on", "sys_updated_on", "short_description",
    "manufacturer", "model_number", "cost_center", "environment"
]

async def find_cis_by_type(ci_type: str, detailed: bool = False) -> dict[str, Any] | str:
    """
    Find all Configuration Items of a specific type.

    Args:
        ci_type: CI class/table name (e.g., 'cmdb_ci_server', 'cmdb_ci_computer')
        detailed: If True, returns detailed CI information

    Returns:
        Dictionary with CI results or error string

    The ci_type is queried directly instead of being pre-validated against the
    static CI_TABLES list — that list drifts from a given instance's CI classes
    and was rejecting valid, common types (e.g. cmdb_ci_server). An unknown
    table simply yields no results rather than a misleading "invalid type".
    """
    if not ci_type:
        return "CI type is required"
    if not _is_valid_ci_table(ci_type):
        return "Invalid CI table name"

    fields = DETAILED_CI_FIELDS if detailed else ESSENTIAL_CI_FIELDS
    
    try:
        url = f"{NWS_API_BASE}/api/now/table/{ci_type}?sysparm_fields={','.join(fields)}&sysparm_display_value=true&sysparm_limit=100"
        data = await make_nws_request(url)
        
        if data and data.get('result'):
            return {
                "ci_type": ci_type,
                "count": len(data['result']),
                "result": data['result']
            }
        return NO_CIS_FOUND_FOR_TYPE.format(ci_type=ci_type)

    except Exception:
        return ERROR_SEARCHING_CIS_BY_TYPE

async def search_cis_by_attributes(
    name: Optional[str] = None,
    ip_address: Optional[str] = None, 
    location: Optional[str] = None,
    status: Optional[str] = None,
    ci_type: Optional[str] = None,
    detailed: bool = False
) -> dict[str, Any] | str:
    """
    Search Configuration Items by multiple attributes.
    
    Args:
        name: CI name/hostname to search for
        ip_address: IP address to search for
        location: Location to filter by
        status: Operational status to filter by  
        ci_type: Specific CI type to search in (optional)
        detailed: If True, returns detailed CI information
    
    Returns:
        Dictionary with CI results or error string
    """
    if not any([name, ip_address, location, status]):
        return "At least one search attribute must be provided"
    
    if ci_type and not _is_valid_ci_table(ci_type):
        return "Invalid CI table name"
    table = ci_type or "cmdb_ci"
    fields = DETAILED_CI_FIELDS if detailed else ESSENTIAL_CI_FIELDS
    
    # Build query conditions. User values are percent-encoded (safe='') so
    # structural characters (#, +, %, ?, ...) in a name/location don't corrupt
    # the sysparm_query. (Operator chars in the locked encode safe-set —
    # & ^ = etc. — still pass through and remain unsupported inside values.)
    query_parts = []
    try:
        if name:
            query_parts.append(f"nameLIKE{encode_query_value(name)}")
        if ip_address:
            query_parts.append(f"ip_address={encode_query_value(ip_address)}")
        if location:
            query_parts.append(f"locationLIKE{encode_query_value(location)}")
        if status:
            query_parts.append(f"operational_status={encode_query_value(status)}")
    except ValueError:
        return "Invalid CI search value"
    
    query_string = "^".join(query_parts)
    
    try:
        url = f"{NWS_API_BASE}/api/now/table/{table}?sysparm_fields={','.join(fields)}&sysparm_query={query_string}&sysparm_display_value=true&sysparm_limit=100"
        data = await make_nws_request(url)
        
        if data and data.get('result'):
            return {
                "table": table,
                "search_criteria": {
                    "name": name,
                    "ip_address": ip_address,
                    "location": location,
                    "status": status
                },
                "count": len(data['result']),
                "result": data['result']
            }
        return NO_CIS_FOUND_MATCHING_CRITERIA

    except Exception:
        return ERROR_SEARCHING_CIS

_SYS_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
_TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_CI_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _is_valid_ci_table(table: str) -> bool:
    """Accept ordinary and instance-specific ServiceNow table identifiers."""
    return bool(_TABLE_NAME_PATTERN.fullmatch(table))


def _is_sys_id(ci_identifier: str) -> bool:
    return bool(_SYS_ID_PATTERN.fullmatch(ci_identifier))


def _is_valid_ci_identifier(ci_identifier: object) -> bool:
    """Accept a CI number or sys_id, never an encoded-query fragment."""
    return isinstance(ci_identifier, str) and bool(
        _CI_IDENTIFIER_PATTERN.fullmatch(ci_identifier)
    )


async def _probe_ci_table(
    table: str,
    ci_identifier: str,
    lookup_field: str,
    display_value: bool = True,
) -> Optional[Dict[str, Any]]:
    """Fetch one CI row by number or sys_id from a validated table."""
    query_value = quote(ci_identifier, safe="")
    url = (
        f"{NWS_API_BASE}/api/now/table/{table}?"
        f"sysparm_fields={','.join(DETAILED_CI_FIELDS)}&"
        f"sysparm_query={lookup_field}={query_value}&"
        f"sysparm_display_value={'true' if display_value else 'false'}"
    )
    try:
        data = await make_nws_request(url, display_value=display_value)
    except Exception:
        return None
    if data and data.get('result'):
        return data['result'][0]
    return None


def _detail_result(
    ci_table: str,
    ci_identifier: str,
    lookup_field: str,
    row: Dict[str, Any],
) -> dict[str, Any]:
    """Shape detail results while retaining backward-compatible number output."""
    result: dict[str, Any] = {
        "ci_table": ci_table,
        "ci_identifier": ci_identifier,
        "result": row,
    }
    if lookup_field == "number":
        result["ci_number"] = ci_identifier
    return result


async def get_ci_details(ci_identifier: str, ci_type: Optional[str] = None) -> dict[str, Any] | str:
    """
    Get comprehensive details for a specific Configuration Item.

    Args:
        ci_identifier: CI number or ServiceNow sys_id
        ci_type: Specific CI table to search in (optional)

    Returns:
        Dictionary with detailed CI information or error string

    A sys_id is the reliable follow-up identifier for custom CMDB classes that
    have no number field. When no table is supplied, the base ``cmdb_ci`` row
    is read first with raw values so its real ``sys_class_name`` table can be
    resolved dynamically. The upstream common-table probes remain as a fallback
    for instances where the base lookup does not return a row.
    """
    if not ci_identifier:
        return "CI number is required"

    if not _is_valid_ci_identifier(ci_identifier):
        return "Invalid CI identifier"

    if ci_type and not _is_valid_ci_table(ci_type):
        return "Invalid CI table name"

    lookup_field = "sys_id" if _is_sys_id(ci_identifier) else "number"

    if ci_type:
        row = await _probe_ci_table(ci_type, ci_identifier, lookup_field)
        if row:
            return _detail_result(ci_type, ci_identifier, lookup_field, row)
        return CI_NOT_FOUND.format(ci_number=ci_identifier)

    # ServiceNow returns raw ``sys_class_name`` only when display values are
    # disabled. That technical table name lets this fork resolve a customer
    # extension such as ``u_h104_custom_ci`` without a static allowlist.
    base_row = await _probe_ci_table(
        "cmdb_ci", ci_identifier, lookup_field, display_value=False
    )
    if base_row:
        dynamic_table = base_row.get("sys_class_name")
        if isinstance(dynamic_table, str) and _is_valid_ci_table(dynamic_table):
            if dynamic_table != "cmdb_ci":
                detail_row = await _probe_ci_table(
                    dynamic_table, ci_identifier, lookup_field
                )
                if detail_row:
                    return _detail_result(
                        dynamic_table, ci_identifier, lookup_field, detail_row
                    )
            return _detail_result("cmdb_ci", ci_identifier, lookup_field, base_row)

    # Fallback: preserve upstream common-class discovery for unusual instances
    # where the base table does not surface the inherited record.
    tables_to_search = [
        "cmdb_ci_server", "cmdb_ci_computer", "cmdb_ci_database",
        "cmdb_ci_hardware", "cmdb_ci_network_gear", "cmdb_ci_service", "cmdb_ci"
    ]
    semaphore = asyncio.Semaphore(3)

    async def _bounded(table: str) -> Optional[Dict[str, Any]]:
        async with semaphore:
            return await _probe_ci_table(table, ci_identifier, lookup_field)

    rows = await asyncio.gather(*(_bounded(table) for table in tables_to_search))
    for table, row in zip(tables_to_search, rows):
        if row:
            return _detail_result(table, ci_identifier, lookup_field, row)

    return CI_NOT_FOUND.format(ci_number=ci_identifier)

def _extract_ci_search_attributes(ci_data: Dict, ci_table: str) -> Dict[str, str]:
    """Extract search attributes from CI data. Complexity: 4"""
    search_attrs = {}

    if ci_data.get('sys_class_name'):
        search_attrs['ci_type'] = ci_table
    if ci_data.get('location') and ci_data['location'] != '':
        search_attrs['location'] = ci_data['location']
    if ci_data.get('operational_status'):
        search_attrs['status'] = ci_data['operational_status']

    return search_attrs

def _filter_and_limit_ci_results(similar_cis: Dict, ci_number: str, limit: int = 20) -> List[Dict]:
    """Filter out original CI and limit results. Complexity: 3"""
    if not isinstance(similar_cis, dict) or not similar_cis.get('result'):
        return []

    filtered_results = [
        ci for ci in similar_cis['result']
        if ci.get('number') != ci_number
    ]

    return filtered_results[:limit]

def _build_similar_ci_response(ci_number: str, search_attrs: Dict, filtered_results: List[Dict]) -> Dict[str, Any]:
    """Build response for similar CIs. Complexity: 2"""
    return {
        "original_ci": ci_number,
        "similar_criteria": search_attrs,
        "count": len(filtered_results),
        "result": filtered_results
    }

async def similar_cis_for_ci(ci_number: str) -> dict[str, Any] | str:
    """
    Find Configuration Items similar to the specified CI based on attributes.

    Args:
        ci_number: CI number to find similar CIs for

    Returns:
        Dictionary with similar CIs or error string

    Complexity: 8 (reduced from ~15-17)
    """
    # First get the CI details
    ci_details = await get_ci_details(ci_number)

    if isinstance(ci_details, str):
        return ci_details

    ci_data = ci_details['result']
    ci_table = ci_details['ci_table']

    # Extract key attributes for similarity search
    search_attrs = _extract_ci_search_attributes(ci_data, ci_table)

    # Search for similar CIs
    try:
        similar_cis = await search_cis_by_attributes(**search_attrs, detailed=True)

        # Filter and limit results
        filtered_results = _filter_and_limit_ci_results(similar_cis, ci_number, limit=20)

        if filtered_results:
            return _build_similar_ci_response(ci_number, search_attrs, filtered_results)

        return NO_SIMILAR_CIS_FOUND.format(ci_number=ci_number)

    except Exception:
        return ERROR_FINDING_SIMILAR_CIS

async def get_all_ci_types() -> dict[str, Any] | str:
    """
    Get all available CI types/classes in the CMDB.
    
    Returns:
        Dictionary with CI types and their counts
    """
    try:
        # Query sys_db_object to get all tables that extend cmdb_ci
        url = f"{NWS_API_BASE}/api/now/table/sys_db_object?sysparm_query=super_class.name=cmdb_ci^ORname=cmdb_ci&sysparm_fields=name,label,number_ref"
        data = await make_nws_request(url)
        
        if data and data.get('result'):
            ci_types = []
            for table_info in data['result']:
                table_name = table_info.get('name')
                if table_name and table_name.startswith('cmdb_ci'):
                    ci_types.append({
                        "table_name": table_name,
                        "display_name": table_info.get('label', table_name),
                        "record_count": table_info.get('number_ref', 'Unknown')
                    })
            
            return {
                "total_ci_types": len(ci_types),
                "ci_types": sorted(ci_types, key=lambda x: x['table_name'])
            }
        
        return NO_CI_TYPES_FOUND

    except Exception:
        return ERROR_GETTING_CI_TYPES

# Convenience function for quick CI search
async def quick_ci_search(search_term: str) -> dict[str, Any] | str:
    """
    Quick search for CIs by name, IP, or number.
    
    Args:
        search_term: Term to search for in CI name, IP, or number fields
    
    Returns:
        Dictionary with CI results or error string
    """
    try:
        # Try multiple search approaches. Percent-encode the term so special
        # characters in it don't corrupt the sysparm_query structure.
        safe_term = encode_query_value(search_term)
        query_parts = [
            f"nameLIKE{safe_term}",
            f"ip_address={safe_term}",
            f"number={safe_term}"
        ]

        query_string = "^OR".join(query_parts)
        url = f"{NWS_API_BASE}/api/now/table/cmdb_ci?sysparm_fields={','.join(ESSENTIAL_CI_FIELDS)}&sysparm_query={query_string}&sysparm_display_value=true&sysparm_limit=50"
        data = await make_nws_request(url)
        
        if data and data.get('result'):
            return {
                "search_term": search_term,
                "count": len(data['result']),
                "result": data['result']
            }
        
        return NO_CIS_FOUND_FOR_SEARCH.format(search_term=search_term)

    except ValueError:
        return "Invalid CI search value"
    except Exception:
        return ERROR_QUICK_CI_SEARCH

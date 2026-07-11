# H104 Basic Auth migration

## Goal

Provide a separate, forked ServiceNow MCP project that works with the API account already held by H104, without requiring creation of an OAuth connected application. The implementation intentionally reuses the upstream MCP tool, filter, URL-builder, response-parser, and audit layers.

## Runtime change

| Concern | Upstream behavior | H104 fork behavior |
| --- | --- | --- |
| ServiceNow authentication | Client-credentials token request and in-memory token cache | Basic Authorization header on each REST request |
| 401 behavior | Clear cache, acquire a token, retry once | Return `None` on read; propagate the status to write tools when requested |
| Credentials | Instance + client ID + client secret | Instance + service-account username + password |
| Connection test | Token-oriented status | Read-only `cmdb_ci?sysparm_limit=1` status |
| Auth package | `oauth/` token store, executor, singleton | `auth/` Basic client, singleton, and reusable HTTP pool |

## Preserved behavior

- The URL builder still encodes ServiceNow query parameters and adds read-performance parameters.
- Display-value envelopes are still flattened on reads only.
- POST/PATCH/DELETE bypass read-only URL mutations and retain `raise_for_status=True` for tool-level 401/403 mapping.
- The broad upstream tool catalogue and local stdio FastMCP launcher remain available. Remote SSE is deliberately disabled in this Basic Auth fork.
- `quick_ci_search` now returns `sys_id`, and `get_ci_details(sys_id)` resolves
  a dynamic CMDB class from the base CI record before reading its details. This
  covers company-custom CIs that do not use the upstream `number` convention.

## Environment compatibility

`auth.environment.load_servicenow_environment()` loads the fork-local `.env` and optionally an external file named by `SERVICENOW_ENV_FILE`. `config_loader.py` and `ServiceNowBasicAuthClient` support both the canonical `SERVICENOW_*` names and the H104 `SERVICE_NOW_*` aliases.

The external-file option is deliberate: the fork can use `D:\DEV\HTS\ServiceNow\.env` without duplicating a credential into the new project or into an Obsidian configuration note.

## Scope decision

This fork remains a broad, potentially write-capable MCP server because that is the upstream project's tool contract. The H104 CMDB MCP remains the preferred EA server because it has narrower, H104-specific, read-only domain/table/field controls and Scripted REST-to-Table API fallback for company customisation.

## Validation contract

- Unit tests verify Basic header construction, absence of token state, no 401 retry, and error propagation.
- Configuration tests verify H104 aliases, external env-file loading, Basic-only validation, and no OAuth setup instructions.
- HTTP and integration tests verify that all generic query and write routing now resolves through `auth`.
- Launcher tests verify Basic-only setup and clean stdio startup.

# Basic Auth setup

This fork supports ServiceNow REST API authentication with a service-account username and password. It does not initiate an OAuth client-credentials flow.

## Credential configuration

Use either variable set below. Both are accepted so the existing H104 `.env` can be reused.

| Purpose | Preferred name | Existing H104 alias |
| --- | --- | --- |
| Instance URL | `SERVICENOW_INSTANCE` | `SERVICE_NOW_HOST` |
| Username | `SERVICENOW_USERNAME` | `SERVICE_NOW_USERNAME` |
| Password | `SERVICENOW_PASSWORD` | `SERVICE_NOW_PASSWORD` |

The instance value should include `https://`.

### Reference an existing local credential file

Rather than copying values, set this non-secret path in this fork's ignored `.env` file:

```dotenv
SERVICENOW_ENV_FILE=D:\DEV\HTS\ServiceNow\.env
MCP_TRANSPORT=stdio
```

At startup the fork loads its own `.env`, then loads the referenced file if it exists. Variables provided by the OS environment retain highest precedence.

## Validate safely

`now_test_connection` reads a maximum of one record from `cmdb_ci`. Its result reports only the status and `auth_method`; it never returns the username or password.

The account must have ServiceNow REST access to the requested tables. A `403` is an account/table authorization issue, not an MCP token-refresh issue, because Basic Auth has no token lifecycle.

For CI detail lookup, use the `sys_id` included by `quick_ci_search` when a
custom CI class has no conventional `number` field. `get_ci_details(sys_id)`
resolves the raw `sys_class_name` from `cmdb_ci` and reads the matching custom
table automatically.

## Security constraints

- Keep the service account least-privileged.
- Do not configure write roles unless the corresponding MCP tools are intentionally needed.
- Keep this server on local stdio for Obsidian/EA use.
- This Basic Auth fork intentionally rejects SSE and all non-stdio transports. Use the H104 CMDB MCP for an explicitly secured HTTP/SSE deployment.

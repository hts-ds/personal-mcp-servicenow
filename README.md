# H104 ServiceNow MCP — Basic Auth Fork

This is the H104 fork of [Papamzor/personal-mcp-servicenow](https://github.com/Papamzor/personal-mcp-servicenow). It retains the upstream MCP tools, filter pipeline, query handling, audit logging, and stdio launcher, but replaces its OAuth client-credentials runtime with direct ServiceNow HTTP Basic Auth.

Use it as a broad ServiceNow MCP server. For EA/CMDB-only work, prefer the companion H104 CMDB MCP because it is read-only and enforces the H104 CI scope.

## What changed in this fork

- OAuth token cache, refresh, token endpoint, and 401 retry code were removed.
- `auth/ServiceNowBasicAuthClient` sends a Basic authorization header on every REST call.
- The configuration accepts both the fork's `SERVICENOW_*` variables and the existing H104 `SERVICE_NOW_*` variables.
- `SERVICENOW_ENV_FILE` can reference an existing protected local `.env` file, so credentials do not need to be copied into this repository.
- The connection tool is now `now_test_connection`; it performs a read-only `cmdb_ci` request and never returns a password.
- This fork is stdio-only. It intentionally rejects remote SSE because a Basic Auth-backed, write-capable MCP server must not expose an unauthenticated network endpoint.

See [docs/H104_BASIC_AUTH_MIGRATION.md](docs/H104_BASIC_AUTH_MIGRATION.md) for the detailed design and [BASIC_AUTH_SETUP_GUIDE.md](BASIC_AUTH_SETUP_GUIDE.md) for configuration.

## Local setup (recommended: stdio)

The H104 developer machine has no free space on `D:` for a virtual environment. Keep the repository on `D:` and create the virtual environment on `C:` instead:

```powershell
$venv = "$HOME\.venvs\personal-mcp-servicenow-basic-auth"
uv venv $venv
uv pip install --python "$venv\Scripts\python.exe" -r requirements.txt -r requirements-dev.txt
```

Create a local `.env` from `.env.example`. To reuse the supplied H104 credential file without copying any secret, the local configuration can contain only:

```dotenv
SERVICENOW_ENV_FILE=D:\DEV\HTS\ServiceNow\.env
MCP_TRANSPORT=stdio
```

`SERVICENOW_ENV_FILE`, `.env`, and all credential values are ignored by Git. Do not commit a username, password, or Authorization header.

## Obsidian / MCP stdio connection

Configure the MCP client with the persistent `C:` virtual-environment Python executable and the fork launcher:

```json
{
  "mcpServers": {
    "servicenow-basic-auth": {
      "command": "C:\\Users\\H104082101171\\.venvs\\personal-mcp-servicenow-basic-auth\\Scripts\\python.exe",
      "args": [
        "D:\\DEV\\HTS\\personal-mcp-servicenow-basic-auth\\personal_mcp_servicenow_main.py"
      ],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "SERVICENOW_ENV_FILE": "D:\\DEV\\HTS\\ServiceNow\\.env"
      }
    }
  }
}
```

The configuration deliberately contains no ServiceNow credential. See the Obsidian note created with this implementation for the H104 CMDB-specific server and comparison.

## Validate the read-only connection

```powershell
$python = "$HOME\.venvs\personal-mcp-servicenow-basic-auth\Scripts\python.exe"
& $python -c "import asyncio; from auth.client import ServiceNowBasicAuthClient; print(asyncio.run(ServiceNowBasicAuthClient().test_connection()))"
```

The test reads at most one CMDB CI. It does not create, update, or delete ServiceNow records.

## MCP tool boundary

The upstream tool surface is broad (generic tables, CMDB, knowledge, SLA, and private-task workflows). Some registered tools can write records, including private-task and knowledge-article operations. Basic Auth does not grant permissions by itself; ServiceNow roles remain the authorization boundary. Use the H104 CMDB MCP for normal EA CI discovery and detail lookup.

Useful read-only CI tools in this fork include:

- `find_cis_by_type(ci_type)`
- `search_cis_by_attributes(name, ip_address, location, status)`
- `get_ci_details(ci_identifier)`
- `similar_cis_for_ci(ci_number)`
- `get_all_ci_types()`
- `quick_ci_search(search_term)`

For an instance-specific CI class that has no `number` field, pass the `sys_id`
returned by `quick_ci_search` to `get_ci_details(sys_id)`. The fork looks up
the raw base-CMDB class and then fetches detail from the resolved custom table.

## Transport

`stdio` is the only transport in this fork and is the H104/Obsidian deployment target. The process exits with code `2` for any other `MCP_TRANSPORT` value. Use the companion H104 CMDB MCP when a secured Streamable HTTP/SSE endpoint is required.

## Verification

```powershell
$python = "$HOME\.venvs\personal-mcp-servicenow-basic-auth\Scripts\python.exe"
& $python -m pytest -q
& $python -m compileall -q auth http_layer Table_Tools
```

The migration contract is covered by Basic Auth header, no-token-cache, read/write error, configuration-alias, stdio, and no-secret status tests.

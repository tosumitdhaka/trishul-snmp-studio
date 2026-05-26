# API Reference

This is the practical API reference for the current `2.x` runtime.

For complete request and response schemas, use the OpenAPI document served by
the running app at `/docs`.

## API Surface

All operator-facing routes are under `/api/...`. There is one unified API —
no separate `v2` surface for simulator, catalog, runtime, or history.

## Public Endpoints

- `GET /api/meta` — product metadata (name, version)
- `GET /api/health` — basic health check
- `GET /api/healthz/ui` — operator shell probe

## WebSocket

`GET /api/ws?token=<session-token>` — WebSocket handshake

The browser sends `ping` keepalives; the server replies with `pong`.

Server push message types:

- `full_state` — sent on connect; snapshot of simulator, traps, stats, and mibs
- `status` — simulator and trap receiver running state
- `stats` — current counters
- `mibs` — loaded MIB summary
- `trap` — new trap received
- `simulator_log` — new simulator activity entry

## Session And Settings

- `POST /api/settings/login` — authenticate; returns `{token, username}`
- `POST /api/settings/logout`
- `GET /api/settings/check` — validate active token
- `POST /api/settings/auth` — rotate credentials
- `GET /api/settings/app` — read operator app settings
- `POST /api/settings/app` — update operator app settings

Login request:
```json
{"username": "admin", "password": "admin123"}
```

All authenticated endpoints require `X-Auth-Token: <token>` header.

## Stats

- `GET /api/stats/` — aggregated stats (simulator, traps, walker, mibs)
- `DELETE /api/stats/` — reset counters

## Simulator

- `GET /api/simulator/status`
- `POST /api/simulator/start` — `{"port": 1061, "community": "public"}`
- `POST /api/simulator/stop`
- `POST /api/simulator/restart`
- `GET /api/simulator/data` — read custom OID overrides
- `POST /api/simulator/data` — save custom OID overrides
- `GET /api/simulator/logs` — recent activity log
- `DELETE /api/simulator/logs` — clear activity log

## Walk

- `POST /api/walk/execute`

```json
{
  "target": "127.0.0.1",
  "port": 1061,
  "community": "public",
  "oid": "1.3.6.1.2.1.1",
  "parse": true,
  "use_mibs": true
}
```

Optional `json_format`: `"current"` (default) or `"grouped"`.

## Traps

- `GET /api/traps/status`
- `POST /api/traps/start` — `{"port": 1162, "community": "public", "resolve_mibs": true}`
- `POST /api/traps/stop`
- `POST /api/traps/send`
- `GET /api/traps/` — list recent received trap events
- `DELETE /api/traps/` — clear received events

Send request:
```json
{
  "target": "127.0.0.1",
  "port": 1162,
  "community": "public",
  "oid": "IF-MIB::linkDown",
  "varbinds": [
    {"oid": "1.3.6.1.2.1.2.2.1.1.1", "type": "Integer", "value": 1}
  ]
}
```

## MIBs

- `GET /api/mibs/status` — loaded modules, failed compile runs, source groups
- `GET /api/mibs/objects` — flat object list from active bundle
- `GET /api/mibs/traps` — notification list from active bundle
- `GET /api/mibs/resolve?oid=<oid>&mode=<numeric|symbolic>` — OID resolution
- `POST /api/mibs/validate-batch` — analyze upload before committing
- `POST /api/mibs/upload` — upload and compile MIB files
- `POST /api/mibs/reload` — recompile all uploaded MIBs
- `POST /api/mibs/fetch-dependencies` — fetch missing dependency MIBs
- `POST /api/mibs/export` — export catalog as JSON or CSV
- `POST /api/mibs/download` — download one stored MIB source or a zip of multiple source files
- `DELETE /api/mibs/file` — delete one uploaded MIB file (body: `{"path": "..."}`)
- `POST /api/mibs/delete-batch` — delete multiple uploaded MIB files
- `DELETE /api/mibs/{filename:path}` — delete by path (URL-encoded)

`GET /api/mibs/status` returns both the deduplicated effective runtime view and
the per-source inventory view:

- `mibs` and `active_modules` — the same deduplicated active module list
- `errors` and `failed_modules` — the same true-failure list
- `source_inventory` — per-source membership and status, including `shadowed` rows
- `source_groups` — source-group totals derived from the stored inventory

Source-group export requests keep source-group membership. Global or all-module
exports stay deduplicated to the active runtime bundle.

Catalog export request body:

```json
{
  "format": "json",
  "modules": ["IF-MIB"],
  "notifications": ["IF-MIB::linkDown"],
  "source_groups": ["juniper"],
  "export_type": "notifications"
}
```

Supported `export_type` values:

- `catalog`
- `summary`
- `modules`
- `objects`
- `notifications`

Export responses always include `summary`, `filters`, and `metadata`. JSON
exports may also include:

- `modules`
- `objects`
- `notifications`
- `notification_members`

For `notifications`, JSON stays notification-centric and nests the resolved
member details under each notification entry. CSV flattens those member details
into one row per member while retaining the parent notification identity.

Raw source download request body:

```json
{
  "paths": ["juniper/JUNIPER-MAG-MIB.mib", "juniper/JUNIPER-IF-MIB.mib"]
}
```

`POST /api/mibs/download` returns the original source file for a single path, or
a zip archive when multiple managed source files are requested.

Upload request (multipart):
- field: `files[]` — one or more `.mib`, `.txt`, or `.my` files
- optional field: `source_group` — target upload group (default: `common`)
- optional field: `compile_mode` — `full` (default) or `partial`

## MIB Browser

- `GET /api/mibs/browse/modules` — list loaded modules
- `GET /api/mibs/browse/tree/module?module=<name>&type_filter=<type>` — module node tree
- `GET /api/mibs/browse/tree/oid?root_oid=<oid>&depth=<n>&module=<name>` — OID subtree
- `GET /api/mibs/browse/search?q=<query>&module=<name>&type_filter=<type>` — search nodes
- `GET /api/mibs/browse/node/{oid}` — single node detail with breadcrumb and trap objects

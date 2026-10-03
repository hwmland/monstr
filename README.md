# Monstr

Monstr is a full-stack STORJ log monitoring platform. The asynchronous FastAPI backend tails multiple log files, persists new lines into SQLite, and exposes a REST API. The React + TypeScript frontend renders the stored data today and is prepared for WebSocket streaming in the future.

## Features

- Async log tailing across multiple files defined at startup
- Automatic database bootstrap and periodic data retention cleanup
- REST API for querying stored log, reputation, and transfer data (served under `/api`)
- REST API for adding sensors to Home Assistant
- Production build of the client served directly by the Python backend
- Prepared to run in Docker (multi-stage Dockerfile included)
- Modern React stack (Vite, TypeScript, Zustand) with testing via Vitest and Testing Library

## Project Structure

- `server/` – FastAPI service, background workers, database models, and tests
- `client/` – Vite-powered React SPA with routing, services, and state store

## Requirements

- Python 3.11+
- Node.js 18+
- SQLite (bundled with standard Python installations)

## Server

### Backend Setup

PowerShell (Windows)

```powershell
cd server
python -m venv .vent.monstr
.\.vent.monstr\Scripts\activate
pip install -r requirements.txt
```

Bash (macOS / Linux / WSL)

```bash
cd server
python3 -m venv .vent.monstr
source .vent.monstr/bin/activate
pip install -r requirements.txt
```

Deactivate the environment at any time with `deactivate`.

### Running the server

> **Important:** run the CLI from the repository root (`monstr/`), not from the `server/` subdirectory. If you just installed dependencies inside `server/`, execute `cd ..` first.

PowerShell (Windows):

```powershell
# from the project root with the virtual environment still activated
python -m server.src.cli --source myNode:.\testdata\node.log --source otherNode:C:\path\to\node2.log
```

Bash (macOS / Linux):

```bash
# from the project root with the virtual environment activated
python -m server.src.cli --source myNode:./testdata/node.log --source otherNode:/path/to/node2.log
```

Node specifications follow the `NAME:PATH` pattern so each database record references the logical node name instead of the filesystem path. Below is a compact reference for the CLI, environment overrides, and examples showing how to run the server.

### CLI usage

Basic shape for starting the service:

PowerShell (Windows):

```powershell
# from the project root with the virtual environment activated
python -m server.src.cli --source myNode:.\testdata\node.log --source otherNode:C:\path\to\node2.log
```

Bash (macOS / Linux / WSL):

```bash
# from the project root with the virtual environment activated
python -m server.src.cli --source myNode:./testdata/node.log --source otherNode:/path/to/node2.log
```

Supported CLI flags

- `--config-file PATH` — Load backend settings from a JSONC file.
- `--config-json JSONC` — Load backend settings from an inline JSONC value. This is mutually exclusive with `--config-file`.
- `--source NAME:SPEC` (repeatable) — Declare a log source in the preferred sequence. Use `NAME:PATH` for local log files or `NAME:HOST:PORT` for remote TCP sources. Repeat the flag to declare multiple sources; their declared order is preserved at startup. Append `|http://localhost:14002` (or another HTTP(S) URL) to associate a nodeapi endpoint with the source.

  **Deprecation notice:** Local file sources (`--source NAME:PATH` or JSONC `type: "file"`) are obsolete, are no longer guaranteed to work, and will be removed in a future release. Use streaming TCP sources (`--source NAME:HOST:PORT` or JSONC `type: "tcp"`) instead.

  Implementation note: you can use the companion project `hwmland/tailsender` as a lightweight remote sender that tails a file and forwards appended lines to Monstr over TCP. Configure a tailsender instance on the remote host and point Monstr at it with `--source name:host:port`.

- `--host HOST` — Bind the API server to the specified host (default: `127.0.0.1`). Setting `--host 0.0.0.0` (or `--host ::`) makes the API listen on all network interfaces so the server becomes reachable from other machines on the network. Use this when running inside a container or when exposing the API to other hosts. Beware that binding to all interfaces exposes the API to your network; secure the host appropriately (firewall, auth) if used in production.
- `--port PORT` — Bind the API server to the specified port (default: `8000`).
- `--log-level LEVEL` — Override the API root logger level (e.g. `info`, `debug`). This sets the overall verbosity for the server.
- `--log NAME:LEVEL` (repeatable) — Per-logger override in `LOGGER:LEVEL` form. These take precedence over the `MONSTR_LOG_OVERRIDES` environment variable and are useful to enable fine-grained debug output (for example `--log api.call:DEBUG`).

Environment variables

- `MONSTR_CONFIG_FILE` — Path to a JSONC configuration file.
- `MONSTR_CONFIG_JSON` — Inline JSONC configuration, suitable for a Docker Compose YAML block scalar. Set at most one of these selectors unless a CLI config option is supplied; an explicit CLI selector takes precedence over both.
- `MONSTR_LOG_OVERRIDES` — Comma-separated `LOGGER:LEVEL` pairs (e.g. `root:INFO,services.cleanup:WARNING`). The CLI `--log` flag takes precedence for any logger it names.

### JSONC backend configuration

JSONC adds comments and trailing commas to JSON. The configuration is partial: omitted values continue to come from legacy `MONSTR_*` environment variables or application defaults. The grouped keys map to the existing backend settings:

```jsonc
{
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "reload": false,
    "log_level": "info",
    "cors_allow_origins": ["http://localhost:5173", "http://127.0.0.1:5173"]
  },
  "database": {
    "url": "sqlite+aiosqlite:///./data/monstr.db",
    "sql_echo": false,
    "write_suspend_seconds": 60
  },
  "nodeapi": {
    "poll_interval": 1.0, // Log polling interval
    "batch_size": 32,
    "unprocessed_dir": "../data/",
    "poll_interval_seconds": 60,
    "estimated_payout_interval_seconds": 300,
    "held_history_interval_seconds": 300,
    "satellite_details_interval_seconds": 300,
    "paystub_interval_seconds": 600
  },
  "nodegroups": [
    {
      "name": "group-a",
      "icon": "mdi:home",
      "locations": [
        {
          "alias": "site-a",
          "ip": "192.0.2.10",
          "nodes": [
            {
              "name": "node-a",
              "type": "tcp",
              "host": "logs.example.net",
              "port": 9001,
              "nodeapi_url": "http://node-a.example.net:14001/",
              "disqualifications": [
                { "satellite_id": null, "period": "2025-10" }
              ]
            },
            {
              "name": "node-b",
              "type": "file",
              "path": "./logs/node-b.log"
            }
          ]
        }
      ]
    }
  ],
  "maintenance": {
    "cleanup_interval_seconds": 300,
    "grouping_interval_seconds": 120,
    "retention": {
      "default_minutes": 40320,
      "transfers_minutes": 1440,
      "log_entries_minutes": 40320,
      "transfer_grouped_minutes": -1,
      "hashstore_compaction_minutes": 2628000
    }
  },
  "frontend": {
    "dist_dir": "../client/dist"
  },
  "logging": {
    "overrides": {
      "api.call": "DEBUG"
    }
  }
}
```

Each node uses `type: "tcp"` with `host` and `port`, or `type: "file"` with `path`; `nodeapi_url` is optional. A location's IP24 expected-instance count is derived from the number of valid nodes in its `nodes` array. Node sources are applied in nodegroup, location, then node order. Nodegroup names are retained for future use. A node's optional `disqualifications` list inherits that node's name as the source; `satellite_id` may be omitted, `null`, or `"all"` to mean all satellites.

Each nodegroup may optionally specify an MDI icon identifier such as `"icon": "mdi:home"` as a sibling of `name` and `locations`. The identifier must be a non-empty `mdi:<name>` value; the backend validates its syntax but does not contact Iconify. The browser loads configured icons from `https://api.iconify.design`, so the client browser needs network access to that service. Icons appear before member node names on node buttons and before group names in the nodegroup selector; if an icon cannot be loaded, selection remains usable and shows an accessible fallback.

When `nodegroups` is present, it supplies the source, IP24, and disqualification settings. If omitted, those settings continue to use the legacy `MONSTR_SOURCES`, `MONSTR_IP24`, and `MONSTR_DISQUAL` values. The legacy repeatable `--source`, `--ip24`, and `--disqual` flags remain supported and replace their corresponding configured list. Explicit CLI flags override JSONC; JSONC overrides legacy environment variables and `.env`; defaults apply last.

Unknown JSONC keys produce a warning and are ignored. Invalid entries in node, location, or disqualification lists produce a warning and are skipped; an all-invalid configured list becomes empty. Invalid scalar values, invalid list containers, or an unreadable/malformed JSONC document stop startup with a clear configuration error; setting errors include their config path. A configured group `icon` with invalid syntax also stops startup with its config path.

Nodegroup names must be unique without regard to case; `All` and `<groups>` are reserved. Node names must be unique across groups and cannot equal `All` in any letter case. These identity conflicts stop startup. Empty groups are returned by the nodegroups API but disabled in the client selector.

You can pass a JSONC file or inline JSONC from the CLI:

PowerShell:

```powershell
python -m server.src.cli --config-file .local\config.local.jsonc

$config = @'
{
  "api": { "port": 8000 }
}
'@
python -m server.src.cli --config-json $config
```

Bash:

```bash
python -m server.src.cli --config-file .local/config.local.jsonc
python -m server.src.cli --config-json '{"api":{"port":8000}}'
```

### Legacy CLI examples

The flags and environment variables below remain available for compatibility.

PowerShell (Windows) example that sets two nodes and enables the request-finish debug messages emitted by the `api.call` logger:

```powershell
python -m server.src.cli \
  --source Hashnode:.\testdata\hash.log|http://localhost:14002 \
  --source Blobnode:.\testdata\blob.log \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info \
  --log api.call:DEBUG
```

Bash (macOS / Linux) equivalent:

```bash
python -m server.src.cli \
  --source Hashnode:./testdata/hash.log|http://localhost:14002 \
  --source Blobnode:./testdata/blob.log \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info \
  --log api.call:DEBUG
```

### Request-finish debug logging (api.call)

Monstr includes a small request-finish middleware that can emit a concise DEBUG message whenever an HTTP request completes. The message contains the client address, HTTP method, full path (including query), response status code and duration in milliseconds.

This behavior is controlled solely by the `api.call` logger. To enable the messages, set `api.call` to `DEBUG` using any of the supported mechanisms (environment/CLI/admin API). For example, use the admin API to set the logger at runtime:

```http
POST /api/admin/loggers
Content-Type: application/json

{ "name": "api.call", "level": "DEBUG" }
```

To disable, set the logger back to `INFO` (or your preferred level):

```http
POST /api/admin/loggers
Content-Type: application/json

{ "name": "api.call", "level": "INFO" }
```

Alternatively, set the logger at startup with `MONSTR_LOG_OVERRIDES` or the
CLI `--log` flag (CLI wins over environment values).

Notes:

- The middleware is always registered but checks the `api.call` logger's
  level for DEBUG each request, so toggles take effect immediately.
- We chose logger-level gating instead of a separate runtime setting so you can
  use existing logging controls to manage verbosity without adding another
  configuration surface.

### What the server serves

- OpenAPI docs: once running, the backend exposes the OpenAPI UI at `http://<host>:<port>/api/docs` (default `http://127.0.0.1:8000/api/docs`).
- Nodegroups API: `GET /api/nodegroups` returns active configured group names, their node names, and an optional MDI `icon` identifier. Empty groups are returned with an empty `nodes` array; groups are omitted when legacy sources override nodegroups.
- Frontend SPA: if `client/dist` exists (a production build of the client), FastAPI will serve the compiled SPA at the root path `/` (for example `http://127.0.0.1:8000/`).

- Overall status API: the server exposes a lightweight health/status endpoint at
  `/api/overall-status` which returns a compact JSON summary of the running
  service (configured source count, last-processed timestamps, processing
  lag, database connectivity and similar high-level metrics). This endpoint is
  intentionally small and stable so it can be polled frequently by external
  systems. It's provided primarily as a convenience for Home Assistant users —
  you can create a simple REST sensor in Home Assistant to surface Monstr's
  health into dashboards and automations.

  Example Home Assistant REST sensor configuration:

```yaml
rest:
  resource: http://pve1.internal:9898/api/overall-status
  method: POST
  headers:
    User-Agent: Home Assistant
    Content-Type: application/json
  payload: '{ "nodes": [ ] }'
  scan_interval: 60
  sensor:
    - name: "STORJ Download Speed"
      value_template: "{{ (float(value_json.total.minute1.downloadSpeed) / 1000000) }}"
      unit_of_measurement: "Mbps"
    - name: "STORJ Upload Speed"
      value_template: "{{ value_json.total.minute1.uploadSpeed / 1000000 }}"
      unit_of_measurement: "Mbps"
```

<details>
<summary>API output: /api/overall-status (click to expand)</summary>

The `/api/overall-status` endpoint returns an `OverallStatusResponse` containing a `total` summary and a `nodes` mapping keyed by node name. Each value follows the `NodeOverallMetrics` schema and contains reputation aggregates and short transfer windows. The request body is `OverallStatusRequest` (JSON `{ "nodes": [...] }`); omit or send an empty list to request all nodes.

Response shape (serialized field names shown):

- `total` (object): aggregate `NodeOverallMetrics` across selected nodes.
- `nodes` (object): mapping where each property name is a node identifier and the value is a `NodeOverallMetrics` object for that node.

NodeOverallMetrics fields:

- `node` (string)
- `minOnline`, `minAudit`, `minSuspension` (float) — minimum reputation scores observed across satellites
- `avgOnline`, `avgAudit`, `avgSuspension` (float) — simple averages of reputation scores
- `minute1`, `minute3`, `minute5` (objects) — `TransferWindowMetrics` for 1/3/5 minute windows
- `currentMonthPayout` (object) — optional payout summary for the current month gathered from each node's nodeapi. Fields: `estimatedPayout`, `heldBackPayout`, `downloadPayout`, `repairPayout`, `diskPayout`, `totalHeldPayout` (all numeric or null, in `USD`).

TransferWindowMetrics fields (per window):

- `downloadSize`, `uploadSize` (int) — total bytes transferred in the window
- `downloadCount`, `uploadCount` (int) — successful operation counts
- `downloadCountTotal`, `uploadCountTotal` (int) — total attempted operations (including failures)
- `downloadSuccessRate`, `uploadSuccessRate` (float 0..1) — success ratios
- `downloadSpeed`, `uploadSpeed` (float) — computed speeds; implementation reports bytes/sec converted to bits/sec (bytes/window_seconds \* 8)

Example payload (matches current implementation):

```json
{
  "total": {
    "node": "total",
    "minOnline": 0.98,
    "minAudit": 0.95,
    "minSuspension": 0.0,
    "avgOnline": 0.993,
    "avgAudit": 0.976,
    "avgSuspension": 0.0,
    "minute1": {
      "downloadSize": 1234567,
      "uploadSize": 234567,
      "downloadCount": 12,
      "uploadCount": 3,
      "downloadCountTotal": 13,
      "uploadCountTotal": 4,
      "downloadSuccessRate": 0.9230769230769231,
      "uploadSuccessRate": 0.75,
      "downloadSpeed": 164608.93333333335,
      "uploadSpeed": 31274.666666666668
    },
    "minute3": {
      /* ... */
    },
    "minute5": {
      /* ... */
    },
    "currentMonthPayout": {
      "estimatedPayout": 123.45,
      "heldBackPayout": 10.0,
      "totalHeldPayout": 75.25,
      "downloadPayout": 45.0,
      "repairPayout": 2.5,
      "diskPayout": 65.95
    }
  },
  "nodes": {
    "hashnode": {
      "node": "hashnode",
      "minOnline": 0.99,
      "minAudit": 0.97,
      "minSuspension": 0.0,
      "avgOnline": 0.995,
      "avgAudit": 0.98,
      "avgSuspension": 0.0,
      "minute1": {
        "downloadSize": 1234567,
        "uploadSize": 234567,
        "downloadCount": 12,
        "uploadCount": 3,
        "downloadCountTotal": 13,
        "uploadCountTotal": 4,
        "downloadSuccessRate": 0.923,
        "uploadSuccessRate": 0.75,
        "downloadSpeed": 164608.9,
        "uploadSpeed": 31274.7
      },
      "minute3": {
        /* ... */
      },
      "minute5": {
        /* ... */
      },
      "currentMonthPayout": {
        "estimatedPayout": 123.45,
        "heldBackPayout": 10.0,
        "totalHeldPayout": 75.25,
        "downloadPayout": 45.0,
        "repairPayout": 2.5,
        "diskPayout": 65.95
      }
    }
  }
}
```

Notes:

- The `downloadSpeed` / `uploadSpeed` values are in bits per second as computed by the implementation (bytes/window_seconds \* 8). Convert to Mbps in Home Assistant with `value_json.total.minute1.downloadSpeed / 1000000`.
- Use `value_template` to extract a single numeric value for a sensor and `json_attributes_path: "$"` to expose the rest of the payload as attributes.

</details>

Tip: always run the CLI from the repository root so relative paths in `NAME:PATH` pairs are resolved consistently.

### Backend Tests

PowerShell (Windows):

```powershell
pytest
```

Bash (macOS / Linux / WSL):

```bash
pytest
```

## Frontend Workflow

### Build for the Python Server

PowerShell (Windows):

```powershell
cd client
npm install
npm run build
```

Bash (macOS / Linux / WSL):

```bash
cd client
npm install
npm run build
```

The compiled assets land in `client/dist`. On the next backend start, FastAPI will serve those files automatically.

### Local Development & Tests

PowerShell (Windows):

```powershell
npm run dev         # Vite on http://127.0.0.1:5173, using the local API
npm run dev:server  # Vite using http://app-pve2.internal:9898/api
npm test            # runs Vitest
```

Bash (macOS / Linux / WSL):

```bash
npm run dev         # Vite on http://127.0.0.1:5173, using the local API
npm run dev:server  # Vite using http://app-pve2.internal:9898/api
npm test            # runs Vitest
```

`npm run dev` keeps the default API URL at `http://localhost:8000/api`. The `dev:server` script loads `client/.env.server` to target `http://app-pve2.internal:9898/api`; that server must allow browser requests from the Vite origin (`http://127.0.0.1:5173`) through CORS.

## Container Image

The repository includes a multi-stage Dockerfile that builds the Vite client and bundles it alongside the FastAPI server inside a slim Python runtime.

### Build the Image

PowerShell (Windows):

```powershell
docker build -t monstr .
```

Bash (macOS / Linux / WSL):

```bash
docker build -t monstr .
```

Run the container with sample logs mounted (example binds port 8000 and mounts a `testdata` directory):

PowerShell (Windows):

```powershell
docker run
  -p 8000:8000 \
  -e MONSTR_SOURCES="hashnode:/logs/hash.log,blobnode:/logs/blob.log" \
  -v ${PWD}\testdata:/logs:ro \
  monstr:latest
```

Bash (macOS / Linux / WSL):

```bash
docker run -p 8000:8000 \
  -e MONSTR_SOURCES="hashnode:/logs/hash.log,blobnode:/logs/blob.log" \
  -v ${PWD}/testdata:/logs:ro \
  monstr:latest
```

Docker Compose can mount a JSONC file (recommended for larger settings) or put inline JSONC in an environment block. The repository's `.local/` directory is ignored by Git, making it suitable for a private local configuration file.

Mounted-file example:

```yaml
services:
  monstr:
    image: ghcr.io/hwmland/monstr:latest
    ports:
      - "8000:8000"
    environment:
      MONSTR_CONFIG_FILE: /config/monstr.jsonc
    volumes:
      - ./.local/config.local.jsonc:/config/monstr.jsonc:ro
      - ./logs:/logs:ro
```

Inline JSONC example:

```yaml
services:
  monstr:
    image: ghcr.io/hwmland/monstr:latest
    ports:
      - "8000:8000"
    environment:
      MONSTR_CONFIG_JSON: |
        {
          "api": {
            "host": "0.0.0.0",
            "port": 8000
          },
          "nodegroups": [
            {
              "name": "group-a",
              "icon": "mdi:home",
              "locations": [
                {
                  "alias": "site-a",
                  "ip": "192.0.2.10",
                  "nodes": [
                    {
                      "name": "node-a",
                      "type": "tcp",
                      "host": "logs.example.net",
                      "port": 9001
                    }
                  ]
                }
              ]
            }
          ]
        }
```

## Development notes and next steps

- The log parsing logic lives in `server/src/services/log_monitor.py` and can be extended to support additional formats.
- The cleanup/retention settings are configurable in the server configuration; see `server/src/config.py`.
- Frontend charting uses Recharts and has a centralized time-format preference stored in localStorage under the key `pref_time_24h`.

Contributions and issues are welcome — open a PR or file an issue with a reproducible example.

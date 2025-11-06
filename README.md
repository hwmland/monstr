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

- `--source NAME:SPEC` (repeatable) — Declare a log source in the preferred sequence. Use `NAME:PATH` for local log files or `NAME:HOST:PORT` for remote TCP sources. Repeat the flag to declare multiple sources; their declared order is preserved at startup.

  Implementation note: you can use the companion project `hwmland/tailsender` as a lightweight remote sender that tails a file and forwards appended lines to Monstr over TCP. Configure a tailsender instance on the remote host and point Monstr at it with `--source name:host:port`.

- `--host HOST` — Bind the API server to the specified host (default: `127.0.0.1`). Setting `--host 0.0.0.0` (or `--host ::`) makes the API listen on all network interfaces so the server becomes reachable from other machines on the network. Use this when running inside a container or when exposing the API to other hosts. Beware that binding to all interfaces exposes the API to your network; secure the host appropriately (firewall, auth) if used in production.
- `--port PORT` — Bind the API server to the specified port (default: `8000`).
- `--log-level LEVEL` — Override the API root logger level (e.g. `info`, `debug`). This sets the overall verbosity for the server.
- `--log NAME:LEVEL` (repeatable) — Per-logger override in `LOGGER:LEVEL` form. These take precedence over the `MONSTR_LOG_OVERRIDES` environment variable and are useful to enable fine-grained debug output (for example `--log api.call:DEBUG`).

Environment variables

- `MONSTR_LOG_OVERRIDES` — Comma-separated `LOGGER:LEVEL` pairs (e.g. `root:INFO,services.cleanup:WARNING`). The CLI `--log` flag takes precedence for any logger it names.

Examples

PowerShell (Windows) example that sets two nodes and enables the request-finish debug messages emitted by the `api.call` logger:

```powershell
python -m server.src.cli \
  --source Hashnode:.\testdata\hash.log \
  --source Blobnode:.\testdata\blob.log \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info \
  --log api.call:DEBUG
```

Bash (macOS / Linux) equivalent:

```bash
python -m server.src.cli \
  --source Hashnode:./testdata/hash.log \
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

The `/api/overall-status` endpoint returns an `OverallStatusResponse` containing a `total` summary and a `nodes` array. Each entry follows the `NodeOverallMetrics` schema and contains reputation aggregates and short transfer windows. The request body is `OverallStatusRequest` (JSON `{ "nodes": [...] }`); omit or send an empty list to request all nodes.

Response shape (serialized field names shown):

- `total` (object): aggregate `NodeOverallMetrics` across selected nodes.
- `nodes` (array): list of `NodeOverallMetrics` objects for each node.

NodeOverallMetrics fields:

- `node` (string)
- `minOnline`, `minAudit`, `minSuspension` (float) — minimum reputation scores observed across satellites
- `avgOnline`, `avgAudit`, `avgSuspension` (float) — simple averages of reputation scores
- `minute1`, `minute3`, `minute5` (objects) — `TransferWindowMetrics` for 1/3/5 minute windows

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
    }
  },
  "nodes": [
    {
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
      }
    }
  ]
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
npm run dev   # launches Vite dev server on http://127.0.0.1:5173
npm test      # runs Vitest
```

Bash (macOS / Linux / WSL):

```bash
npm run dev   # launches Vite dev server on http://127.0.0.1:5173
npm test      # runs Vitest
```

During development the backend API remains available at `http://127.0.0.1:8000/api`.

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

Docker Compose example (service runs the CLI and sets logger overrides):

```yaml
services:
  monstr:
    image: ghcr.io/hwmland/monstr:latest
    ports:
      - "8000:8000"
    environment:
  MONSTR_SOURCES="hashnode:/logs/hash.log,blobnode:/logs/blob.log"
      MONSTR_LOG_OVERRIDES="root:INFO,services.cleanup:WARNING"
    volumes:
      - ./testdata:/logs:ro
```

## Development notes and next steps

- The log parsing logic lives in `server/src/services/log_monitor.py` and can be extended to support additional formats.
- The cleanup/retention settings are configurable in the server configuration; see `server/src/config.py`.
- Frontend charting uses Recharts and has a centralized time-format preference stored in localStorage under the key `pref_time_24h`.

Contributions and issues are welcome — open a PR or file an issue with a reproducible example.

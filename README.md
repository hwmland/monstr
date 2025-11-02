# Monstr

Monstr is a full-stack log monitoring platform. The asynchronous FastAPI backend tails multiple log files, persists new lines into SQLite, and exposes a REST API. The React + TypeScript frontend renders the stored data today and is prepared for WebSocket streaming in the future.

## Features

- Async log tailing across multiple files defined at startup
- Automatic database bootstrap and periodic data retention cleanup
- REST API for querying stored log, reputation, and transfer data (served under `/api`)
- Production build of the client served directly by the Python backend
- Modern React stack (Vite, TypeScript, Zustand) with testing via Vitest and Testing Library

## Project Structure

- `server/` – FastAPI service, background workers, database models, and tests
- `client/` – Vite-powered React SPA with routing, services, and state store

## Requirements

- Python 3.11+
- Node.js 18+
- SQLite (bundled with standard Python installations)

## Backend Setup

### Windows PowerShell

```powershell
cd server
python -m venv .vent.monstr
.\.vent.monstr\Scripts\activate
pip install -r requirements.txt
```

### Bash (macOS / Linux / WSL)

```bash
cd server
python3 -m venv .vent.monstr
source .vent.monstr/bin/activate
pip install -r requirements.txt
```

Deactivate the environment at any time with `deactivate`.

### Running the API

> **Important:** run the CLI from the repository root (`monstr/`), not from the `server/` subdirectory. If you just installed dependencies inside `server/`, execute `cd ..` first.

```powershell
# from the project root with the virtual environment still activated
python -m server.src.cli --node myNode:.\testdata\node.log --node otherNode:C:\path\to\node2.log
```

Node specifications follow the `NAME:PATH` pattern so each database record references the logical node name instead of the filesystem path. The CLI also accepts overrides such as `--host`, `--port`, and `--log-level`. The backend serves the OpenAPI docs at `http://127.0.0.1:8000/api/docs` and the built frontend (when present) at `http://127.0.0.1:8000/`.

### Backend Tests

```powershell
pytest
```

## Frontend Workflow

### Build for the Python Server

```powershell
cd client
npm install
npm run build
```

The compiled assets land in `client/dist`. On the next backend start, FastAPI will serve those files automatically.

### Local Development & Tests

```powershell
npm run dev   # launches Vite dev server on http://127.0.0.1:5173
npm test      # runs Vitest
```

During development the backend API remains available at `http://127.0.0.1:8000/api`.

## Container Image

The repository includes a multi-stage Dockerfile that builds the Vite client and bundles it alongside the FastAPI server inside a slim Python runtime.

### Build the Image

````powershell
docker build -t monstr .
# Monstr

Monstr is a full-stack log monitoring platform. The asynchronous FastAPI backend tails multiple log files, persists new lines into SQLite, and exposes a REST API. The React + TypeScript frontend renders the stored data today and is prepared for WebSocket streaming in the future.

## Highlights

- Async tailing of multiple log files
- Automatic database bootstrap and configurable data retention
- REST API under `/api` for querying logs, transfers and derived aggregates
- The Python backend can serve a production build of the React frontend

## Project layout

- `server/` – FastAPI app, background workers, database models and tests
- `client/` – Vite + React SPA (TypeScript) with charts and UI

## Requirements

- Python 3.11+
- Node.js 18+

## Quickstart (backend)

These instructions assume you work from the repository root (the top-level `monstr/` folder).

Windows PowerShell

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
````

macOS / Linux / WSL

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

Run the CLI (example)

```powershell
# from the project root
python -m server.src.cli --node Hashnode:.\testdata\hash.log --node Blobnode:.\testdata\blob.log --log-level info
```

Notes

- Node entries are provided as NAME:PATH so database records keep a stable logical name rather than a filesystem path.
- The API OpenAPI docs are available at `http://127.0.0.1:8000/api/docs` when the server is running.

## CLI & logging configuration

Monstr's CLI accepts both environment-based and CLI-based logging overrides so you can control logger levels at startup. The rules are:

- Environment variable: `MONSTR_LOG_OVERRIDES` — a comma-separated list of `LOGGER:LEVEL` entries.
- CLI flag: `--log LOGGER:LEVEL` — a repeatable argument; CLI-provided overrides take precedence over the environment.

Examples (PowerShell)

```powershell
$env:MONSTR_LOG_OVERRIDES = "root:INFO,services.cleanup:WARNING"
python -m server.src.cli --node Hashnode:.\testdata\hash.log

# CLI overrides (these win for the named loggers)
python -m server.src.cli --node Hashnode:.\testdata\hash.log --log services.cleanup:DEBUG --log api:INFO
```

Docker / docker-compose example

```yaml
services:
	monstr:
		image: ghcr.io/hwmland/monstr:latest
		ports:
			- "8000:8000"
		environment:
			MONSTR_LOG_SOURCES: "hashnode:/logs/hash.log,blobnode:/logs/blob.log"
			MONSTR_LOG_OVERRIDES: "root:INFO,services.cleanup:WARNING"
		volumes:
			- ./testdata:/logs:ro
		command: ["python","-m","server.src.cli","--node","Hashnode:/logs/hash.log","--node","Blobnode:/logs/blob.log","--log","services.cleanup:DEBUG"]
```

The CLI will normalize formatters so the console output includes timestamps and the logger name (for example, `2025-11-02 12:34:56,789 root: Message...`).

## Request-finish debug logging (api.call)

Monstr includes a small request-finish middleware that can emit a concise DEBUG
message whenever an HTTP request completes. The message contains the client
address, HTTP method, full path (including query), response status code and
duration in milliseconds.

This behavior is controlled solely by the `api.call` logger. To enable the
messages, set `api.call` to `DEBUG` using any of the supported mechanisms
(environment/CLI/admin API). For example, use the admin API to set the logger at
runtime:

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

## Testing

Server tests are written with pytest and live under `server/src/tests`. Run them from the project root so imports resolve correctly:

PowerShell

```powershell
$env:PYTHONPATH = "."
pytest -q
```

macOS / Linux

```bash
PYTHONPATH=. pytest -q
```

Client (frontend)

```powershell
cd client
npm install
npm run dev    # development server (Vite)
npm run build  # build production assets
npm test       # run Vitest
```

When you run the production backend and the client has been built (`client/dist` exists), FastAPI will serve the compiled SPA at `/` automatically.

## Docker image

The repository contains a multi-stage `Dockerfile` that builds the client and bundles it with the Python runtime.

Build the image locally

```powershell
docker build -t monstr .
```

Run the container with sample logs mounted (PowerShell example)

```powershell
docker run `
	-p 8000:8000 `
	-e MONSTR_LOG_SOURCES="hashnode:/logs/hash.log,blobnode:/logs/blob.log" `
	-v ${PWD}\testdata:/logs:ro `
	ghcr.io/hwmland/monstr:latest
```

## Development notes and next steps

- The log parsing logic lives in `server/src/services/log_monitor.py` and can be extended to support additional formats.
- The cleanup/retention settings are configurable in the server configuration; see `server/src/config.py`.
- Frontend charting uses Recharts and has a centralized time-format preference stored in localStorage under the key `pref_time_24h`.

Contributions and issues are welcome — open a PR or file an issue with a reproducible example.

# Monstr

Monstr is a full-stack log monitoring platform. The asynchronous FastAPI backend tails multiple log files, persists new lines into SQLite, and exposes a REST API. The React + TypeScript frontend renders the stored data today and is prepared for WebSocket streaming in the future.

## Features

- Async log tailing across multiple files defined at startup
- Automatic database bootstrap and periodic data retention cleanup
- REST API for querying stored log entries and transfer events (served under `/api`)
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

## Next Steps

- Define the concrete parsing rules in `server/src/services/log_monitor.py`.
- Extend the REST API with richer filtering or aggregation endpoints.
- Wire up WebSocket broadcasting on the backend and consume it via `client/src/services/socketClient.ts`.
- Automate data retention parameters through configuration or UI controls.

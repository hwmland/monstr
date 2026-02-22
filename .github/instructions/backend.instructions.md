---
name: "Backend Instructions"
applyTo: "server/**"
description: "Instructions for the Python backend (FastAPI + SQLAlchemy + SQLite)."
---

# Backend Instructions (Python / FastAPI)

## Technology Stack

- **Python 3.11+** — use `from __future__ import annotations` in every file.
- **FastAPI** — async request handlers; all routes mounted under `/api`.
- **SQLModel** — table definitions that double as Pydantic models.
- **SQLAlchemy 2.0 async** — async engine + `async_sessionmaker`; driver is `aiosqlite`.
- **SQLite** — single-file database in `./data/`. No ORM migrations framework (Alembic); migrations are hand-written in `migrations.py`.
- **pydantic-settings** — `Settings` class in `config.py`; env vars prefixed with `MONSTR_`.
- **pytest + pytest-asyncio** — test suite in `server/tests/`.

## Architecture

### Layered Design

```
routes (API)  →  repositories (DB access)  →  models (SQLModel tables)
                 services (background tasks) ↗
```

- **Routes** (`api/routes/`) — thin FastAPI routers. Obtain a session via `database.SessionFactory()`, instantiate repositories, call their methods, return response schemas.
- **Repositories** (`repositories/`) — each owns one table. Accept an `AsyncSession` in `__init__`. Contain all SQL logic. Never import FastAPI types.
- **Services** (`services/`) — long-running `asyncio.Task` workers (log tailing, transfer grouping, cleanup, node API polling, IP24). Each has `start()`/`stop()` lifecycle methods.
- **Models** (`models.py`) — SQLModel classes with `table=True`. Shared between repositories and routes.
- **Schemas** (`schemas.py`) — Pydantic models for request/response serialisation. Keep separate from table models.

### Application Lifecycle

Defined in `core/app.py` → `create_app()` → `lifespan`:

1. `init_database()` — creates tables, runs migrations sequentially.
2. Services start in order: LogMonitor → NodeApi → Cleanup → TransferGrouping → IP24.
3. On shutdown, services stop in the same order.

### Background Services

All services follow the same pattern:

- `_run()` loop with `while not self._stop_event.is_set()`
- Work inside `async with database.SessionFactory() as session:`
- Wait between cycles via `asyncio.wait_for(self._stop_event.wait(), timeout=…)`
- Outer `except Exception` catches unexpected errors and logs them; the loop continues.

## Database & Migrations

### Migration System

- `migrations.py` contains numbered migration functions: `_migrate_N_to_N+1(conn)`.
- Each takes a synchronous `Connection` (run inside `conn.run_sync`).
- Register in the `MIGRATIONS` tuple at the bottom of the file.
- `LATEST_SCHEMA_VERSION` must equal `len(MIGRATIONS)`.
- Migrations run at startup before any service starts.
- Use raw SQL via `conn.execute(text(...))` — SQLModel/ORM not available in sync context.

### SQLite Gotchas

- **DateTime storage**: SQLite stores datetimes as strings `'YYYY-MM-DD HH:MM:SS.ffffff'` (space separator, no timezone). Python's `.isoformat()` produces `'YYYY-MM-DDTHH:MM:SS+00:00'` which **breaks string comparisons**. When writing raw SQL with datetime comparisons, use the `_format_dt()` helper or `.strftime('%Y-%m-%d %H:%M:%S.%f')`.
- **No ALTER COLUMN**: Use the rebuild-table pattern (`_rebuild_table_with_capped_columns` in migrations.py) to change column types.
- **Concurrency**: SQLite allows one writer at a time. Multiple services share the same engine. `OperationalError` (database locked) and `StaleDataError` (row modified/deleted by another session) must both be caught in flush/commit handlers — roll back and retry on the next cycle.
- **Indexes**: Composite indexes are preferred over multiple single-column indexes when queries filter on multiple columns together.

## Transfer Grouping System

### Granularity & Promotion

Raw `Transfer` rows are aggregated into `TransferGrouped` rows at granularity=1 (1-minute buckets). Coarser granularities are built by promoting finer ones:

```
Transfer → TransferGrouped(gran=1) → gran=5 → gran=60
```

Promotion rules are defined in `TransferGroupedRepository.PROMOTION_RULES`.

### size_class='all' Rows

For granularities > 1, an additional `size_class='all'` row is emitted during promotion, summing across all per-size-class entries. This enables fast SQL-level aggregation for high-level dashboards without fetching individual size classes.

**Key invariant**: `list_for_granularity_before` (used by promotions) must exclude `size_class='all'` to prevent double-counting. The 'all' row is always re-computed from per-size-class data.

### SQL Aggregation

The `/api/transfer-grouped/intervals` and `/totals` endpoints use SQL `SUM() + GROUP BY` directly on the database rather than loading rows into Python. The repository methods `collect_interval_buckets()` and `collect_totals_by_source()` implement a cursor-advancement pattern across granularity tiers (60→5→1→raw transfers) to cover the requested time range with the coarsest available data.

## Error Handling in Services

When flushing/committing in background services, catch **both**:

```python
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.exc import StaleDataError

except (OperationalError, StaleDataError) as exc:
    logger.warning("flush/commit failed: %s", exc)
    await session.rollback()
    return  # retry next cycle
```

`StaleDataError` occurs when another service (e.g., Cleanup) deletes rows between SELECT and UPDATE in the same cycle.

## Testing Patterns

- Each test gets an **isolated SQLite database** via the `isolated_database` fixture in `conftest.py`.
- Tests use `httpx.AsyncClient` with `ASGITransport` to call the FastAPI app directly (no network).
- Standard pattern:
  ```python
  @pytest.mark.asyncio
  async def test_something():
      settings = Settings(database_url=..., sources=[...])
      app = create_app(settings)
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          response = await client.get("/api/...")
          assert response.status_code == 200
  ```
- Test data is inserted via repositories within `async with database.SessionFactory() as session:`.
- Performance/integration tests against the real database (`pokus.db`) should be decorated with `@pytest.mark.skipif` if the file is absent.

## Code Style

- **Line length**: 100 (Black).
- **Imports**: isort with `profile = "black"`.
- **Type annotations**: Always use; prefer `X | None` over `Optional[X]`.
- **Docstrings**: Required on public classes and functions.
- **Logging**: Use `from server.src.core.logging import get_logger; logger = get_logger(__name__)`. Never use `print()`.
- **Async**: All database operations must be async. Use `await session.execute(...)`, never sync equivalents.

## Adding a New Configuration Parameter

When adding a new repeatable CLI/env parameter (like `--source`, `--ip24`, `--disqual`):

1. **Dataclass** — add a frozen `@dataclass` in `config.py` for the parsed result (e.g., `SourceDefinition`, `DisqualDefinition`).
2. **Settings field** — add `field_name: str | List[str] = []` to the `Settings` class. The `str | List[str]` union prevents pydantic-settings from JSON-decoding simple comma-separated env strings.
3. **Coercion validator** — add a `@field_validator("field_name", mode="before")` that handles `None`, empty string, comma-separated, newline-separated, JSON array, and Python list/tuple/set inputs. Follow the `_coerce_sources` / `_coerce_ip24` pattern.
4. **Parsed property** — add a `@property` on `Settings` that parses the raw string list into the structured dataclass. Validate format and raise `ValueError` on invalid input.
5. **CLI argument** — add `parser.add_argument("--flag", dest="field_name", action="append", default=[], help="…")` in `cli.py`.
6. **Build settings override** — in `build_settings()`, add: `if getattr(args, "field_name", None): overrides["field_name"] = args.field_name`.
7. **Tests** — add coercion tests (comma, newline, list, JSON, empty, None) and parsing tests (valid, invalid, edge cases) in `server/tests/`.

The env var is automatically available as `MONSTR_FIELD_NAME` (upper-cased, `MONSTR_` prefix).

## Adding a New Feature Checklist

1. **Model** — add/modify SQLModel class in `models.py` if schema changes.
2. **Migration** — add `_migrate_N_to_N+1` in `migrations.py`, update `MIGRATIONS` tuple and `LATEST_SCHEMA_VERSION`.
3. **Repository** — add data-access methods in the appropriate repository class.
4. **Route** — add/modify FastAPI router in `api/routes/`, register in `core/app.py` if new.
5. **Schema** — add request/response models in `schemas.py` if needed.
6. **Tests** — add tests in `server/tests/`. Run: `python -m pytest -q server/tests`.
7. **README** — update if the feature is user-facing.

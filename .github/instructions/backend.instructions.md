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

## Log Parsing & External Data Formats

### Storj Node Logs

- **Location**: Parsed in `services/log_monitor.py`
- **Format**: Tab-separated: `TIMESTAMP\tLEVEL\tAREA\tACTION\tJSON_DETAILS`
- **JSON field names**: Storj changed from Title Case (`"Piece ID"`, `"Satellite ID"`) to snake_case (`"piece_id"`, `"satellite_id"`) around early 2026. **Support both formats** using the `_normalize_details()` helper.
- **Key parsing methods**:
  - `_process_piecestore_transfer()` — parses download/upload events
  - `_process_reputation_service()` — parses reputation score updates
- **Normalization**: The `_normalize_details()` static method converts new snake_case keys to legacy Title Case format internally, keeping the rest of the processing logic unchanged.
- **When modifying parsers**: Always add tests for both old and new formats. See `test_log_monitor.py` for examples.

**Field name mapping (new → old)**:

| snake_case (new)         | Title Case (old/canonical) |
| ------------------------ | -------------------------- |
| `piece_id`               | `Piece ID`                 |
| `satellite_id`           | `Satellite ID`             |
| `action`                 | `Action`                   |
| `size`                   | `Size`                     |
| `offset`                 | `Offset`                   |
| `remote_address`         | `Remote Address`           |
| `process`                | `Process`                  |
| `total_audits`           | `Total Audits`             |
| `successful_audits`      | `Successful Audits`        |
| `audit_score`            | `Audit Score`              |
| `online_score`           | `Online Score`             |
| `suspension_score`       | `Suspension Score`         |
| `audit_score_delta`      | `Audit Score Delta`        |
| `online_score_delta`     | `Online Score Delta`       |
| `suspension_score_delta` | `Suspension Score Delta`   |

### Storj Node API

- **Location**: Consumed in `services/node_api.py`
- **Format**: REST API returning camelCase JSON (`satelliteId`, `usageAtRest`, etc.)
- **Not affected by log format changes** — this is a separate data source with stable formatting
- **Endpoints polled**: `/api/sno/satellites`, `/api/sno/estimated-payout`, etc.

### Test Data Samples

- **Location**: `testdata/` directory in repo root
- **Files**: `blob.log-*`, `hash.log-*` — real Storj log samples (anonymized)
- **Usage**: Use these files to test parser changes and validate against realistic data
- **Format variations**: May contain both old and new format logs; parser must handle both

## Common Modification Patterns

### Supporting Multiple Versions of External Formats

When external data sources (logs, APIs) change format:

1. **Add a normalization layer** — Create a helper method (e.g., `_normalize_details()`) that converts all format variations to a canonical format.
2. **Keep existing logic using canonical format** — Minimize the diff by normalizing input early, then keeping all downstream processing unchanged.
3. **Test both old and new formats separately** — Add dedicated tests for each format version to ensure backward compatibility.
4. **Document the format change** — Add comments explaining what changed and when, plus update the instruction files.
5. **Use fast-path optimization** — Check if normalization is needed before doing expensive transformations.

**Example pattern** (from `log_monitor.py`):

```python
# Module-level mapping constant
_SNAKE_TO_TITLE = {
    "piece_id": "Piece ID",
    "satellite_id": "Satellite ID",
    # ... more mappings
}

@staticmethod
def _normalize_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize snake_case to Title Case for backward compatibility."""
    # Fast path: skip if no snake_case keys present
    if not any(key in details for key in _SNAKE_TO_TITLE):
        return details

    # Remap snake_case keys
    normalized = {}
    for key, value in details.items():
        normalized_key = _SNAKE_TO_TITLE.get(key, key)
        normalized[normalized_key] = value
    return normalized

# Use in processing methods
def _process_something(self, payload: Dict[str, Any]):
    details_raw = payload.get("details") or {}
    details = self._normalize_details(details_raw)  # ← normalize once
    # Rest of method uses canonical format unchanged
    piece_id = details.get("Piece ID")
    ...
```

### Adding New Log Event Types

1. **Identify the area:action** — check raw logs for the exact `AREA` and `ACTION` values
2. **Add to `_process_payload()` dispatcher** — route to appropriate handler method
3. **Create handler method** — follow naming pattern `_process_{area}_{action}_payload()`
4. **Return appropriate tuple** — `(log_payload, transfer_payload, reputation_payload)` with `None` for unused
5. **Add tests** — minimal test in `test_log_monitor.py` checking the event is not marked as unprocessed

### Adding Period-Based Aggregation Endpoints

Several tables use a `period` column (`yyyy-mm-dd` ISO date string) as a grouping key (e.g., `SatelliteUsage`, `DiskUsage`, `Paystub`). When adding POST endpoints that return data grouped by period:

1. **Repository** — accept `start_period: str` for filtering (`WHERE period >= start_period`). Prefer simple string comparison over subqueries for distinct periods. See `SatelliteUsageRepository.list_from_period()`, `DiskUsageRepository.list_between_periods()`.
2. **Route** — convert user-friendly parameters (like `numberOfPeriods: int`) to a `start_period` string: `(datetime.now(timezone.utc).date() - timedelta(days=N)).isoformat()`. Keep the conversion in the route, not the repository.
3. **Grouping** — build `dict[str, list[SchemaRead]]` using `setdefault()`:
   ```python
   periods: dict[str, list[SomeRead]] = {}
   for record in records:
       bucket = periods.setdefault(record.period, [])
       bucket.append(SomeRead.model_validate(record))
   ```
4. **Request schema** — follow the standard pattern: `nodes: list[str]` (empty = all) plus a time parameter with camelCase alias. Deduplicate nodes in the route via `list(dict.fromkeys(payload.nodes))`.
5. **Period format** — `date.isoformat()` produces `yyyy-mm-dd`, matching the DB storage format. String comparisons (`>=`, `<=`) sort correctly.

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
- **Test file naming**: `test_<module_name>.py` mirrors source structure (`services/log_monitor.py` → `tests/test_log_monitor.py`)
- **Run full suite after changes**: `python -m pytest -q server/tests` (from repo root)
- **Date-relative test data**: When testing endpoints that compute time boundaries from "now" (e.g., `today - numberOfPeriods`), use `date.today() - timedelta(days=N)` for test record periods instead of hardcoded dates. Hardcoded historical dates will fall outside the query window and produce empty results.

### Parser Testing Best Practices

When modifying parsing logic (`log_monitor`, format normalization, etc.):

- **Test both valid and invalid inputs** — ensure errors are handled gracefully
- **Test edge cases** — missing fields, wrong types, empty strings, null values
- **For external formats that may change**: Test multiple format versions separately (old vs. new)
- **Add unit tests for normalization helpers** — test pass-through and transformation cases
- **Integration tests use realistic sample data** — use snippets from `testdata/` logs when possible
- **Verify unprocessed handling** — check that malformed data is properly logged to unprocessed files

**Example test structure** for format variations:

```python
@pytest.mark.asyncio
async def test_parser_old_format(tmp_path):
    # Test with Title Case keys
    details = json.dumps({"Piece ID": "ABC", "Size": 256})
    raw_line = f"2025-10-25T12:00:00Z\tINFO\tpiecestore\tdownloaded\t{details}\n"
    # ... assertions

@pytest.mark.asyncio
async def test_parser_new_format(tmp_path):
    # Test with snake_case keys
    details = json.dumps({"piece_id": "ABC", "size": 256})
    raw_line = f"2025-10-25T12:00:00Z\tINFO\tpiecestore\tdownloaded\t{details}\n"
    # ... assertions (should produce identical output)

def test_normalizer_passthrough():
    # Unit test: old format unchanged
    old_format = {"Piece ID": "ABC"}
    assert normalize(old_format) == old_format

def test_normalizer_remaps_snake_case():
    # Unit test: new format remapped
    new_format = {"piece_id": "ABC"}
    expected = {"Piece ID": "ABC"}
    assert normalize(new_format) == expected
```

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

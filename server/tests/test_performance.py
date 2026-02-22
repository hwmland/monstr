"""Performance test comparing old (row-level) vs new (SQL-aggregated) interval queries.

Requires `data/pokus.db` to be present.  Skipped automatically when absent.
"""
from __future__ import annotations

import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from server.src import database
from server.src.config import Settings
from server.src.migrations import apply_migrations
from server.src.repositories.transfer_grouped import TransferGroupedRepository

POKUS_DB = Path(__file__).resolve().parents[2] / "data" / "pokus.db"

skip_no_pokus = pytest.mark.skipif(
    not POKUS_DB.exists(),
    reason="pokus.db not found — skipping performance test",
)


def _setup_db(tmp_path: Path) -> Settings:
    """Copy pokus.db to a temp location and configure the async engine."""
    tmp_db = tmp_path / "pokus_test.db"
    shutil.copy2(POKUS_DB, tmp_db)
    url = f"sqlite+aiosqlite:///{tmp_db}"
    settings = Settings(database_url=url, sources=[])
    database.configure_database(settings)
    return settings


@skip_no_pokus
@pytest.mark.asyncio
async def test_intervals_old_vs_new(tmp_path: Path) -> None:
    """Compare collect_interval_rows (old) with collect_interval_buckets (new).

    Both should produce equivalent totals for 30 × 3-day buckets.
    The new method should be significantly faster.
    """
    settings = _setup_db(tmp_path)
    await database.init_database(settings)

    # 30 intervals of 3 days from a known point in the DB
    # The DB has data from ~2025-11-16 to 2026-02-22
    end = datetime(2026, 2, 22, 8, 0, 0, tzinfo=timezone.utc)
    interval = timedelta(days=3)
    bucket_seconds = int(interval.total_seconds())
    n_intervals = 30
    start = end - interval * (n_intervals - 1)

    async with database.SessionFactory() as session:
        repo = TransferGroupedRepository(session)

        # --- OLD approach: collect_interval_rows ---
        t0 = time.perf_counter()
        old_rows = await repo.collect_interval_rows(None, start, end)
        old_elapsed_ms = (time.perf_counter() - t0) * 1000

        # Aggregate old rows into buckets (same logic as the old route handler)
        old_buckets: dict[int, dict[str, int]] = {}
        for r in old_rows:
            ts = r.interval_start
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            bucket_ts = (int(ts.timestamp()) // bucket_seconds) * bucket_seconds
            if bucket_ts not in old_buckets:
                old_buckets[bucket_ts] = {k: 0 for k in repo.METRIC_COLUMNS}
            for k in repo.METRIC_COLUMNS:
                old_buckets[bucket_ts][k] += int(getattr(r, k, 0) or 0)

        # --- NEW approach: collect_interval_buckets ---
        t0 = time.perf_counter()
        new_buckets, _ = await repo.collect_interval_buckets(None, start, end, bucket_seconds)
        new_elapsed_ms = (time.perf_counter() - t0) * 1000

    # Report timings
    print(f"\nOLD collect_interval_rows: {old_elapsed_ms:.0f}ms, {len(old_rows)} rows")
    print(f"NEW collect_interval_buckets: {new_elapsed_ms:.0f}ms, {len(new_buckets)} buckets")
    speedup = old_elapsed_ms / new_elapsed_ms if new_elapsed_ms > 0 else float("inf")
    print(f"Speedup: {speedup:.1f}x")

    # Verify equivalence: every old bucket must match the new bucket
    all_bucket_keys = set(old_buckets.keys()) | set(new_buckets.keys())
    mismatches = []
    for bk in sorted(all_bucket_keys):
        old_vals = old_buckets.get(bk, {k: 0 for k in repo.METRIC_COLUMNS})
        new_vals = new_buckets.get(bk, {k: 0 for k in repo.METRIC_COLUMNS})
        for metric in repo.METRIC_COLUMNS:
            ov = old_vals.get(metric, 0)
            nv = new_vals.get(metric, 0)
            if ov != nv:
                mismatches.append((bk, metric, ov, nv))

    if mismatches:
        for bk, metric, ov, nv in mismatches[:20]:
            dt = datetime.fromtimestamp(bk, tz=timezone.utc)
            print(f"  MISMATCH bucket={dt} metric={metric}: old={ov} new={nv}")
        pytest.fail(f"{len(mismatches)} metric mismatches between old and new")

    # The new approach should be faster
    assert new_elapsed_ms < old_elapsed_ms, (
        f"New approach ({new_elapsed_ms:.0f}ms) was not faster than old ({old_elapsed_ms:.0f}ms)"
    )


@skip_no_pokus
@pytest.mark.asyncio
async def test_totals_old_vs_new(tmp_path: Path) -> None:
    """Compare per-source totals from old row-level vs new SQL aggregation."""
    settings = _setup_db(tmp_path)
    await database.init_database(settings)

    end = datetime(2026, 2, 22, 8, 0, 0, tzinfo=timezone.utc)
    start = end - timedelta(days=90)

    async with database.SessionFactory() as session:
        repo = TransferGroupedRepository(session)

        # --- OLD approach ---
        t0 = time.perf_counter()
        old_rows = await repo.collect_interval_rows(None, start, end)
        old_elapsed_ms = (time.perf_counter() - t0) * 1000

        old_totals: dict[str, dict[str, int]] = {}
        for r in old_rows:
            src = r.source or ""
            if src not in old_totals:
                old_totals[src] = {k: 0 for k in repo.METRIC_COLUMNS}
            for k in repo.METRIC_COLUMNS:
                old_totals[src][k] += int(getattr(r, k, 0) or 0)

        # --- NEW approach ---
        t0 = time.perf_counter()
        new_totals = await repo.collect_totals_by_source(None, start, end)
        new_elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"\nOLD totals: {old_elapsed_ms:.0f}ms, {len(old_rows)} rows -> {len(old_totals)} sources")
    print(f"NEW totals: {new_elapsed_ms:.0f}ms, {len(new_totals)} sources")
    speedup = old_elapsed_ms / new_elapsed_ms if new_elapsed_ms > 0 else float("inf")
    print(f"Speedup: {speedup:.1f}x")

    # Verify equivalence
    all_sources = set(old_totals.keys()) | set(new_totals.keys())
    mismatches = []
    for src in sorted(all_sources):
        old_vals = old_totals.get(src, {k: 0 for k in repo.METRIC_COLUMNS})
        new_vals = new_totals.get(src, {k: 0 for k in repo.METRIC_COLUMNS})
        for metric in repo.METRIC_COLUMNS:
            ov = old_vals.get(metric, 0)
            nv = new_vals.get(metric, 0)
            if ov != nv:
                mismatches.append((src, metric, ov, nv))

    if mismatches:
        for src, metric, ov, nv in mismatches[:20]:
            print(f"  MISMATCH source={src} metric={metric}: old={ov} new={nv}")
        pytest.fail(f"{len(mismatches)} metric mismatches between old and new")

    assert new_elapsed_ms < old_elapsed_ms, (
        f"New approach ({new_elapsed_ms:.0f}ms) was not faster than old ({old_elapsed_ms:.0f}ms)"
    )

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...models import HashstoreCompaction
from ...repositories.hashstore_compaction import HashstoreCompactionRepository
from ...schemas import (
    ActiveCompactionEntry,
    HashstoreCompactionBucket,
    HashstoreCompactionFilters,
    HashstoreCompactionRead,
    HashstoreCompactionSeriesRequest,
    HashstoreCompactionSeriesResponse,
)
from ...services.log_monitor import LogMonitorService

router = APIRouter(prefix="/api/hashstore-compaction", tags=["hashstore-compaction"])


# (time_range -> (total_days, bucket_days))
_RANGE_SPEC: dict[str, tuple[int, int]] = {
    "30d": (30, 1),
    "90d": (90, 3),
    "1y": (370, 10),    # 37 buckets of 10 days
    "5y": (1850, 50),   # 37 buckets of 50 days
}


@router.get("", response_model=List[HashstoreCompactionRead], tags=["raw"])
async def list_hashstore_compactions(
    source: Optional[str] = Query(default=None, description="Filter by node/source name"),
    satellite_id: Optional[str] = Query(default=None, alias="satelliteId", description="Filter by satellite"),
    store: Optional[str] = Query(default=None, description="Filter by store (s0, s1)"),
    since: Optional[datetime] = Query(default=None, description="Records after this timestamp"),
    until: Optional[datetime] = Query(default=None, description="Records before this timestamp"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum records to return"),
    session: AsyncSession = Depends(get_session),
) -> List[HashstoreCompactionRead]:
    """List hashstore compaction records with optional filtering."""
    repository = HashstoreCompactionRepository(session)
    records = await repository.list(
        source=source,
        satellite_id=satellite_id,
        store=store,
        since=since,
        until=until,
        limit=limit,
    )
    return [HashstoreCompactionRead.model_validate(record) for record in records]


def _get_log_monitor(request: Request) -> LogMonitorService | None:
    service = getattr(request.app.state, "log_monitor", None)
    if isinstance(service, LogMonitorService):
        return service
    return None


@router.get("/active", response_model=Dict[str, List[ActiveCompactionEntry]])
async def list_active_compactions(request: Request) -> Dict[str, List[ActiveCompactionEntry]]:
    """Return the compactions currently in progress, grouped by node name.

    The state is held in memory by the log monitor, so compactions that started before
    the server was launched are not reported.
    """
    service = _get_log_monitor(request)
    if service is None:
        return {}

    grouped: Dict[str, List[ActiveCompactionEntry]] = {}
    for accumulator in service.active_compactions():
        if accumulator.started_at is None:
            continue
        grouped.setdefault(accumulator.source, []).append(
            ActiveCompactionEntry(
                satellite_id=accumulator.satellite_id,
                store=accumulator.store,
                started_at=accumulator.started_at,
            )
        )
    return grouped


def _empty_bucket(bucket_start: datetime) -> dict:
    return {
        "bucket_start": bucket_start,
        "num_logs": 0, "len_logs": 0,
        "set_percent": 0.0, "trash_percent": 0.0, "ttl_percent": 0.0,
        "data_reclaimable": 0, "free_required": 0, "compactions_total": 0,
        "num_set": 0, "len_set": 0, "avg_set": 0.0,
        "num_trash": 0, "len_trash": 0, "num_ttl": 0, "len_ttl": 0,
        "table_load": 0.0, "table_size": 0, "num_slots": 0,
        "passes": 0, "duration_ms": 0, "duration_max_ms": 0, "duration_median_ms": 0,
        "records_rewritten": 0, "bytes_rewritten": 0,
        "records_trashed": 0, "bytes_trashed": 0,
        "records_expired": 0, "bytes_expired": 0,
        "records_restored": 0, "bytes_restored": 0,
        "logs_reclaimed": 0, "bytes_reclaimed": 0,
        "event_count": 0,
    }


def _accumulate(bucket: dict, ev: HashstoreCompaction) -> None:
    # Snapshot fields — sum across all events in the bucket.
    bucket["num_logs"] += ev.num_logs
    bucket["len_logs"] += ev.len_logs
    bucket["data_reclaimable"] += ev.data_reclaimable
    bucket["free_required"] += ev.free_required
    bucket["compactions_total"] += ev.compactions_total
    bucket["num_set"] += ev.num_set
    bucket["len_set"] += ev.len_set
    bucket["num_trash"] += ev.num_trash
    bucket["len_trash"] += ev.len_trash
    bucket["num_ttl"] += ev.num_ttl
    bucket["len_ttl"] += ev.len_ttl
    bucket["table_size"] += ev.table_size
    bucket["num_slots"] += ev.num_slots

    # Ratios — accumulate for averaging after the loop.
    bucket["set_percent"] += ev.set_percent
    bucket["trash_percent"] += ev.trash_percent
    bucket["ttl_percent"] += ev.ttl_percent
    bucket["table_load"] += ev.table_load
    bucket["avg_set"] += ev.avg_set

    # Deltas — sum within bucket.
    bucket["passes"] += ev.passes
    bucket["duration_ms"] += ev.duration_ms
    bucket["duration_max_ms"] = max(bucket["duration_max_ms"], ev.duration_ms)
    bucket.setdefault("_durations", []).append(ev.duration_ms)
    bucket["records_rewritten"] += ev.records_rewritten
    bucket["bytes_rewritten"] += ev.bytes_rewritten
    bucket["records_trashed"] += ev.records_trashed
    bucket["bytes_trashed"] += ev.bytes_trashed
    bucket["records_expired"] += ev.records_expired
    bucket["bytes_expired"] += ev.bytes_expired
    bucket["records_restored"] += ev.records_restored
    bucket["bytes_restored"] += ev.bytes_restored
    bucket["logs_reclaimed"] += ev.logs_reclaimed
    bucket["bytes_reclaimed"] += ev.bytes_reclaimed

    bucket["event_count"] += 1


@router.post("/series", response_model=HashstoreCompactionSeriesResponse)
async def hashstore_series(
    payload: HashstoreCompactionSeriesRequest,
    session: AsyncSession = Depends(get_session),
) -> HashstoreCompactionSeriesResponse:
    """Return bucketed compaction metrics for the dashboard panel.

    Buckets are anchored to the start of the requested window. Snapshot
    fields use the latest event within each bucket; delta fields are summed.
    """
    total_days, bucket_days = _RANGE_SPEC[payload.time_range]
    bucket_seconds = bucket_days * 86400

    # End is the start of the day AFTER today (UTC), so today's events are
    # included in the last bucket.
    now = datetime.now(timezone.utc)
    end_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
    # Align end to a bucket boundary by setting start = end - total_days.
    start_dt = end_day - timedelta(days=total_days)
    end_dt = end_day
    bucket_count = total_days // bucket_days

    nodes_filter = list(dict.fromkeys(payload.nodes)) if payload.nodes else None

    repository = HashstoreCompactionRepository(session)
    events = await repository.list_range(
        since=start_dt,
        until=end_dt,
        sources=nodes_filter,
        satellite_id=payload.satellite_id,
        store=payload.store,
    )

    # Single flat bucket list — all matching events aggregated together.
    buckets = [
        _empty_bucket(start_dt + timedelta(seconds=i * bucket_seconds))
        for i in range(bucket_count)
    ]

    for ev in events:
        ev_ts = ev.timestamp
        if ev_ts.tzinfo is None:
            ev_ts = ev_ts.replace(tzinfo=timezone.utc)
        offset = int((ev_ts - start_dt).total_seconds())
        idx = offset // bucket_seconds
        if idx < 0 or idx >= bucket_count:
            continue
        _accumulate(buckets[idx], ev)

    # Compute median duration and average ratio fields.
    for b in buckets:
        durations = b.pop("_durations", [])
        b["duration_median_ms"] = int(median(durations)) if durations else 0
        n = b["event_count"]
        if n > 0:
            b["set_percent"] /= n
            b["trash_percent"] /= n
            b["ttl_percent"] /= n
            b["table_load"] /= n
            b["avg_set"] /= n

    return HashstoreCompactionSeriesResponse(
        start_time=start_dt,
        end_time=end_dt,
        bucket_seconds=bucket_seconds,
        buckets=[HashstoreCompactionBucket(**b) for b in buckets],
    )


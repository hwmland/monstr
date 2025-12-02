from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.transfer_grouped import TransferGroupedRepository
from ...schemas import TransferGroupedFilters, TransferGroupedRead
from ...schemas import DataDistributionRequest, DataDistributionResponse, DataDistributionItem
from ...schemas import IntervalTransferResponse, IntervalTransferBucket
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from ...schemas import IntervalTransfersRequest, TransferTotalsRequest, TransferTotalsResponse, TransferTotalsNode

router = APIRouter(prefix="/api/transfer-grouped", tags=["transfer-grouped"])


@router.get("", response_model=list[TransferGroupedRead], tags=["raw"])
async def list_transfer_grouped(
    filters: TransferGroupedFilters = Depends(),
    size_class_param: str | None = Query(default=None, alias="sizeClass"),
    session: AsyncSession = Depends(get_session),
) -> Sequence[TransferGroupedRead]:
    """Return grouped transport aggregates for the requested filters."""
    if size_class_param is not None:
        filters.size_class = size_class_param
    repository = TransferGroupedRepository(session)
    records = await repository.list(filters)
    return [TransferGroupedRead.model_validate(record) for record in records]


@router.post("/data-distribution", response_model=DataDistributionResponse)
async def data_distribution(
    payload: DataDistributionRequest,
    session: AsyncSession = Depends(get_session),
) -> DataDistributionResponse:
    """Return data size distribution per size_class over the last hour at 1-minute granularity."""
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    repository = TransferGroupedRepository(session)
    rows = await repository.list_for_sources_between(payload.nodes or None, one_hour_ago, now, granularity=1)

    if not rows:
        return DataDistributionResponse(start_time=one_hour_ago, end_time=now, distribution=[])

    # Aggregate per size_class preserving all counters separately
    buckets: dict[str, dict[str, int]] = {}
    min_start = None
    for r in rows:
        sc = r.size_class
        if sc not in buckets:
            buckets[sc] = {
                'size_dl_succ_nor': 0,
                'size_ul_succ_nor': 0,
                'size_dl_fail_nor': 0,
                'size_ul_fail_nor': 0,
                'size_dl_succ_rep': 0,
                'size_ul_succ_rep': 0,
                'size_dl_fail_rep': 0,
                'size_ul_fail_rep': 0,
                'count_dl_succ_nor': 0,
                'count_ul_succ_nor': 0,
                'count_dl_fail_nor': 0,
                'count_ul_fail_nor': 0,
                'count_dl_succ_rep': 0,
                'count_ul_succ_rep': 0,
                'count_dl_fail_rep': 0,
                'count_ul_fail_rep': 0,
            }
        b = buckets[sc]
        b['size_dl_succ_nor'] += int(r.size_dl_succ_nor or 0)
        b['size_ul_succ_nor'] += int(r.size_ul_succ_nor or 0)
        b['size_dl_fail_nor'] += int(r.size_dl_fail_nor or 0)
        b['size_ul_fail_nor'] += int(r.size_ul_fail_nor or 0)
        b['size_dl_succ_rep'] += int(r.size_dl_succ_rep or 0)
        b['size_ul_succ_rep'] += int(r.size_ul_succ_rep or 0)
        b['size_dl_fail_rep'] += int(r.size_dl_fail_rep or 0)
        b['size_ul_fail_rep'] += int(r.size_ul_fail_rep or 0)

        b['count_dl_succ_nor'] += int(r.count_dl_succ_nor or 0)
        b['count_ul_succ_nor'] += int(r.count_ul_succ_nor or 0)
        b['count_dl_fail_nor'] += int(r.count_dl_fail_nor or 0)
        b['count_ul_fail_nor'] += int(r.count_ul_fail_nor or 0)
        b['count_dl_succ_rep'] += int(r.count_dl_succ_rep or 0)
        b['count_ul_succ_rep'] += int(r.count_ul_succ_rep or 0)
        b['count_dl_fail_rep'] += int(r.count_dl_fail_rep or 0)
        b['count_ul_fail_rep'] += int(r.count_ul_fail_rep or 0)

        if min_start is None or r.interval_start < min_start:
            min_start = r.interval_start

    distribution = [
        DataDistributionItem(size_class=sc, **vals) for sc, vals in sorted(buckets.items())
    ]

    # Ensure the start_time we return is timezone-aware UTC
    start_time = min_start or one_hour_ago
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    else:
        start_time = start_time.astimezone(timezone.utc)

    return DataDistributionResponse(start_time=start_time, end_time=now, distribution=distribution)


def parse_interval_length(spec: str) -> timedelta:
    """Parse interval length strings like '10s', '2m', '10m', '1h', '1d' into timedelta."""
    spec = spec.strip().lower()
    if spec.endswith('s'):
        return timedelta(seconds=int(spec[:-1]))
    if spec.endswith('m'):
        return timedelta(minutes=int(spec[:-1]))
    if spec.endswith('h'):
        return timedelta(hours=int(spec[:-1]))
    if spec.endswith('d'):
        return timedelta(days=int(spec[:-1]))
    # fallback: try integer seconds
    return timedelta(seconds=int(spec))


def round_down_to_interval(dt: datetime, interval: timedelta) -> datetime:
    """Round down a timezone-aware datetime to the nearest interval boundary (interval starting point)."""
    # ensure timezone-aware UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    total_seconds = int(dt.timestamp())
    interval_seconds = int(interval.total_seconds())
    bucket_start_ts = (total_seconds // interval_seconds) * interval_seconds
    return datetime.fromtimestamp(bucket_start_ts, tz=timezone.utc)


@router.post("/totals", response_model=TransferTotalsResponse)
async def transfer_totals(
    payload: TransferTotalsRequest,
    session: AsyncSession = Depends(get_session),
) -> TransferTotalsResponse:
    interval_delta = parse_interval_length(payload.interval)
    now = datetime.now(timezone.utc)
    start = now - interval_delta

    repository = TransferGroupedRepository(session)
    rows = await repository.collect_interval_rows(payload.nodes or None, start, now)

    metric_fields = (
        "size_dl_succ_nor",
        "size_ul_succ_nor",
        "size_dl_fail_nor",
        "size_ul_fail_nor",
        "size_dl_succ_rep",
        "size_ul_succ_rep",
        "size_dl_fail_rep",
        "size_ul_fail_rep",
        "count_dl_succ_nor",
        "count_ul_succ_nor",
        "count_dl_fail_nor",
        "count_ul_fail_nor",
        "count_dl_succ_rep",
        "count_ul_succ_rep",
        "count_dl_fail_rep",
        "count_ul_fail_rep",
    )

    totals: dict[str, dict[str, int]] = {}

    for row in rows:
        node = row.source or ""
        if node not in totals:
            totals[node] = {field: 0 for field in metric_fields}
        node_totals = totals[node]
        for field in metric_fields:
            node_totals[field] += int(getattr(row, field, 0) or 0)

    response_totals = {
        node: TransferTotalsNode(**values)
        for node, values in totals.items()
        if node
    }

    return TransferTotalsResponse(
        interval_seconds=int(interval_delta.total_seconds()),
        totals=response_totals,
    )


@router.post("/intervals", response_model=IntervalTransferResponse)
async def interval_transfers(
    payload: IntervalTransfersRequest,
    session: AsyncSession = Depends(get_session),
) -> IntervalTransferResponse:
    """Return transfer aggregates bucketed into arbitrary interval lengths.

    This mirrors the hourly endpoint but uses the requested interval length and number of intervals.
    The same algorithm is used: read granularity=5 from start_time, then granularity=1 from gran5_end,
    then raw Transfer rows since gran1_end. Bucket all rows by interval_length boundaries and sum counters.
    The response reuses IntervalTransferResponse/IntervalTransferBucket models (bucketStart/bucketEnd and counters).
    """
    now = datetime.now(timezone.utc)

    interval = parse_interval_length(payload.interval_length)

    # compute nominal start and round down to interval boundary
    intervals = payload.number_of_intervals - 1 # because of rounding down I need to decrease number or intervals.
    nominal_start = now - (interval * intervals)
    rounded_start = round_down_to_interval(nominal_start, interval)

    repository = TransferGroupedRepository(session)

    all_rows = await repository.collect_interval_rows(payload.nodes or None, rounded_start, now)

    # Prepare buckets (start from rounded_start up to now), bucket boundaries are interval-sized
    buckets: dict[datetime, dict[str, int]] = {}

    # helper to get bucket start for a datetime given interval
    def bucket_start_for_interval(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return round_down_to_interval(dt, interval)

    # Initialize buckets for each interval boundary from rounded_start up to now
    cur = rounded_start
    while cur < now:
        buckets[cur] = {
            'size_dl_succ_nor': 0,
            'size_ul_succ_nor': 0,
            'size_dl_fail_nor': 0,
            'size_ul_fail_nor': 0,
            'size_dl_succ_rep': 0,
            'size_ul_succ_rep': 0,
            'size_dl_fail_rep': 0,
            'size_ul_fail_rep': 0,
            'count_dl_succ_nor': 0,
            'count_ul_succ_nor': 0,
            'count_dl_fail_nor': 0,
            'count_ul_fail_nor': 0,
            'count_dl_succ_rep': 0,
            'count_ul_succ_rep': 0,
            'count_dl_fail_rep': 0,
            'count_ul_fail_rep': 0,
        }
        cur = cur + interval

    # Aggregate rows into buckets by their interval_start
    for r in all_rows:
        bs = bucket_start_for_interval(r.interval_start)
        if bs < rounded_start:
            continue
        if bs not in buckets:
            # allow rows that are exactly at 'now' to be clipped into last bucket
            prev_bs = round_down_to_interval(r.interval_start - interval, interval)
            if prev_bs in buckets:
                bs = prev_bs
            else:
                continue

        b = buckets[bs]
        b['size_dl_succ_nor'] += int(r.size_dl_succ_nor or 0)
        b['size_ul_succ_nor'] += int(r.size_ul_succ_nor or 0)
        b['size_dl_fail_nor'] += int(r.size_dl_fail_nor or 0)
        b['size_ul_fail_nor'] += int(r.size_ul_fail_nor or 0)
        b['size_dl_succ_rep'] += int(r.size_dl_succ_rep or 0)
        b['size_ul_succ_rep'] += int(r.size_ul_succ_rep or 0)
        b['size_dl_fail_rep'] += int(r.size_dl_fail_rep or 0)
        b['size_ul_fail_rep'] += int(r.size_ul_fail_rep or 0)

        b['count_dl_succ_nor'] += int(r.count_dl_succ_nor or 0)
        b['count_ul_succ_nor'] += int(r.count_ul_succ_nor or 0)
        b['count_dl_fail_nor'] += int(r.count_dl_fail_nor or 0)
        b['count_ul_fail_nor'] += int(r.count_ul_fail_nor or 0)
        b['count_dl_succ_rep'] += int(r.count_dl_succ_rep or 0)
        b['count_ul_succ_rep'] += int(r.count_ul_succ_rep or 0)
        b['count_dl_fail_rep'] += int(r.count_dl_fail_rep or 0)
        b['count_ul_fail_rep'] += int(r.count_ul_fail_rep or 0)

    # Build response buckets list in ascending order
    bucket_items: list[IntervalTransferBucket] = []
    sorted_starts = sorted(buckets.keys())
    for i, start in enumerate(sorted_starts):
        end = start + interval
        # Clip last bucket end to now
        if end > now:
            end = now
        vals = buckets[start]
        bucket_items.append(
            IntervalTransferBucket(
                bucket_start=start,
                bucket_end=end,
                **vals,
            )
        )

    resp_start = rounded_start
    resp_end = now

    return IntervalTransferResponse(start_time=resp_start, end_time=resp_end, buckets=bucket_items)

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
    totals = await repository.collect_totals_by_source(payload.nodes or None, start, now)

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

    Uses SQL-side SUM + GROUP BY to push aggregation to the database,
    returning only the bucketed results instead of individual rows.
    """
    now = datetime.now(timezone.utc)

    interval = parse_interval_length(payload.interval_length)
    bucket_seconds = int(interval.total_seconds())

    # compute nominal start and round down to interval boundary
    intervals = payload.number_of_intervals - 1 # because of rounding down I need to decrease number or intervals.
    nominal_start = now - (interval * intervals)
    rounded_start = round_down_to_interval(nominal_start, interval)

    repository = TransferGroupedRepository(session)

    raw_buckets, _ = await repository.collect_interval_buckets(
        payload.nodes or None, rounded_start, now, bucket_seconds,
    )

    # Build response buckets aligned to interval boundaries
    bucket_items: list[IntervalTransferBucket] = []
    cur = rounded_start
    while cur < now:
        bucket_ts = int(cur.timestamp())
        vals = raw_buckets.get(bucket_ts, {})
        end = cur + interval
        if end > now:
            end = now
        bucket_items.append(
            IntervalTransferBucket(
                bucket_start=cur,
                bucket_end=end,
                **{k: vals.get(k, 0) for k in (
                    'size_dl_succ_nor', 'size_ul_succ_nor',
                    'size_dl_fail_nor', 'size_ul_fail_nor',
                    'size_dl_succ_rep', 'size_ul_succ_rep',
                    'size_dl_fail_rep', 'size_ul_fail_rep',
                    'count_dl_succ_nor', 'count_ul_succ_nor',
                    'count_dl_fail_nor', 'count_ul_fail_nor',
                    'count_dl_succ_rep', 'count_ul_succ_rep',
                    'count_dl_fail_rep', 'count_ul_fail_rep',
                )},
            )
        )
        cur = cur + interval

    return IntervalTransferResponse(
        start_time=rounded_start, end_time=now, buckets=bucket_items,
    )

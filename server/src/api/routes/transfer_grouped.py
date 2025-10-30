from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.transfer_grouped import TransferGroupedRepository
from ...schemas import TransferGroupedFilters, TransferGroupedRead
from ...schemas import DataDistributionRequest, DataDistributionResponse, DataDistributionItem
from ...schemas import HourlyTransfersRequest, HourlyTransfersResponse, HourlyTransferBucket
from datetime import datetime, timezone, timedelta
from ...models import TransferGrouped
from sqlalchemy import select, func

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


@router.post("/hourly", response_model=HourlyTransfersResponse)
async def hourly_transfers(
    payload: HourlyTransfersRequest,
    session: AsyncSession = Depends(get_session),
) -> HourlyTransfersResponse:
    """Return hourly summed transfer metrics over the last N hours.

    Algorithm:
    - Compute start_time = now - hours, rounded up to the next full hour (so buckets align to hour boundaries)
    - Read granularity=5 records with interval_start >= start_time
    - Find maximum interval_end among those records -> granularity5_end
    - Read granularity=1 records with interval_start >= granularity5_end
    - Combine both sets, bucket by full hours (e.g., 13:00-14:00), sum all size and count fields per bucket
    - Clip the endtime of the last bucket to now
    - Return list of hourly buckets with bucketStart/bucketEnd and summed counters
    """
    now = datetime.now(timezone.utc)

    # compute nominal start and round up to full hour
    nominal_start = now - timedelta(hours=payload.hours)
    # round up to next hour boundary if not already exact
    if nominal_start.minute != 0 or nominal_start.second != 0 or nominal_start.microsecond != 0:
        rounded_start = (nominal_start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    else:
        rounded_start = nominal_start.replace(minute=0, second=0, microsecond=0)

    repository = TransferGroupedRepository(session)

    # Read granularity=5 records with interval_start >= rounded_start
    gran5_rows = await repository.list_for_sources_between(payload.nodes or None, rounded_start, now, granularity=5)

    # Find maximum interval_end among granularity=5 rows
    gran5_end: datetime | None = None
    for r in gran5_rows:
        if gran5_end is None or r.interval_end > gran5_end:
            gran5_end = r.interval_end

    # If no gran5 rows, gran5_end equals rounded_start
    if gran5_end is None:
        gran5_end = rounded_start

    # Ensure gran5_end is timezone-aware UTC
    if gran5_end.tzinfo is None:
        gran5_end = gran5_end.replace(tzinfo=timezone.utc)
    else:
        gran5_end = gran5_end.astimezone(timezone.utc)

    # Read granularity=1 records with interval_start >= gran5_end
    gran1_rows = await repository.list_for_sources_between(payload.nodes or None, gran5_end, now, granularity=1)

    # Combine both lists
    all_rows = list(gran5_rows) + list(gran1_rows)

    # Prepare hourly buckets (start from rounded_start up to now), bucket boundaries are full hours
    buckets: dict[datetime, dict[str, int]] = {}
    # helper to get bucket start for a datetime
    def bucket_start_for(dt: datetime) -> datetime:
        # normalize to UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.replace(minute=0, second=0, microsecond=0)

    # Initialize buckets for each hour boundary from rounded_start up to now
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
        cur = cur + timedelta(hours=1)

    # Aggregate rows into buckets by their interval_start
    for r in all_rows:
        bs = bucket_start_for(r.interval_start)
        if bs < rounded_start:
            # ignore older records
            continue
        # If bucket missing (possible if interval_start is after now), skip
        if bs not in buckets:
            # allow rows that are exactly at 'now' to be clipped into last bucket
            # compute previous hour bucket
            prev_bs = (bs.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1))
            if prev_bs in buckets:
                bs = prev_bs
            else:
                # skip if no suitable bucket
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
    bucket_items: list[HourlyTransferBucket] = []
    sorted_starts = sorted(buckets.keys())
    for i, start in enumerate(sorted_starts):
        end = start + timedelta(hours=1)
        # Clip last bucket end to now
        if end > now:
            end = now
        vals = buckets[start]
        bucket_items.append(
            HourlyTransferBucket(
                bucket_start=start,
                bucket_end=end,
                **vals,
            )
        )

    # Determine overall start_time and end_time for response
    resp_start = rounded_start
    resp_end = now

    return HourlyTransfersResponse(start_time=resp_start, end_time=resp_end, buckets=bucket_items)

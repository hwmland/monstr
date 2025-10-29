from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.transfer_grouped import TransferGroupedRepository
from ...schemas import TransferGroupedFilters, TransferGroupedRead
from ...schemas import DataDistributionRequest, DataDistributionResponse, DataDistributionItem
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

    return DataDistributionResponse(start_time=min_start or one_hour_ago, end_time=now, distribution=distribution)

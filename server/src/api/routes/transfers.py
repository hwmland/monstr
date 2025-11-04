from __future__ import annotations

from collections import defaultdict
from datetime import timedelta, timezone, datetime
from typing import Sequence

from fastapi import APIRouter, Depends
from server.src.core.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.transfers import TransferRepository
from ...repositories.transfer_grouped import TransferGroupedRepository
from ...schemas import (
    TransferActualCategoryMetrics,
    TransferActualRequest,
    TransferActualResponse,
    TransferActualMetrics,
    TransferActualSatelliteMetrics,
    TransferFilters,
    TransferRead,
)

router = APIRouter(prefix="/api/transfers", tags=["transfers"])

logger = get_logger(__name__)


@router.get("", response_model=list[TransferRead], tags=["raw"])
async def list_transfers(
    filters: TransferFilters = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Sequence[TransferRead]:
    """Return transfer records filtered by the requested criteria."""
    repository = TransferRepository(session)
    records = await repository.list(filters)
    return [TransferRead.model_validate(record) for record in records]


@router.post("/actual", response_model=TransferActualResponse)
async def get_transfer_actuals(
    payload: TransferActualRequest,
    session: AsyncSession = Depends(get_session),
) -> TransferActualResponse:
    """Aggregate transfer activity for the past hour for the requested nodes."""
    repository = TransferRepository(session)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)

    nodes = sorted({node for node in payload.nodes if node})

    # First, load pre-aggregated granularity=1 rows from TransferGrouped to cover
    # as much of the window as possible. This avoids scanning all raw Transfer
    # rows when historical aggregates exist.
    grouped_repo = TransferGroupedRepository(session)
    grouped_rows = await grouped_repo.list_for_sources_between(nodes or None, start_time, end_time, granularity=1)

    # Initialize buckets
    def new_bucket() -> dict[str, float]:
        return {"operations_total": 0, "operations_success": 0, "bytes": 0}

    def new_category() -> dict[str, dict[str, float]]:
        return {"normal": new_bucket(), "repair": new_bucket()}

    overall = {"download": new_category(), "upload": new_category()}
    satellites: dict[str, dict[str, dict[str, dict[str, float]]]] = defaultdict(
        lambda: {"download": new_category(), "upload": new_category()}
    )

    earliest_data_ts = None

    # Aggregate from grouped rows first
    for r in grouped_rows:
        # Use interval_start as representative timestamp for the grouped row
        if earliest_data_ts is None or r.interval_start < earliest_data_ts:
            earliest_data_ts = r.interval_start

        # download metrics
        # normal
        overall_bucket = overall["download"]["normal"]
        overall_bucket["operations_total"] += int(r.count_dl_succ_nor or 0) + int(r.count_dl_fail_nor or 0)
        overall_bucket["operations_success"] += int(r.count_dl_succ_nor or 0)
        overall_bucket["bytes"] += int(r.size_dl_succ_nor or 0)

        sat_bucket = satellites[r.satellite_id]["download"]["normal"]
        sat_bucket["operations_total"] += int(r.count_dl_succ_nor or 0) + int(r.count_dl_fail_nor or 0)
        sat_bucket["operations_success"] += int(r.count_dl_succ_nor or 0)
        sat_bucket["bytes"] += int(r.size_dl_succ_nor or 0)

        # repair
        overall_bucket = overall["download"]["repair"]
        overall_bucket["operations_total"] += int(r.count_dl_succ_rep or 0) + int(r.count_dl_fail_rep or 0)
        overall_bucket["operations_success"] += int(r.count_dl_succ_rep or 0)
        overall_bucket["bytes"] += int(r.size_dl_succ_rep or 0)

        sat_bucket = satellites[r.satellite_id]["download"]["repair"]
        sat_bucket["operations_total"] += int(r.count_dl_succ_rep or 0) + int(r.count_dl_fail_rep or 0)
        sat_bucket["operations_success"] += int(r.count_dl_succ_rep or 0)
        sat_bucket["bytes"] += int(r.size_dl_succ_rep or 0)

        # upload metrics
        overall_bucket = overall["upload"]["normal"]
        overall_bucket["operations_total"] += int(r.count_ul_succ_nor or 0) + int(r.count_ul_fail_nor or 0)
        overall_bucket["operations_success"] += int(r.count_ul_succ_nor or 0)
        overall_bucket["bytes"] += int(r.size_ul_succ_nor or 0)

        sat_bucket = satellites[r.satellite_id]["upload"]["normal"]
        sat_bucket["operations_total"] += int(r.count_ul_succ_nor or 0) + int(r.count_ul_fail_nor or 0)
        sat_bucket["operations_success"] += int(r.count_ul_succ_nor or 0)
        sat_bucket["bytes"] += int(r.size_ul_succ_nor or 0)

        # repair uploads
        overall_bucket = overall["upload"]["repair"]
        overall_bucket["operations_total"] += int(r.count_ul_succ_rep or 0) + int(r.count_ul_fail_rep or 0)
        overall_bucket["operations_success"] += int(r.count_ul_succ_rep or 0)
        overall_bucket["bytes"] += int(r.size_ul_succ_rep or 0)

        sat_bucket = satellites[r.satellite_id]["upload"]["repair"]
        sat_bucket["operations_total"] += int(r.count_ul_succ_rep or 0) + int(r.count_ul_fail_rep or 0)
        sat_bucket["operations_success"] += int(r.count_ul_succ_rep or 0)
        sat_bucket["bytes"] += int(r.size_ul_succ_rep or 0)

    # Determine the end of the grouped coverage; load raw Transfer rows only after this point
    if grouped_rows:
        grouped_end = max(r.interval_end for r in grouped_rows)
    else:
        grouped_end = start_time

    # Read raw transfers only for the tail after grouped_end
    transfers_tail = await repository.list_for_sources_between(nodes or None, grouped_end, end_time)

    # Update earliest_data_ts using raw transfers if present
    if transfers_tail:
        min_transfer_ts = min(r.timestamp for r in transfers_tail)
        if earliest_data_ts is None or min_transfer_ts < earliest_data_ts:
            earliest_data_ts = min_transfer_ts

    # If we found any data, adjust start_time to earliest observed timestamp
    if earliest_data_ts is not None:
        start_time = earliest_data_ts

    # normalize to UTC-aware to avoid mixing naive/aware datetimes
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    else:
        start_time = start_time.astimezone(timezone.utc)

    interval_seconds = max((end_time - start_time).total_seconds(), 1.0)

    # Merge raw transfers tail into aggregates
    for record in transfers_tail:
        if record.action == "DL":
            action_key = "download"
        elif record.action == "UL":
            action_key = "upload"
        else:
            continue

        category_key = "repair" if record.is_repair else "normal"

        overall_bucket = overall[action_key][category_key]
        overall_bucket["operations_total"] += 1
        if record.is_success:
            overall_bucket["operations_success"] += 1
            overall_bucket["bytes"] += record.size

        satellite_bucket = satellites[record.satellite_id][action_key][category_key]
        satellite_bucket["operations_total"] += 1
        if record.is_success:
            satellite_bucket["operations_success"] += 1
            satellite_bucket["bytes"] += record.size

    def to_metrics(bucket: dict[str, float]) -> TransferActualMetrics:
        bytes_total = bucket["bytes"]
        return TransferActualMetrics(
            operations_total=int(bucket["operations_total"]),
            operations_success=int(bucket["operations_success"]),
            data_bytes=int(bytes_total),
            rate=bytes_total / interval_seconds if bytes_total else 0.0,
        )

    def to_category(group: dict[str, dict[str, float]]) -> TransferActualCategoryMetrics:
        return TransferActualCategoryMetrics(
            normal=to_metrics(group["normal"]),
            repair=to_metrics(group["repair"]),
        )

    satellite_breakdown = [
        TransferActualSatelliteMetrics(
            satellite_id=satellite_id,
            download=to_category(group["download"]),
            upload=to_category(group["upload"]),
        )
        for satellite_id, group in sorted(satellites.items())
    ]

    return TransferActualResponse(
        start_time=start_time,
        end_time=end_time,
        download=to_category(overall["download"]),
        upload=to_category(overall["upload"]),
        satellites=satellite_breakdown,
    )

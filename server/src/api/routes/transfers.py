from __future__ import annotations

from collections import defaultdict
from datetime import timedelta, timezone
from typing import Sequence

from fastapi import APIRouter, Depends, Request
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import Settings
from ...core.time import getVirtualNow
from ...database import get_session
from ...repositories.transfers import TransferRepository
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

logger = logging.getLogger(__name__)


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
    request: Request,
    payload: TransferActualRequest,
    session: AsyncSession = Depends(get_session),
) -> TransferActualResponse:
    """Aggregate transfer activity for the past hour for the requested nodes."""
    repository = TransferRepository(session)

    settings: Settings = getattr(request.app.state, "settings")

    end_time = getVirtualNow(settings)
    start_time = end_time - timedelta(hours=1)

    nodes = sorted({node for node in payload.nodes if node})
    records = await repository.list_for_sources_between(nodes or None, start_time, end_time)

    # Calculate start_time based on actual data: use the first record timestamp if available
    if records:
        start_time = min(r.timestamp for r in records)

        # normalize to UTC-aware to avoid mixing naive/aware datetimes
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        else:
            start_time = start_time.astimezone(timezone.utc)
    interval_seconds = max((end_time - start_time).total_seconds(), 1.0)
        
    def new_bucket() -> dict[str, float]:
        return {"operations_total": 0, "operations_success": 0, "bytes": 0}

    def new_category() -> dict[str, dict[str, float]]:
        return {"normal": new_bucket(), "repair": new_bucket()}

    overall = {"download": new_category(), "upload": new_category()}
    satellites: dict[str, dict[str, dict[str, dict[str, float]]]] = defaultdict(
        lambda: {"download": new_category(), "upload": new_category()}
    )

    for record in records:
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

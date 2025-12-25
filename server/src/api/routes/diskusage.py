from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.disk_usage import DiskUsageRepository
from ...schemas import (
    DiskUsageChangeNode,
    DiskUsageChangeRequest,
    DiskUsageChangeResponse,
    DiskUsageFilters,
    DiskUsageRead,
    DiskUsageUsageNode,
    DiskUsageUsageRequest,
    DiskUsageUsageResponse,
)

router = APIRouter(prefix="/api/diskusage", tags=["diskusage"])


def _period_str_to_datetime(period: str) -> datetime:
    try:
        dt = datetime.fromisoformat(period)
    except ValueError:
        try:
            dt = datetime.strptime(period, "%Y-%m")
        except ValueError:
            dt = datetime.strptime(period, "%Y-%m-%d")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("", response_model=List[DiskUsageRead], tags=["raw"])
async def list_disk_usage(
    source: str | None = Query(default=None, description="Filter by node/source name"),
    period: str | None = Query(default=None, description="Filter by period identifier"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session),
) -> List[DiskUsageRead]:
    """List disk usage records with optional filtering."""
    filters = DiskUsageFilters(source=source, period=period, limit=limit)
    repository = DiskUsageRepository(session)
    records = await repository.list(filters)
    return [DiskUsageRead.model_validate(record) for record in records]


@router.post("/usage-change", response_model=DiskUsageChangeResponse)
async def usage_change(
    payload: DiskUsageChangeRequest,
    session: AsyncSession = Depends(get_session),
) -> DiskUsageChangeResponse:
    """Return disk usage end metrics and deltas compared to the requested interval."""

    current_date = datetime.now(timezone.utc).date()
    reference_date = current_date - timedelta(days=payload.interval_days)
    current_period = current_date.isoformat()
    reference_period = reference_date.isoformat()

    nodes_filter = list(dict.fromkeys(payload.nodes)) if payload.nodes else None

    repository = DiskUsageRepository(session)
    current_records = await repository.list_for_period(current_period, nodes_filter)
    reference_records = await repository.list_for_period(reference_period, nodes_filter)

    current_map: Dict[str, DiskUsageChangeNode] = {}
    for record in current_records:
        current_map[record.source] = DiskUsageChangeNode(
            free_end=record.free_end,
            usage_end=record.usage_end,
            trash_end=record.trash_end,
        )

    reference_map = {record.source: record for record in reference_records}

    if nodes_filter:
        node_names = nodes_filter
    else:
        node_names = sorted({*current_map.keys(), *reference_map.keys()})

    nodes_result: Dict[str, DiskUsageChangeNode] = {}
    for node_name in node_names:
        current_metrics = current_map.get(node_name)
        reference_metrics = reference_map.get(node_name)

        current_free = current_metrics.free_end if current_metrics else 0
        current_usage = current_metrics.usage_end if current_metrics else 0
        current_trash = current_metrics.trash_end if current_metrics else 0

        reference_free = reference_metrics.free_end if reference_metrics else 0
        reference_usage = reference_metrics.usage_end if reference_metrics else 0
        reference_trash = reference_metrics.trash_end if reference_metrics else 0

        metrics = DiskUsageChangeNode(
            free_end=current_free,
            usage_end=current_usage,
            trash_end=current_trash,
            free_change=current_free - reference_free,
            usage_change=current_usage - reference_usage,
            trash_change=current_trash - reference_trash,
        )

        nodes_result[node_name] = metrics

    return DiskUsageChangeResponse(
        current_period=current_period,
        reference_period=reference_period,
        nodes=nodes_result,
    )


@router.post("/usage", response_model=DiskUsageUsageResponse)
async def usage(
    payload: DiskUsageUsageRequest,
    session: AsyncSession = Depends(get_session),
) -> DiskUsageUsageResponse:
    """Return per-period disk usage metrics for the requested nodes and window."""

    now_date = datetime.now(timezone.utc).date()
    start_period = (now_date - timedelta(days=payload.interval_days)).isoformat()
    end_period = now_date.isoformat()
    nodes_filter = list(dict.fromkeys(payload.nodes)) if payload.nodes else None

    repository = DiskUsageRepository(session)
    records = await repository.list_between_periods(start_period, end_period, nodes_filter)

    periods_map: Dict[str, Dict[str, DiskUsageUsageNode]] = {}

    for record in records:
        # Determine metrics based on the requested mode.
        if payload.mode == "maxUsage":
            usage_value = record.max_usage
            trash_value = record.trash_at_max_usage
            at_value = record.max_usage_at
        elif payload.mode == "maxTrash":
            usage_value = record.usage_at_max_trash
            trash_value = record.max_trash
            at_value = record.max_trash_at
        else:  # "end"
            usage_value = record.usage_end
            trash_value = record.trash_end
            at_value = _period_str_to_datetime(record.period)

        if at_value.tzinfo is None:
            at_value = at_value.replace(tzinfo=timezone.utc)

        node_metrics = DiskUsageUsageNode(
            capacity=record.free_end,
            usage=usage_value,
            trash=trash_value,
            at=at_value,
        )

        period_bucket = periods_map.setdefault(record.period, {})
        period_bucket[record.source] = node_metrics

    return DiskUsageUsageResponse(periods=periods_map)

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.satellite_usage import SatelliteUsageRepository
from ...schemas import (
    SatelliteUsageFilters,
    SatelliteUsageRead,
    SatelliteUsageRequest,
    SatelliteUsageResponse,
)

router = APIRouter(prefix="/api/satelliteusage", tags=["satelliteusage"])


@router.get("", response_model=List[SatelliteUsageRead], tags=["raw"])
async def list_satellite_usage(
    source: str | None = Query(default=None, description="Filter by node/source name"),
    satellite_id: str | None = Query(default=None, alias="satelliteId", description="Filter by satellite identifier"),
    period: str | None = Query(default=None, description="Filter by period identifier"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session),
) -> List[SatelliteUsageRead]:
    """List satellite usage records with optional filtering."""
    filters = SatelliteUsageFilters(source=source, satellite_id=satellite_id, period=period, limit=limit)
    repository = SatelliteUsageRepository(session)
    records = await repository.list(filters)
    return [SatelliteUsageRead.model_validate(record) for record in records]


@router.post("/usage", response_model=SatelliteUsageResponse)
async def satellite_usage(
    payload: SatelliteUsageRequest,
    session: AsyncSession = Depends(get_session),
) -> SatelliteUsageResponse:
    """Return satellite usage records grouped by period for the requested nodes."""

    start_period = (
        datetime.now(timezone.utc).date() - timedelta(days=payload.number_of_periods)
    ).isoformat()
    sources = list(dict.fromkeys(payload.nodes)) if payload.nodes else None
    repository = SatelliteUsageRepository(session)
    records = await repository.list_from_period(start_period, sources)

    periods: dict[str, list[SatelliteUsageRead]] = {}
    for record in records:
        bucket = periods.setdefault(record.period, [])
        bucket.append(SatelliteUsageRead.model_validate(record))

    return SatelliteUsageResponse(periods=periods)

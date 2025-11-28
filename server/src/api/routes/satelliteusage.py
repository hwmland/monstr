from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.satellite_usage import SatelliteUsageRepository
from ...schemas import SatelliteUsageFilters, SatelliteUsageRead

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

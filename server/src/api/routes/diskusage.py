from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.disk_usage import DiskUsageRepository
from ...schemas import DiskUsageFilters, DiskUsageRead

router = APIRouter(prefix="/api/diskusage", tags=["diskusage"])


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

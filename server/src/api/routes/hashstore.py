from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.hashstore_compaction import HashstoreCompactionRepository
from ...schemas import HashstoreCompactionFilters, HashstoreCompactionRead

router = APIRouter(prefix="/api/hashstore-compaction", tags=["hashstore-compaction"])


@router.get("", response_model=List[HashstoreCompactionRead], tags=["raw"])
async def list_hashstore_compactions(
    source: Optional[str] = Query(default=None, description="Filter by node/source name"),
    satellite_id: Optional[str] = Query(default=None, alias="satelliteId", description="Filter by satellite"),
    store: Optional[str] = Query(default=None, description="Filter by store (s0, s1)"),
    since: Optional[datetime] = Query(default=None, description="Records after this timestamp"),
    until: Optional[datetime] = Query(default=None, description="Records before this timestamp"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum records to return"),
    session: AsyncSession = Depends(get_session),
) -> List[HashstoreCompactionRead]:
    """List hashstore compaction records with optional filtering."""
    repository = HashstoreCompactionRepository(session)
    records = await repository.list(
        source=source,
        satellite_id=satellite_id,
        store=store,
        since=since,
        until=until,
        limit=limit,
    )
    return [HashstoreCompactionRead.model_validate(record) for record in records]

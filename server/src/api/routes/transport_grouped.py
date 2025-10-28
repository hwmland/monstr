from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.transport_grouped import TransportGroupedRepository
from ...schemas import TransportGroupedFilters, TransportGroupedRead

router = APIRouter(prefix="/api/transport-grouped", tags=["transport-grouped"])


@router.get("", response_model=list[TransportGroupedRead], tags=["raw"])
async def list_transport_grouped(
    filters: TransportGroupedFilters = Depends(),
    size_class_param: str | None = Query(default=None, alias="sizeClass"),
    session: AsyncSession = Depends(get_session),
) -> Sequence[TransportGroupedRead]:
    """Return grouped transport aggregates for the requested filters."""
    if size_class_param is not None:
        filters.size_class = size_class_param
    repository = TransportGroupedRepository(session)
    records = await repository.list(filters)
    return [TransportGroupedRead.model_validate(record) for record in records]

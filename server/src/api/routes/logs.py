from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.log_entries import LogEntryRepository
from ...schemas import LogEntryFilters, LogEntryRead

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/", response_model=list[LogEntryRead], tags=["raw"])
async def list_logs(
    filters: LogEntryFilters = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Sequence[LogEntryRead]:
    """Return log entries filtered by the requested criteria."""
    repository = LogEntryRepository(session)
    records = await repository.list(filters)
    return [LogEntryRead.model_validate(record) for record in records]

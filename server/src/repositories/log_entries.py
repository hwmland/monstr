from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import LogEntry
from ..schemas import LogEntryCreate, LogEntryFilters


class LogEntryRepository:
    """Encapsulates database interactions for log entry records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, items: Iterable[LogEntryCreate]) -> Sequence[LogEntry]:
        records = [LogEntry(**item.model_dump()) for item in items]
        self._session.add_all(records)
        await self._session.commit()
        for record in records:
            await self._session.refresh(record)
        return records

    async def list(self, filters: LogEntryFilters) -> Sequence[LogEntry]:
        stmt = select(LogEntry).order_by(LogEntry.ingested_at.desc()).limit(filters.limit)
        if filters.source:
            stmt = stmt.where(LogEntry.source == filters.source)

        result = await self._session.execute(stmt)
        return tuple(result.scalars())

    async def delete_older_than(self, cutoff: datetime) -> int:
        stmt = delete(LogEntry).where(LogEntry.ingested_at < cutoff)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount or 0

from __future__ import annotations

from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import TransportGrouped
from ..schemas import TransportGroupedCreate, TransportGroupedFilters


class TransportGroupedRepository:
    """Database operations for transport grouping aggregates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, items: Iterable[TransportGroupedCreate]) -> Sequence[TransportGrouped]:
        records = [TransportGrouped(**item.model_dump(by_alias=False)) for item in items]
        self._session.add_all(records)
        await self._session.flush()
        await self._session.commit()
        return records

    async def list(self, filters: TransportGroupedFilters) -> Sequence[TransportGrouped]:
        stmt = select(TransportGrouped).order_by(TransportGrouped.interval_start.desc(), TransportGrouped.id.desc())

        if filters.source:
            stmt = stmt.where(TransportGrouped.source == filters.source)
        if filters.satellite_id:
            stmt = stmt.where(TransportGrouped.satellite_id == filters.satellite_id)
        if filters.size_class:
            stmt = stmt.where(TransportGrouped.size_class == filters.size_class)
        if filters.interval_start_from:
            stmt = stmt.where(TransportGrouped.interval_start >= filters.interval_start_from)
        if filters.interval_start_to:
            stmt = stmt.where(TransportGrouped.interval_start <= filters.interval_start_to)

        stmt = stmt.limit(filters.limit)

        result = await self._session.execute(stmt)
        return tuple(result.scalars())

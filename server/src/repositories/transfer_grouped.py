from __future__ import annotations

from typing import Iterable, Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import TransferGrouped
from ..schemas import TransferGroupedCreate, TransferGroupedFilters


class TransferGroupedRepository:
    """Database operations for transfer grouping aggregates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, items: Iterable[TransferGroupedCreate]) -> Sequence[TransferGrouped]:
        records = [TransferGrouped(**item.model_dump(by_alias=False)) for item in items]
        self._session.add_all(records)
        await self._session.flush()
        await self._session.commit()
        return records

    async def list(self, filters: TransferGroupedFilters) -> Sequence[TransferGrouped]:
        stmt = select(TransferGrouped).order_by(TransferGrouped.interval_start.desc(), TransferGrouped.id.desc())

        if filters.source:
            stmt = stmt.where(TransferGrouped.source == filters.source)
        if filters.granularity is not None:
            stmt = stmt.where(TransferGrouped.granularity == filters.granularity)
        if filters.satellite_id:
            stmt = stmt.where(TransferGrouped.satellite_id == filters.satellite_id)
        if filters.size_class:
            stmt = stmt.where(TransferGrouped.size_class == filters.size_class)
        if filters.interval_start_from:
            stmt = stmt.where(TransferGrouped.interval_start >= filters.interval_start_from)
        if filters.interval_start_to:
            stmt = stmt.where(TransferGrouped.interval_start <= filters.interval_start_to)

        stmt = stmt.limit(filters.limit)

        result = await self._session.execute(stmt)
        return tuple(result.scalars())

    async def list_for_granularity_before(self, granularity: int, end: "datetime") -> Sequence[TransferGrouped]:
        """Return TransferGrouped rows at a specific granularity with interval_end < end."""
        stmt = select(TransferGrouped).where(TransferGrouped.granularity == granularity).where(TransferGrouped.interval_end < end).order_by(TransferGrouped.interval_start.asc())
        result = await self._session.execute(stmt)
        return tuple(result.scalars())

    async def list_for_sources_between(
        self,
        sources: list[str] | None,
        start: "datetime",
        end: "datetime",
        granularity: int = 1,
    ) -> Sequence[TransferGrouped]:
        """Return TransferGrouped rows at a specific granularity between start (inclusive) and end (exclusive).

        If `sources` is provided, filter to those source names.
        """
        stmt = select(TransferGrouped).where(TransferGrouped.granularity == granularity)
        stmt = stmt.where(TransferGrouped.interval_start >= start).where(TransferGrouped.interval_end <= end)
        if sources:
            stmt = stmt.where(TransferGrouped.source.in_(sources))
        stmt = stmt.order_by(TransferGrouped.interval_start.asc())
        result = await self._session.execute(stmt)
        return tuple(result.scalars())

    async def delete_many_by_ids(self, ids: list[int]) -> None:
        """Delete many TransferGrouped rows by id."""
        if not ids:
            return
        # Import inside function to avoid circular import issues in some test setups
        from sqlalchemy import delete

        stmt = delete(TransferGrouped).where(TransferGrouped.id.in_(ids))
        await self._session.execute(stmt)

    async def delete_older_than(self, cutoff: datetime) -> int:
        """Delete TransferGrouped rows whose interval_end is older than cutoff.

        Returns the number of rows deleted.
        """
        # Import locally to avoid top-level circular import complications in tests
        from sqlalchemy import delete

        stmt = delete(TransferGrouped).where(TransferGrouped.interval_end < cutoff)
        result = await self._session.execute(stmt)
        await self._session.commit()
        # Some dialects/execution contexts expose rowcount on result
        return getattr(result, "rowcount", 0) or 0

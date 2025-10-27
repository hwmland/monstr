from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transfer
from ..schemas import TransferCreate, TransferFilters


class TransferRepository:
    """Encapsulates database interactions for transfer records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, items: Iterable[TransferCreate]) -> Sequence[Transfer]:
        records = [Transfer(**item.model_dump()) for item in items]
        self._session.add_all(records)
        await self._session.flush()
        await self._session.commit()
        return records

    async def list(self, filters: TransferFilters) -> Sequence[Transfer]:
        stmt = select(Transfer).order_by(Transfer.timestamp.desc())
        if filters.source:
            stmt = stmt.where(Transfer.source == filters.source)
        if filters.action:
            stmt = stmt.where(Transfer.action == filters.action)
        if filters.satellite_id:
            stmt = stmt.where(Transfer.satellite_id == filters.satellite_id)
        if filters.piece_id:
            stmt = stmt.where(Transfer.piece_id == filters.piece_id)
        if filters.is_success is not None:
            stmt = stmt.where(Transfer.is_success == filters.is_success)
        if filters.is_repair is not None:
            stmt = stmt.where(Transfer.is_repair == filters.is_repair)

        stmt = stmt.limit(filters.limit)

        result = await self._session.execute(stmt)
        return tuple(result.scalars())

    async def list_for_sources_between(
        self,
        sources: Sequence[str] | None,
        start: datetime,
        end: datetime,
    ) -> Sequence[Transfer]:
        stmt = select(Transfer).where(Transfer.timestamp >= start, Transfer.timestamp <= end)
        if sources:
            stmt = stmt.where(Transfer.source.in_(tuple(sources)))

        result = await self._session.execute(stmt)
        return tuple(result.scalars())

    async def delete_older_than(self, cutoff: datetime) -> int:
        stmt = delete(Transfer).where(Transfer.timestamp < cutoff)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount or 0

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import HashstoreCompaction


class HashstoreCompactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, record: HashstoreCompaction) -> HashstoreCompaction:
        self.session.add(record)
        await self.session.flush()
        return record

    async def create_many(self, records: List[HashstoreCompaction]) -> None:
        self.session.add_all(records)
        await self.session.flush()

    async def list(
        self,
        source: Optional[str] = None,
        satellite_id: Optional[str] = None,
        store: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        sources: Optional[Sequence[str]] = None,
        limit: int = 100,
    ) -> List[HashstoreCompaction]:
        stmt = select(HashstoreCompaction)

        if source:
            stmt = stmt.where(HashstoreCompaction.source == source)
        if sources:
            stmt = stmt.where(HashstoreCompaction.source.in_(sources))
        if satellite_id:
            stmt = stmt.where(HashstoreCompaction.satellite_id == satellite_id)
        if store:
            stmt = stmt.where(HashstoreCompaction.store == store)
        if since:
            stmt = stmt.where(HashstoreCompaction.timestamp >= since)
        if until:
            stmt = stmt.where(HashstoreCompaction.timestamp <= until)

        stmt = stmt.order_by(HashstoreCompaction.timestamp.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def delete_older_than(self, cutoff: datetime) -> int:
        from sqlalchemy import delete as sa_delete

        stmt = sa_delete(HashstoreCompaction).where(
            HashstoreCompaction.timestamp < cutoff
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0

from __future__ import annotations

from typing import List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import HeldAmount
from ..schemas import HeldAmountFilters


class HeldAmountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, filters: HeldAmountFilters) -> List[HeldAmount]:
        stmt = select(HeldAmount)

        conditions = []
        if filters.source:
            conditions.append(HeldAmount.source == filters.source)
        if filters.satellite_id:
            conditions.append(HeldAmount.satellite_id == filters.satellite_id)
        # Note: timestamp-based filtering intentionally not supported per request

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(HeldAmount.timestamp.desc()).limit(filters.limit)

        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def get_latest(self, source: str, satellite_id: str):
        """Return the newest HeldAmount record for the given source and satellite_id, or None."""
        stmt = select(HeldAmount).where(
            and_(HeldAmount.source == source, HeldAmount.satellite_id == satellite_id)
        ).order_by(HeldAmount.timestamp.desc()).limit(1)
        result = await self.session.execute(stmt)
        row = result.fetchone()
        if not row:
            return None
        return row[0]

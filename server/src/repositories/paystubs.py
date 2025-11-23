from __future__ import annotations

from typing import List, Optional

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Paystub
from ..schemas import PaystubFilters


class PaystubRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, filters: PaystubFilters) -> List[Paystub]:
        stmt = select(Paystub)

        conditions = []
        if filters.source:
            conditions.append(Paystub.source == filters.source)
        if filters.satellite_id:
            conditions.append(Paystub.satellite_id == filters.satellite_id)
        if filters.period:
            conditions.append(Paystub.period == filters.period)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(Paystub.created.desc()).limit(filters.limit)
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def get_latest_period(self, source: str, satellite_id: Optional[str] = None) -> Optional[str]:
        stmt = select(func.max(Paystub.period)).where(Paystub.source == source)
        if satellite_id:
            stmt = stmt.where(Paystub.satellite_id == satellite_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

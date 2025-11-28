from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SatelliteUsage
from ..schemas import SatelliteUsageFilters


class SatelliteUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, filters: SatelliteUsageFilters) -> List[SatelliteUsage]:
        stmt = select(SatelliteUsage)

        if filters.source:
            stmt = stmt.where(SatelliteUsage.source == filters.source)
        if filters.satellite_id:
            stmt = stmt.where(SatelliteUsage.satellite_id == filters.satellite_id)
        if filters.period:
            stmt = stmt.where(SatelliteUsage.period == filters.period)

        stmt = stmt.order_by(
            SatelliteUsage.period.desc(),
            SatelliteUsage.source,
            SatelliteUsage.satellite_id,
        ).limit(filters.limit)
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]

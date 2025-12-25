from __future__ import annotations

from typing import Iterable, List, Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DiskUsage
from ..schemas import DiskUsageFilters


class DiskUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, filters: DiskUsageFilters) -> List[DiskUsage]:
        stmt = select(DiskUsage)

        if filters.source:
            stmt = stmt.where(DiskUsage.source == filters.source)
        if filters.period:
            stmt = stmt.where(DiskUsage.period == filters.period)

        stmt = stmt.order_by(DiskUsage.period.desc(), DiskUsage.source).limit(filters.limit)
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]
    
    async def get_by_source_period(self, source: str, period: str) -> Optional[DiskUsage]:
        """Return the DiskUsage record for (source, period) or None."""
        stmt = select(DiskUsage).where(DiskUsage.source == source, DiskUsage.period == period)
        result = await self.session.execute(stmt)
        row = result.fetchone()
        if not row:
            return None
        return row[0]

    async def list_for_period(
        self,
        period: str,
        sources: Optional[Sequence[str]] = None,
    ) -> List[DiskUsage]:
        """Return all disk usage records matching the supplied period and optional sources."""

        stmt = select(DiskUsage).where(DiskUsage.period == period)
        if sources:
            stmt = stmt.where(DiskUsage.source.in_(sources))

        stmt = stmt.order_by(DiskUsage.source)
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def list_between_periods(
        self,
        start_period: str,
        end_period: str,
        sources: Optional[Sequence[str]] = None,
    ) -> List[DiskUsage]:
        """Return records whose period is between the provided bounds (inclusive)."""

        stmt = select(DiskUsage).where(DiskUsage.period >= start_period, DiskUsage.period <= end_period)
        if sources:
            stmt = stmt.where(DiskUsage.source.in_(sources))

        stmt = stmt.order_by(DiskUsage.period.desc(), DiskUsage.source)
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]

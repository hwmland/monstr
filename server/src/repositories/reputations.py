from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Reputation
from ..schemas import ReputationCreate, ReputationFilters


class ReputationRepository:
    """Encapsulates database interactions for reputation metrics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, items: Iterable[ReputationCreate]) -> Sequence[Reputation]:
        records: list[Reputation] = []
        for item in items:
            record = await self._session.get(Reputation, (item.source, item.satellite_id))
            item_timestamp = self._ensure_timezone(item.timestamp)
            if record is None:
                payload = item.model_dump()
                payload["timestamp"] = item_timestamp
                record = Reputation(**payload)
                self._session.add(record)
                records.append(record)
                continue

            record_timestamp = self._ensure_timezone(record.timestamp)

            if item_timestamp > record_timestamp:
                record.timestamp = item_timestamp
                record.audits_total = item.audits_total
                record.audits_success = item.audits_success
                record.score_audit = item.score_audit
                record.score_online = item.score_online
                record.score_suspension = item.score_suspension
                records.append(record)

        await self._session.flush()
        await self._session.commit()
        return tuple(records)

    async def get_latest(self, source: str, satellite_id: str) -> Reputation | None:
        return await self._session.get(Reputation, (source, satellite_id))

    async def list(self, filters: ReputationFilters) -> Sequence[Reputation]:
        stmt = select(Reputation).order_by(Reputation.timestamp.desc())
        if filters.source:
            stmt = stmt.where(Reputation.source == filters.source)
        if filters.satellite_id:
            stmt = stmt.where(Reputation.satellite_id == filters.satellite_id)

        stmt = stmt.limit(filters.limit)

        result = await self._session.execute(stmt)
        return tuple(result.scalars())

    async def list_all(self) -> Sequence[Reputation]:
        stmt = select(Reputation).order_by(Reputation.source, Reputation.satellite_id)
        result = await self._session.execute(stmt)
        return tuple(result.scalars())

    async def list_for_sources(self, sources: Sequence[str]) -> Sequence[Reputation]:
        if not sources:
            return ()

        stmt = (
            select(Reputation)
            .where(Reputation.source.in_(tuple(sources)))
            .order_by(Reputation.source, Reputation.satellite_id)
        )
        result = await self._session.execute(stmt)
        return tuple(result.scalars())

    def _ensure_timezone(self, value: datetime) -> datetime:
        """Normalize timestamps so comparisons don't fail on naive vs aware datetimes."""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=timezone.utc)
        return value

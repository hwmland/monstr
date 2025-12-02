from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, TYPE_CHECKING
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import TransferGrouped
from ..core.logging import get_logger

# module-level logger
logger = get_logger(__name__)

if TYPE_CHECKING:  # pragma: no cover - used only for type checking
    from ..models import Transfer
from ..schemas import TransferGroupedCreate, TransferGroupedFilters
from .transfers import TransferRepository


class TransferGroupedRepository:
    """Database operations for transfer grouping aggregates."""

    @dataclass(frozen=True)
    class PromotionRule:
        granularity: int
        min_old_minutes: int
        newest_threshold_minutes: int

    # MUST be sorted by granularity
    # min_old_minutes and newest_threshold_minutes are for groping service
    PROMOTION_RULES: tuple[PromotionRule, ...] = (
        PromotionRule(granularity=1, min_old_minutes=120, newest_threshold_minutes=90),
        PromotionRule(granularity=5, min_old_minutes=36 * 60, newest_threshold_minutes=31 * 60),
        PromotionRule(granularity=60, min_old_minutes=0, newest_threshold_minutes=0),
    )

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

    async def collect_interval_rows(
        self,
        sources: list[str] | None,
        rounded_start: datetime,
        end: datetime,
    ) -> Sequence[TransferGrouped]:
        """Return rows covering the requested window using aggregated tables and raw transfers."""

        rows: list[TransferGrouped] = []
        total_start = perf_counter()

        cursor = rounded_start
        for rule in reversed(self.PROMOTION_RULES):
            start = perf_counter()
            gran_rows = await self.list_for_sources_between(sources, cursor, end, granularity=rule.granularity)
            duration_ms = int((perf_counter() - start) * 1000)
            logger.debug("collect_interval_rows: %dms granularity=%s returned %d aggregated rows", duration_ms, rule.granularity, len(gran_rows))
            rows.extend(gran_rows)
            cursor = self._ensure_utc(self._max_interval_end(gran_rows, cursor))

        transfer_repo = TransferRepository(self._session)
        start = perf_counter()
        transfers_since_gran1 = await transfer_repo.list_for_sources_between(sources or None, cursor, end)
        duration_ms = int((perf_counter() - start) * 1000)
        logger.debug("collect_interval_rows: %dms transfers_since_gran1 returned %d raw transfer rows", duration_ms, len(transfers_since_gran1))
        rows.extend(self._convert_transfers(transfers_since_gran1))

        total_ms = int((perf_counter() - total_start) * 1000)
        logger.debug("collect_interval_rows: %dms total elapsed, returning %d rows", total_ms, len(rows))

        return tuple(rows)

    async def delete_many_by_ids(self, ids: list[int]) -> None:
        """Delete many TransferGrouped rows by id."""
        if not ids:
            return

        stmt = delete(TransferGrouped).where(TransferGrouped.id.in_(ids))
        await self._session.execute(stmt)

    async def delete_older_than(self, cutoff: datetime) -> int:
        """Delete TransferGrouped rows whose interval_end is older than cutoff.

        Returns the number of rows deleted.
        """

        stmt = delete(TransferGrouped).where(TransferGrouped.interval_end < cutoff)
        result = await self._session.execute(stmt)
        await self._session.commit()
        # Some dialects/execution contexts expose rowcount on result
        return getattr(result, "rowcount", 0) or 0

    @classmethod
    def _max_interval_end(cls, rows: Sequence[TransferGrouped], default: datetime) -> datetime:
        latest = cls._ensure_utc(default)
        for row in rows:
            row_end = cls._ensure_utc(row.interval_end)
            if row_end > latest:
                latest = row_end
        return latest

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _convert_transfers(transfers: Sequence["Transfer"]) -> list[TransferGrouped]:
        converted: list[TransferGrouped] = []
        for tr in transfers:
            mode = "succ" if tr.is_success else "fail"
            repair = "rep" if tr.is_repair else "nor"
            record = TransferGrouped(
                source=tr.source,
                satellite_id=tr.satellite_id,
                interval_start=tr.timestamp,
                interval_end=tr.timestamp,
                size_class="",
                granularity=1,
                size_dl_succ_nor=0,
                size_ul_succ_nor=0,
                size_dl_fail_nor=0,
                size_ul_fail_nor=0,
                size_dl_succ_rep=0,
                size_ul_succ_rep=0,
                size_dl_fail_rep=0,
                size_ul_fail_rep=0,
                count_dl_succ_nor=0,
                count_ul_succ_nor=0,
                count_dl_fail_nor=0,
                count_ul_fail_nor=0,
                count_dl_succ_rep=0,
                count_ul_succ_rep=0,
                count_dl_fail_rep=0,
                count_ul_fail_rep=0,
            )

            if tr.action == "DL":
                setattr(record, f"size_dl_{mode}_{repair}", tr.size)
                setattr(record, f"count_dl_{mode}_{repair}", 1)
            else:
                setattr(record, f"size_ul_{mode}_{repair}", tr.size)
                setattr(record, f"count_ul_{mode}_{repair}", 1)

            converted.append(record)

        return converted

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, TYPE_CHECKING
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import delete, func, literal_column, text
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
        """Return TransferGrouped rows at a specific granularity with interval_end < end.

        Excludes ``size_class='all'`` rows because promotions re-compute the
        'all' aggregate from per-size-class entries.  Including existing 'all'
        rows would produce duplicate 'all' records with double-counted values.
        """
        stmt = select(TransferGrouped).where(TransferGrouped.granularity == granularity).where(TransferGrouped.interval_end < end).where(TransferGrouped.size_class != 'all').order_by(TransferGrouped.interval_start.asc())
        result = await self._session.execute(stmt)
        return tuple(result.scalars())

    async def list_for_sources_between(
        self,
        sources: list[str] | None,
        start: "datetime",
        end: "datetime",
        granularity: int = 1,
        size_class: str | None = None,
    ) -> Sequence[TransferGrouped]:
        """Return TransferGrouped rows at a specific granularity between start (inclusive) and end (exclusive).

        If `sources` is provided, filter to those source names.
        If `size_class` is given, filter to that exact value; otherwise exclude 'all' rows.
        """
        stmt = select(TransferGrouped).where(TransferGrouped.granularity == granularity)
        stmt = stmt.where(TransferGrouped.interval_start >= start).where(TransferGrouped.interval_end <= end)
        if size_class is not None:
            stmt = stmt.where(TransferGrouped.size_class == size_class)
        else:
            stmt = stmt.where(TransferGrouped.size_class != 'all')
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

    # Column names shared by all aggregation helpers
    METRIC_COLUMNS: tuple[str, ...] = (
        "size_dl_succ_nor", "size_ul_succ_nor", "size_dl_fail_nor", "size_ul_fail_nor",
        "size_dl_succ_rep", "size_ul_succ_rep", "size_dl_fail_rep", "size_ul_fail_rep",
        "count_dl_succ_nor", "count_ul_succ_nor", "count_dl_fail_nor", "count_ul_fail_nor",
        "count_dl_succ_rep", "count_ul_succ_rep", "count_dl_fail_rep", "count_ul_fail_rep",
    )

    async def collect_interval_buckets(
        self,
        sources: list[str] | None,
        rounded_start: datetime,
        end: datetime,
        bucket_seconds: int,
    ) -> tuple[dict[int, dict[str, int]], datetime]:
        """Return pre-aggregated time-buckets covering the requested window.

        Uses SQL SUM + GROUP BY to push aggregation to the database.
        Returns (buckets_dict, max_end) where buckets_dict maps bucket
        unix-timestamp to {metric: summed_value}.
        """
        total_start = perf_counter()
        buckets: dict[int, dict[str, int]] = {}
        latest_end = self._ensure_utc(rounded_start)

        cursor = rounded_start
        for rule in reversed(self.PROMOTION_RULES):
            t0 = perf_counter()
            # For granularity >= 5 use the pre-aggregated 'all' size_class;
            # for granularity == 1 there is no 'all' row, so sum across all size classes.
            sc_filter = "all" if rule.granularity > 1 else None
            rows, max_end = await self._aggregate_grouped_sql(
                sources, cursor, end, rule.granularity, bucket_seconds, sc_filter,
            )
            duration_ms = int((perf_counter() - t0) * 1000)
            logger.debug(
                "collect_interval_buckets: %dms granularity=%d returned %d buckets",
                duration_ms, rule.granularity, len(rows),
            )
            for bucket_ts, vals in rows.items():
                if bucket_ts in buckets:
                    for k in self.METRIC_COLUMNS:
                        buckets[bucket_ts][k] += vals[k]
                else:
                    buckets[bucket_ts] = dict(vals)
            if max_end is not None:
                max_end_utc = self._ensure_utc(max_end)
                if max_end_utc > latest_end:
                    latest_end = max_end_utc
                cursor = latest_end

        # Raw Transfer tail (usually just a few minutes of data)
        transfer_repo = TransferRepository(self._session)
        t0 = perf_counter()
        raw_rows, raw_max_end = await self._aggregate_transfers_sql(
            sources, cursor, end, bucket_seconds,
        )
        duration_ms = int((perf_counter() - t0) * 1000)
        logger.debug(
            "collect_interval_buckets: %dms raw transfers returned %d buckets",
            duration_ms, len(raw_rows),
        )
        for bucket_ts, vals in raw_rows.items():
            if bucket_ts in buckets:
                for k in self.METRIC_COLUMNS:
                    buckets[bucket_ts][k] += vals[k]
            else:
                buckets[bucket_ts] = dict(vals)

        total_ms = int((perf_counter() - total_start) * 1000)
        logger.debug(
            "collect_interval_buckets: %dms total elapsed, returning %d buckets",
            total_ms, len(buckets),
        )
        return buckets, latest_end

    async def collect_totals_by_source(
        self,
        sources: list[str] | None,
        start: datetime,
        end: datetime,
    ) -> dict[str, dict[str, int]]:
        """Return per-source totals covering the requested window using SQL aggregation.

        Returns {source_name: {metric: summed_value}}.
        """
        total_start = perf_counter()
        totals: dict[str, dict[str, int]] = {}

        cursor = start
        for rule in reversed(self.PROMOTION_RULES):
            t0 = perf_counter()
            sc_filter = "all" if rule.granularity > 1 else None
            rows, max_end = await self._aggregate_grouped_by_source_sql(
                sources, cursor, end, rule.granularity, sc_filter,
            )
            duration_ms = int((perf_counter() - t0) * 1000)
            logger.debug(
                "collect_totals_by_source: %dms granularity=%d returned %d sources",
                duration_ms, rule.granularity, len(rows),
            )
            for src, vals in rows.items():
                if src in totals:
                    for k in self.METRIC_COLUMNS:
                        totals[src][k] += vals[k]
                else:
                    totals[src] = dict(vals)
            if max_end is not None:
                max_end_utc = self._ensure_utc(max_end)
                cursor = max_end_utc

        # Raw Transfer tail
        t0 = perf_counter()
        raw_rows, _ = await self._aggregate_transfers_by_source_sql(sources, cursor, end)
        duration_ms = int((perf_counter() - t0) * 1000)
        logger.debug(
            "collect_totals_by_source: %dms raw transfers returned %d sources",
            duration_ms, len(raw_rows),
        )
        for src, vals in raw_rows.items():
            if src in totals:
                for k in self.METRIC_COLUMNS:
                    totals[src][k] += vals[k]
            else:
                totals[src] = dict(vals)

        total_ms = int((perf_counter() - total_start) * 1000)
        logger.debug("collect_totals_by_source: %dms total", total_ms)
        return totals

    # ------------------------------------------------------------------
    # Internal SQL aggregation helpers
    # ------------------------------------------------------------------

    async def _aggregate_grouped_sql(
        self,
        sources: list[str] | None,
        start: datetime,
        end: datetime,
        granularity: int,
        bucket_seconds: int,
        size_class: str | None,
    ) -> tuple[dict[int, dict[str, int]], datetime | None]:
        """Run SUM+GROUP BY on transfergrouped, bucketing by *bucket_seconds*."""
        table = TransferGrouped.__tablename__
        sum_cols = ", ".join(f'SUM("{c}") AS "{c}"' for c in self.METRIC_COLUMNS)
        bucket_expr = f'(CAST(strftime(\'%s\', "interval_start") AS INTEGER) / :bucket) * :bucket'

        where = '"granularity" = :gran AND "interval_start" >= :start AND "interval_end" <= :end'
        params: dict = {
            "bucket": bucket_seconds,
            "gran": granularity,
            "start": self._format_dt(start),
            "end": self._format_dt(end),
        }
        if size_class is not None:
            where += ' AND "size_class" = :sc'
            params["sc"] = size_class
        else:
            where += ' AND "size_class" != \'all\''
        if sources:
            placeholders = ", ".join(f":src{i}" for i in range(len(sources)))
            where += f' AND "source" IN ({placeholders})'
            for i, s in enumerate(sources):
                params[f"src{i}"] = s

        sql = (
            f'SELECT {bucket_expr} AS bucket_ts, {sum_cols}, '
            f'MAX("interval_end") AS max_end '
            f'FROM "{table}" WHERE {where} '
            f'GROUP BY bucket_ts ORDER BY bucket_ts'
        )
        result = await self._session.execute(text(sql), params)
        rows_out: dict[int, dict[str, int]] = {}
        max_end_val: datetime | None = None
        for row in result:
            bucket_ts = int(row[0])
            vals = {col: int(row[i + 1] or 0) for i, col in enumerate(self.METRIC_COLUMNS)}
            rows_out[bucket_ts] = vals
            row_max_end = row[len(self.METRIC_COLUMNS) + 1]
            if row_max_end is not None:
                parsed = self._parse_dt(row_max_end)
                if max_end_val is None or parsed > max_end_val:
                    max_end_val = parsed
        return rows_out, max_end_val

    async def _aggregate_grouped_by_source_sql(
        self,
        sources: list[str] | None,
        start: datetime,
        end: datetime,
        granularity: int,
        size_class: str | None,
    ) -> tuple[dict[str, dict[str, int]], datetime | None]:
        """Run SUM+GROUP BY source on transfergrouped."""
        table = TransferGrouped.__tablename__
        sum_cols = ", ".join(f'SUM("{c}") AS "{c}"' for c in self.METRIC_COLUMNS)

        where = '"granularity" = :gran AND "interval_start" >= :start AND "interval_end" <= :end'
        params: dict = {
            "gran": granularity,
            "start": self._format_dt(start),
            "end": self._format_dt(end),
        }
        if size_class is not None:
            where += ' AND "size_class" = :sc'
            params["sc"] = size_class
        else:
            where += ' AND "size_class" != \'all\''
        if sources:
            placeholders = ", ".join(f":src{i}" for i in range(len(sources)))
            where += f' AND "source" IN ({placeholders})'
            for i, s in enumerate(sources):
                params[f"src{i}"] = s

        sql = (
            f'SELECT "source", {sum_cols}, MAX("interval_end") AS max_end '
            f'FROM "{table}" WHERE {where} '
            f'GROUP BY "source" ORDER BY "source"'
        )
        result = await self._session.execute(text(sql), params)
        rows_out: dict[str, dict[str, int]] = {}
        max_end_val: datetime | None = None
        for row in result:
            source = str(row[0])
            vals = {col: int(row[i + 1] or 0) for i, col in enumerate(self.METRIC_COLUMNS)}
            rows_out[source] = vals
            row_max_end = row[len(self.METRIC_COLUMNS) + 1]
            if row_max_end is not None:
                parsed = self._parse_dt(row_max_end)
                if max_end_val is None or parsed > max_end_val:
                    max_end_val = parsed
        return rows_out, max_end_val

    async def _aggregate_transfers_sql(
        self,
        sources: list[str] | None,
        start: datetime,
        end: datetime,
        bucket_seconds: int,
    ) -> tuple[dict[int, dict[str, int]], datetime | None]:
        """Aggregate raw Transfer rows into time buckets via SQL."""
        table = "transfer"
        # Build per-action/per-mode/per-repair conditional SUM expressions
        case_sums = []
        for col in self.METRIC_COLUMNS:
            # col pattern: {size|count}_{dl|ul}_{succ|fail}_{nor|rep}
            parts = col.split("_")
            metric_type = parts[0]  # size or count
            action = parts[1].upper()  # DL or UL
            mode = parts[2]  # succ or fail
            repair = parts[3]  # nor or rep

            is_success = "1" if mode == "succ" else "0"
            is_repair = "1" if repair == "rep" else "0"
            action_cond = f'"action" = \'{action}\''
            succ_cond = f'"is_success" = {is_success}'
            repair_cond = f'"is_repair" = {is_repair}'

            if metric_type == "size":
                value_expr = '"size"'
            else:
                value_expr = "1"

            case_sums.append(
                f'SUM(CASE WHEN {action_cond} AND {succ_cond} AND {repair_cond} '
                f'THEN {value_expr} ELSE 0 END) AS "{col}"'
            )

        sum_clause = ", ".join(case_sums)
        bucket_expr = f'(CAST(strftime(\'%s\', "timestamp") AS INTEGER) / :bucket) * :bucket'

        where = '"timestamp" >= :start AND "timestamp" <= :end'
        params: dict = {
            "bucket": bucket_seconds,
            "start": self._format_dt(start),
            "end": self._format_dt(end),
        }
        if sources:
            placeholders = ", ".join(f":src{i}" for i in range(len(sources)))
            where += f' AND "source" IN ({placeholders})'
            for i, s in enumerate(sources):
                params[f"src{i}"] = s

        sql = (
            f'SELECT {bucket_expr} AS bucket_ts, {sum_clause} '
            f'FROM "{table}" WHERE {where} '
            f'GROUP BY bucket_ts ORDER BY bucket_ts'
        )
        result = await self._session.execute(text(sql), params)
        rows_out: dict[int, dict[str, int]] = {}
        for row in result:
            bucket_ts = int(row[0])
            vals = {col: int(row[i + 1] or 0) for i, col in enumerate(self.METRIC_COLUMNS)}
            rows_out[bucket_ts] = vals
        return rows_out, None

    async def _aggregate_transfers_by_source_sql(
        self,
        sources: list[str] | None,
        start: datetime,
        end: datetime,
    ) -> tuple[dict[str, dict[str, int]], datetime | None]:
        """Aggregate raw Transfer rows by source via SQL."""
        table = "transfer"
        case_sums = []
        for col in self.METRIC_COLUMNS:
            parts = col.split("_")
            metric_type = parts[0]
            action = parts[1].upper()
            mode = parts[2]
            repair = parts[3]

            is_success = "1" if mode == "succ" else "0"
            is_repair = "1" if repair == "rep" else "0"
            action_cond = f'"action" = \'{action}\''
            succ_cond = f'"is_success" = {is_success}'
            repair_cond = f'"is_repair" = {is_repair}'
            value_expr = '"size"' if metric_type == "size" else "1"

            case_sums.append(
                f'SUM(CASE WHEN {action_cond} AND {succ_cond} AND {repair_cond} '
                f'THEN {value_expr} ELSE 0 END) AS "{col}"'
            )

        sum_clause = ", ".join(case_sums)
        where = '"timestamp" >= :start AND "timestamp" <= :end'
        params: dict = {
            "start": self._format_dt(start),
            "end": self._format_dt(end),
        }
        if sources:
            placeholders = ", ".join(f":src{i}" for i in range(len(sources)))
            where += f' AND "source" IN ({placeholders})'
            for i, s in enumerate(sources):
                params[f"src{i}"] = s

        sql = (
            f'SELECT "source", {sum_clause} '
            f'FROM "{table}" WHERE {where} '
            f'GROUP BY "source" ORDER BY "source"'
        )
        result = await self._session.execute(text(sql), params)
        rows_out: dict[str, dict[str, int]] = {}
        for row in result:
            source = str(row[0])
            vals = {col: int(row[i + 1] or 0) for i, col in enumerate(self.METRIC_COLUMNS)}
            rows_out[source] = vals
        return rows_out, None

    @staticmethod
    def _format_dt(dt: datetime) -> str:
        """Format a datetime for SQLite string comparison.

        SQLite stores datetimes as ``YYYY-MM-DD HH:MM:SS.ffffff`` (space
        separator, no timezone offset).  We must produce the same format
        so that ``>=`` / ``<=`` comparisons work correctly.
        """
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")

    @staticmethod
    def _parse_dt(value) -> datetime:
        """Parse a datetime value from a raw SQL result (string or datetime)."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        # SQLite returns ISO strings
        s = str(value)
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

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

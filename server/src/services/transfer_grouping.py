from __future__ import annotations

import asyncio
import contextlib
import time
from server.src.core.logging import get_logger
from typing import Optional

from .. import database
from ..config import Settings
from datetime import timedelta, datetime, timezone
from math import floor
from sqlalchemy import select
from ..models import Transfer, TransferGrouped
from ..repositories.transfers import TransferRepository
from ..repositories.transfer_grouped import TransferGroupedRepository
from sqlalchemy.exc import OperationalError

logger = get_logger(__name__)


class TransferGroupingService:
    """Periodically groups transfer rows into aggregated transfer_grouped records."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def _to_utc(self, dt: datetime) -> datetime:
        """Return a timezone-aware datetime in UTC.

        If dt is naive we assume it's already UTC and attach UTC tzinfo.
        If dt is aware, convert to UTC.
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _round_down_to_granularity(self, dt: datetime, minutes: int) -> datetime:
        """Round a datetime down to the given minute granularity (UTC-aware)."""
        dt = self._to_utc(dt)
        total_minutes = dt.hour * 60 + dt.minute
        bucket_min = floor(total_minutes / minutes) * minutes
        base = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return base + timedelta(minutes=bucket_min)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="transfer-grouping")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                async with database.SessionFactory() as session:
                    transfer_repo = TransferRepository(session)
                    grouped_repo = TransferGroupedRepository(session)

                    # Process transfers into 1-minute grouped aggregates and time it.
                    t0 = time.time()
                    await self._process_batch(transfer_repo, grouped_repo)
                    t1 = time.time()
                    logger.info("TransferGroupingService: process batch completed in %.2fms", (t1 - t0) * 1000.0)

                    rules = TransferGroupedRepository.PROMOTION_RULES
                    for idx, rule in enumerate(rules[:-1]):
                        to_rule = rules[idx + 1]
                        t0 = time.time()
                        await self._promote_groups(
                            grouped_repo,
                            from_gran=rule.granularity,
                            to_gran=to_rule.granularity,
                            min_old_minutes=rule.min_old_minutes,
                            newest_threshold_minutes=rule.newest_threshold_minutes,
                        )
                        t1 = time.time()
                        logger.info(
                            "TransferGroupingService: promote %d->%d completed in %.2fms",
                            rule.granularity,
                            to_rule.granularity,
                            (t1 - t0) * 1000.0,
                        )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Failed during transfer grouping cycle")

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._settings.grouping_interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def _process_batch(self, transfer_repo: TransferRepository, grouped_repo: TransferGroupedRepository) -> None:
        """Process a small batch of transfers and persist grouped records.

        This is a placeholder to be implemented with actual grouping logic later.
        """
        logger.info("TransferGroupingService: process batch start")

        # Use a fixed 1-minute grouping granularity (do not rely on Settings)
        gran_minutes = 1
        gran_delta = timedelta(minutes=gran_minutes)

        # Get oldest unprocessed transfer
        read_t0 = time.perf_counter()
        result = await transfer_repo._session.execute(
            select(Transfer).where(Transfer.is_processed == False).order_by(Transfer.timestamp.asc()).limit(1)
        )
        oldest = result.scalars().first()
        read_t1 = time.perf_counter()
        logger.debug("_process_batch: read_oldest_from_repo in %.2fms", (read_t1 - read_t0) * 1000.0)

        if oldest is None:
            logger.info("No unprocessed transfers found")
            return

        now = self._to_utc(datetime.now(timezone.utc))
        # If oldest unprocessed transfer is not older than twice the granularity, skip processing
        if self._to_utc(oldest.timestamp) > (now - 2 * gran_delta):
            logger.info("Oldest unprocessed transfer is too recent to process: %s", oldest.timestamp)
            return

        # Window selection per specification:
        # start_window = latest.timestamp
        # end_window = min(start_window + 1 hour, now - gran_delta)
        # round end_window down to granularity
        one_hour = timedelta(hours=1)

        now = self._to_utc(datetime.now(timezone.utc))
        start_window = self._to_utc(oldest.timestamp)
        candidate_end = start_window + one_hour
        limit_end = now - gran_delta
        end_window = candidate_end if candidate_end <= limit_end else limit_end
        # Round end_window down to granularity
        end_window = self._round_down_to_granularity(end_window, gran_minutes)

        # If rounding makes the end_window <= start_window, nothing to do.
        if end_window <= start_window:
            logger.info("Computed end_window <= start_window after rounding: %s <= %s", end_window, start_window)
            return

        # read unprocessed transfers from oldest to newest within window
        read_rows_t0 = time.perf_counter()
        rows = await transfer_repo.list_for_sources_between(None, start_window, end_window)
        rows = [r for r in rows if not r.is_processed]
        rows.sort(key=lambda r: r.timestamp)
        read_rows_t1 = time.perf_counter()
        logger.debug(
            "_process_batch: read_rows_from_repo %d rows in %.2fms",
            0 if rows is None else len(rows),
            (read_rows_t1 - read_rows_t0) * 1000.0,
        )

        if not rows:
            logger.info("No unprocessed transfers in window")
            return

        # bucket by (source, satellite_id, interval_start)
        proc_t0 = time.perf_counter()
        buckets: dict[tuple[str, str, datetime], list] = {}
        for tr in rows:
            # compute interval start aligned to granularity using helper
            ts = tr.timestamp
            interval_start = self._round_down_to_granularity(ts, gran_minutes)
            # store the transfer object only; interval bounds are derived from the key
            key = (tr.source, tr.satellite_id, interval_start)
            buckets.setdefault(key, []).append(tr)

        created: list[TransferGrouped] = []
        processed_ids: list[int] = []

        for (source, satellite_id, interval_start), entries in buckets.items():
            # bucket entries by size_class so we create one TransferGrouped per size class
            size_buckets: dict[str, dict] = {}
            for tr in entries:
                # determine size class as human-friendly string:
                # 1K, 4K, 16K, 64K, 256K, 1M, big (>1M)
                size = tr.size
                if size < 1 * 1024:
                    size_class = '1K'
                elif size < 4 * 1024:
                    size_class = '4K'
                elif size < 16 * 1024:
                    size_class = '16K'
                elif size < 64 * 1024:
                    size_class = '64K'
                elif size < 256 * 1024:
                    size_class = '256K'
                elif size < 1 * 1024 * 1024:
                    size_class = '1M'
                else:
                    size_class = 'big'

                # ensure agg container exists for this size_class
                if size_class not in size_buckets:
                    size_buckets[size_class] = {
                        'size_dl_succ_nor': 0,
                        'size_ul_succ_nor': 0,
                        'size_dl_fail_nor': 0,
                        'size_ul_fail_nor': 0,
                        'size_dl_succ_rep': 0,
                        'size_ul_succ_rep': 0,
                        'size_dl_fail_rep': 0,
                        'size_ul_fail_rep': 0,
                        'count_dl_succ_nor': 0,
                        'count_ul_succ_nor': 0,
                        'count_dl_fail_nor': 0,
                        'count_ul_fail_nor': 0,
                        'count_dl_succ_rep': 0,
                        'count_ul_succ_rep': 0,
                        'count_dl_fail_rep': 0,
                        'count_ul_fail_rep': 0,
                    }

                mode = 'succ' if tr.is_success else 'fail'
                repair = 'rep' if tr.is_repair else 'nor'

                # map to the correct key in the per-size_class agg
                if tr.action == 'DL':
                    key_sum = f"size_dl_{mode}_{repair}"
                    key_count = f"count_dl_{mode}_{repair}"
                else:
                    key_sum = f"size_ul_{mode}_{repair}"
                    key_count = f"count_ul_{mode}_{repair}"

                size_buckets[size_class][key_sum] += tr.size
                size_buckets[size_class][key_count] += 1
                processed_ids.append(tr.id)

            # create a TransferGrouped per size_class
            for sc, agg in size_buckets.items():
                tg = TransferGrouped(
                    source=source,
                    satellite_id=satellite_id,
                    interval_start=interval_start,
                    interval_end=interval_start + gran_delta,
                    size_class=sc,
                    granularity=gran_minutes,
                    **agg,
                )
                created.append(tg)

        # finish processing timing before DB add/mark
        proc_t1 = time.perf_counter()
        logger.debug(
            "_process_batch: processing (bucket/aggregate) completed in %.2fms",
            (proc_t1 - proc_t0) * 1000.0,
        )

        # persist created grouped records and mark the source transfers processed.
        # The outer `async with database.SessionFactory()` already manages a transaction
        # for the session, so starting another `begin()` here raises an error. Use
        # add/flush/commit on the existing session instead.
        add_t0 = time.perf_counter()
        grouped_repo._session.add_all(created)
        # mark processed transfers (modify mapped objects and add them to session)
        for tr in rows:
            if tr.id in processed_ids:
                tr.is_processed = True
                grouped_repo._session.add(tr)
        add_t1 = time.perf_counter()
        logger.debug(
            "_process_batch: add_created_and_mark_processed %d created, %d processed ids in %.2fms",
            len(created),
            len(processed_ids),
            (add_t1 - add_t0) * 1000.0,
        )

        # flush changes and commit the transaction managed by the session context
        # Attempt to flush and commit; on OperationalError (e.g. DB locked/read-only)
        # abort this transformation cycle and roll back so the next run can try again.
        try:
            flush_t0 = time.perf_counter()
            await grouped_repo._session.flush()
            flush_t1 = time.perf_counter()
            logger.debug("_process_batch: flush completed in %.2fms", (flush_t1 - flush_t0) * 1000.0)
        except OperationalError as exc:
            logger.warning("_process_batch: flush failed due to DB error; aborting this cycle: %s", exc)
            try:
                await grouped_repo._session.rollback()
            except Exception:
                logger.exception("Failed to rollback session after flush error")
            return

        try:
            commit_t0 = time.perf_counter()
            await grouped_repo._session.commit()
            commit_t1 = time.perf_counter()
            logger.debug("_process_batch: commit completed in %.2fms", (commit_t1 - commit_t0) * 1000.0)
        except OperationalError as exc:
            logger.warning("_process_batch: commit failed due to DB error; rolling back and aborting this cycle: %s", exc)
            try:
                await grouped_repo._session.rollback()
            except Exception:
                logger.exception("Failed to rollback session after commit error")
            return
        logger.info("Created %d grouped records and processed %d transfers", len(created), len(processed_ids))
    async def _promote_groups(
        self,
        grouped_repo: TransferGroupedRepository,
        from_gran: int,
        to_gran: int,
        min_old_minutes: int,
        newest_threshold_minutes: int,
    ) -> None:
        """Promote grouped records from a finer granularity to a coarser one.

        - Find the oldest record at `from_gran` granularity; it must be at least `min_old_minutes` old.
        - Find the newest record at `from_gran` granularity; if it's older than `newest_threshold_minutes`, finish (nothing to do).
        - Compute endtime = round_down_to_granularity(now - newest_threshold_minutes, to_gran).
        - Read all `from_gran` grouped records with interval_end < endtime.
        - Aggregate them into `to_gran` buckets (by source, satellite_id, interval_start aligned to to_gran).
        - Create new TransferGrouped rows with granularity=to_gran and aggregated counters.
        - Delete the original `from_gran` grouped rows that were promoted.

        This method is parametrized to allow future promotions (e.g., 1->5, 5->60, ...).
        """
        # helpers (reuse inner helpers from process_batch)
        # use class helpers for UTC and rounding

        # Find bounds in from_gran
        read_oldest_t0 = time.perf_counter()
        res_old = await grouped_repo._session.execute(
            select(TransferGrouped).where(TransferGrouped.granularity == from_gran).order_by(TransferGrouped.interval_start.asc()).limit(1)
        )
        oldest = res_old.scalars().first()
        read_oldest_t1 = time.perf_counter()
        logger.debug("_promote_groups: read_oldest_grouped in %.2fms", (read_oldest_t1 - read_oldest_t0) * 1000.0)

        if oldest is None:
            logger.debug("No grouped records at granularity %d", from_gran)
            return

        now = self._to_utc(datetime.now(timezone.utc))
        # oldest must be at least min_old_minutes old
        if self._to_utc(oldest.interval_start) > (now - timedelta(minutes=min_old_minutes)):
            logger.info(
                "Oldest %d-minute grouped record is not old enough to promote (need %d minutes)",
                from_gran,
                min_old_minutes,
            )
            return

        # newest record
        read_newest_t0 = time.perf_counter()
        res_new = await grouped_repo._session.execute(
            select(TransferGrouped).where(TransferGrouped.granularity == from_gran).order_by(TransferGrouped.interval_start.desc()).limit(1)
        )
        newest = res_new.scalars().first()
        read_newest_t1 = time.perf_counter()
        logger.debug("_promote_groups: read_newest_grouped in %.2fms", (read_newest_t1 - read_newest_t0) * 1000.0)
        if newest is None:
            logger.debug("No grouped records at granularity %d", from_gran)
            return

        # if newest is older than newest_threshold_minutes, finish (nothing to do)
        if self._to_utc(newest.interval_start) < (now - timedelta(minutes=newest_threshold_minutes)):
            logger.info(
                "Newest %d-minute grouped record is older than %d minutes; nothing to promote",
                from_gran,
                newest_threshold_minutes,
            )
            return


        # compute endtime: round down (now - newest_threshold_minutes m) to to_gran
        endtime = self._round_down_to_granularity(
            now - timedelta(minutes=newest_threshold_minutes), to_gran
        )

        logger.debug("Promote groups start: %d->%d", from_gran, to_gran)

        # load all from_gran records with interval_start < endtime
        read_rows_t0 = time.perf_counter()
        rows = await grouped_repo.list_for_granularity_before(from_gran, endtime)
        read_rows_t1 = time.perf_counter()
        logger.debug(
            "_promote_groups: read_rows_from_repo %d rows in %.2fms",
            0 if rows is None else len(rows),
            (read_rows_t1 - read_rows_t0) * 1000.0,
        )
        if not rows:
            logger.info("No %d-minute grouped records older than %s to promote", from_gran, endtime)
            return

        proc_t0 = time.perf_counter()
        # bucket into to_gran intervals
        to_delta = timedelta(minutes=to_gran)
        buckets: dict[tuple[str, str, datetime], list] = {}
        for r in rows:
            i_start = r.interval_start
            target_start = self._round_down_to_granularity(i_start, to_gran)
            key = (r.source, r.satellite_id, target_start)
            buckets.setdefault(key, []).append(r)

        created: list[TransferGrouped] = []
        promoted_ids: list[int] = []

        for (source, satellite_id, interval_start), entries in buckets.items():
            # aggregate numeric fields per size_class so promotions preserve size buckets
            size_buckets: dict[str, dict] = {}
            for ent in entries:
                promoted_ids.append(ent.id)
                sc = ent.size_class or ""
                if sc not in size_buckets:
                    size_buckets[sc] = {
                        'size_dl_succ_nor': 0,
                        'size_ul_succ_nor': 0,
                        'size_dl_fail_nor': 0,
                        'size_ul_fail_nor': 0,
                        'size_dl_succ_rep': 0,
                        'size_ul_succ_rep': 0,
                        'size_dl_fail_rep': 0,
                        'size_ul_fail_rep': 0,
                        'count_dl_succ_nor': 0,
                        'count_ul_succ_nor': 0,
                        'count_dl_fail_nor': 0,
                        'count_ul_fail_nor': 0,
                        'count_dl_succ_rep': 0,
                        'count_ul_succ_rep': 0,
                        'count_dl_fail_rep': 0,
                        'count_ul_fail_rep': 0,
                    }
                for k in list(size_buckets[sc].keys()):
                    size_buckets[sc][k] += getattr(ent, k, 0) or 0

            # create a TransferGrouped per size_class
            for sc, agg_fields in size_buckets.items():
                tg = TransferGrouped(
                    source=source,
                    satellite_id=satellite_id,
                    interval_start=interval_start,
                    interval_end=interval_start + to_delta,
                    size_class=sc,
                    granularity=to_gran,
                    **agg_fields,
                )
                created.append(tg)

        proc_t1 = time.perf_counter()
        logger.debug(
            "_promote_groups: processing (aggregate) completed in %.2fms",
            (proc_t1 - proc_t0) * 1000.0,
        )

        # persist new grouped rows and delete old ones
        add_t0 = time.perf_counter()
        grouped_repo._session.add_all(created)
        add_t1 = time.perf_counter()
        logger.debug(
            "_promote_groups: add_created %d records in %.2fms",
            len(created),
            (add_t1 - add_t0) * 1000.0,
        )

        # delete promoted source rows
        del_t0 = time.perf_counter()
        await grouped_repo.delete_many_by_ids(promoted_ids)
        del_t1 = time.perf_counter()
        logger.debug(
            "_promote_groups: delete_promoted %d ids in %.2fms",
            len(promoted_ids),
            (del_t1 - del_t0) * 1000.0,
        )

        # Attempt to flush/commit; on DB OperationalError, roll back and abort
        try:
            flush_t0 = time.perf_counter()
            await grouped_repo._session.flush()
            flush_t1 = time.perf_counter()
            logger.debug("_promote_groups: flush completed in %.2fms", (flush_t1 - flush_t0) * 1000.0)
        except OperationalError as exc:
            logger.warning("_promote_groups: flush failed due to DB error; aborting promotion: %s", exc)
            try:
                await grouped_repo._session.rollback()
            except Exception:
                logger.exception("_promote_groups: Failed to rollback after flush error")
            return

        try:
            commit_t0 = time.perf_counter()
            await grouped_repo._session.commit()
            commit_t1 = time.perf_counter()
            logger.debug("_promote_groups: commit completed in %.2fms", (commit_t1 - commit_t0) * 1000.0)
        except OperationalError as exc:
            logger.warning("_promote_groups: commit failed due to DB error; rolling back and aborting promotion: %s", exc)
            try:
                await grouped_repo._session.rollback()
            except Exception:
                logger.exception("_promote_groups: Failed to rollback after commit error")
            return

        logger.info(
            "Promoted %d records from %d->%d minute granularity into %d records",
            len(promoted_ids),
            from_gran,
            to_gran,
            len(created),
        )

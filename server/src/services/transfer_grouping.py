from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Optional

from .. import database
from ..config import Settings
from ..core.time import getVirtualNow
from datetime import timedelta, datetime, timezone
from math import floor
from sqlalchemy import select
from ..models import Transfer, TransferGrouped
from ..repositories.transfers import TransferRepository
from ..repositories.transfer_grouped import TransferGroupedRepository

logger = logging.getLogger(__name__)


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

                    # Process transfers into 1-minute grouped aggregates.
                    await self._process_batch(transfer_repo, grouped_repo)
                    # Promote 1-minute groups into 5-minute groups when possible.
                    await self._promote_groups(grouped_repo, from_gran=1, to_gran=5, min_old_minutes=120, newest_threshold_minutes=90)
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
        result = await transfer_repo._session.execute(
            select(Transfer).where(Transfer.is_processed == False).order_by(Transfer.timestamp.asc()).limit(1)
        )
        oldest = result.scalars().first()

        if oldest is None:
            logger.info("No unprocessed transfers found")
            return

        now = self._to_utc(getVirtualNow(self._settings))
        # If oldest unprocessed transfer is not older than twice the granularity, skip processing
        if self._to_utc(oldest.timestamp) > (now - 2 * gran_delta):
            logger.info("Oldest unprocessed transfer is too recent to process: %s", oldest.timestamp)
            return

        # Window selection per specification:
        # start_window = latest.timestamp
        # end_window = min(start_window + 1 hour, now - gran_delta)
        # round end_window down to granularity
        one_hour = timedelta(hours=1)

        now = self._to_utc(getVirtualNow(self._settings))
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
        rows = await transfer_repo.list_for_sources_between(None, start_window, end_window)
        rows = [r for r in rows if not r.is_processed]
        rows.sort(key=lambda r: r.timestamp)

        if not rows:
            logger.info("No unprocessed transfers in window")
            return

        # bucket by (source, satellite_id, interval_start)
        buckets: dict[tuple[str, str, datetime], list] = {}
        for tr in rows:
            # compute interval start aligned to granularity using helper
            ts = tr.timestamp
            interval_start = self._round_down_to_granularity(ts, gran_minutes)
            interval_end = interval_start + gran_delta
            key = (tr.source, tr.satellite_id, interval_start)
            buckets.setdefault(key, []).append((tr, interval_start, interval_end))

        created: list[TransferGrouped] = []
        processed_ids: list[int] = []

        for (source, satellite_id, interval_start), entries in buckets.items():
            # initialize counters
            agg = {
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
            size_class = ""
            for tr, i_start, i_end in entries:
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

                prefix = 'size_' if tr.action == 'DL' else 'size_ul_' if tr.action == 'UL' else 'size_'
                mode = 'succ' if tr.is_success else 'fail'
                repair = 'rep' if tr.is_repair else 'nor'

                # map to the correct key in agg
                if tr.action == 'DL':
                    key_sum = f"size_dl_{mode}_{repair}"
                    key_count = f"count_dl_{mode}_{repair}"
                else:
                    key_sum = f"size_ul_{mode}_{repair}"
                    key_count = f"count_ul_{mode}_{repair}"

                agg[key_sum] += tr.size
                agg[key_count] += 1
                processed_ids.append(tr.id)

            tg = TransferGrouped(
                source=source,
                satellite_id=satellite_id,
                interval_start=interval_start,
                interval_end=interval_start + gran_delta,
                size_class=size_class,
                granularity=gran_minutes,
                **agg,
            )
            created.append(tg)

        # persist created grouped records and mark the source transfers processed.
        # The outer `async with database.SessionFactory()` already manages a transaction
        # for the session, so starting another `begin()` here raises an error. Use
        # add/flush/commit on the existing session instead.
        grouped_repo._session.add_all(created)
        # mark processed transfers (modify mapped objects and add them to session)
        for tr in rows:
            if tr.id in processed_ids:
                tr.is_processed = True
                grouped_repo._session.add(tr)

        # flush changes and commit the transaction managed by the session context
        await grouped_repo._session.flush()
        await grouped_repo._session.commit()

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
        res_old = await grouped_repo._session.execute(
            select(TransferGrouped).where(TransferGrouped.granularity == from_gran).order_by(TransferGrouped.interval_start.asc()).limit(1)
        )
        oldest = res_old.scalars().first()

        if oldest is None:
            logger.debug("No grouped records at granularity %d", from_gran)
            return

        now = self._to_utc(getVirtualNow(self._settings))
        # oldest must be at least min_old_minutes old
        if self._to_utc(oldest.interval_start) > (now - timedelta(minutes=min_old_minutes)):
            logger.info(
                "Oldest %d-minute grouped record is not old enough to promote (need %d minutes)",
                from_gran,
                min_old_minutes,
            )
            return

        # newest record
        res_new = await grouped_repo._session.execute(
            select(TransferGrouped).where(TransferGrouped.granularity == from_gran).order_by(TransferGrouped.interval_start.desc()).limit(1)
        )
        newest = res_new.scalars().first()
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

        # load all from_gran records with interval_start < endtime
        rows = await grouped_repo.list_for_granularity_before(from_gran, endtime)
        if not rows:
            logger.info("No %d-minute grouped records older than %s to promote", from_gran, endtime)
            return

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
            # aggregate numeric fields; TransferGrouped has many counters — sum any int fields
            agg_fields = {
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
            size_class = ""
            for ent in entries:
                promoted_ids.append(ent.id)
                # prefer the largest size_class seen (heuristic); store last non-empty
                if ent.size_class:
                    size_class = ent.size_class
                for k in list(agg_fields.keys()):
                    agg_fields[k] += getattr(ent, k, 0) or 0

            tg = TransferGrouped(
                source=source,
                satellite_id=satellite_id,
                interval_start=interval_start,
                interval_end=interval_start + to_delta,
                size_class=size_class,
                granularity=to_gran,
                **agg_fields,
            )
            created.append(tg)

        # persist new grouped rows and delete old ones
        grouped_repo._session.add_all(created)
        # delete promoted source rows
        await grouped_repo.delete_many_by_ids(promoted_ids)

        await grouped_repo._session.flush()
        await grouped_repo._session.commit()

        logger.info("Promoted %d records from %d->%d minute granularity into %d records", len(promoted_ids), from_gran, to_gran, len(created))

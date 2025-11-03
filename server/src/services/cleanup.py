from __future__ import annotations

import asyncio
import contextlib
from server.src.core.logging import get_logger
from datetime import datetime, timedelta, timezone
from typing import Optional

from .. import database
from ..config import Settings
from ..repositories.log_entries import LogEntryRepository
from ..repositories.transfers import TransferRepository
from ..repositories.transfer_grouped import TransferGroupedRepository

logger = get_logger(__name__)


class CleanupService:
    """Periodically removes stale records from the database."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="log-cleanup")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            # Compute per-table cutoffs using configured per-table or global retention
            now = datetime.now(timezone.utc)
            cutoff_logs = now - timedelta(minutes=self._settings.get_retention_minutes("log_entries"))
            cutoff_transfers = now - timedelta(minutes=self._settings.get_retention_minutes("transfers"))
            cutoff_grouped = now - timedelta(minutes=self._settings.get_retention_minutes("transfer_grouped"))
            try:
                async with database.SessionFactory() as session:
                    log_repository = LogEntryRepository(session)
                    transfer_repository = TransferRepository(session)
                    grouped_repository = TransferGroupedRepository(session)

                    import time

                    # Time each deletion step so operators can see which stages take
                    # the most time during cleanup cycles. Use wall-clock `time.time()`
                    # which is sufficient for coarse measurements (milliseconds).
                    t0 = time.time()
                    try:
                        deleted_logs = await log_repository.delete_older_than(cutoff_logs)
                    except Exception:  # noqa: BLE001
                        deleted_logs = 0
                        logger.exception("Failed deleting expired log entries")
                    t_logs = (time.time() - t0) * 1000.0
                    logger.info("Deleted %d expired log entries in %.2fms", deleted_logs, t_logs)

                    t0 = time.time()
                    try:
                        deleted_transfers = await transfer_repository.delete_older_than(cutoff_transfers)
                    except Exception:  # noqa: BLE001
                        deleted_transfers = 0
                        logger.exception("Failed deleting expired transfers")
                    t_transfers = (time.time() - t0) * 1000.0
                    logger.info("Deleted %d expired transfers in %.2fms", deleted_transfers, t_transfers)

                    t0 = time.time()
                    try:
                        deleted_grouped = await grouped_repository.delete_older_than(cutoff_grouped)
                    except Exception:  # noqa: BLE001
                        deleted_grouped = 0
                        logger.exception("Failed deleting expired grouped transfer aggregates")
                    t_grouped = (time.time() - t0) * 1000.0
                    logger.info(
                        "Deleted %d expired grouped transfer aggregates in %.2fms",
                        deleted_grouped,
                        t_grouped,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Failed during cleanup cycle")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._settings.cleanup_interval_seconds
                )
            except asyncio.TimeoutError:
                continue

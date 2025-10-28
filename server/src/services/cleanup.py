from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import timedelta
from typing import Optional

from .. import database
from ..config import Settings
from ..core.time import getVirtualNow
from ..repositories.log_entries import LogEntryRepository
from ..repositories.transfers import TransferRepository

logger = logging.getLogger(__name__)


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
            cutoff = getVirtualNow(self._settings) - timedelta(minutes=self._settings.retention_minutes)
            try:
                async with database.SessionFactory() as session:
                    log_repository = LogEntryRepository(session)
                    transfer_repository = TransferRepository(session)

                    deleted_logs = await log_repository.delete_older_than(cutoff)
                    deleted_transfers = await transfer_repository.delete_older_than(cutoff)

                    if deleted_logs:
                        logger.info("Deleted %d expired log entries", deleted_logs)
                    if deleted_transfers:
                        logger.info("Deleted %d expired transfers", deleted_transfers)
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

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from ..config import Settings
from ..database import SessionFactory
from ..repositories.log_entries import LogEntryRepository

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
            cutoff = datetime.utcnow() - timedelta(minutes=self._settings.retention_minutes)
            try:
                async with SessionFactory() as session:
                    repository = LogEntryRepository(session)
                    deleted = await repository.delete_older_than(cutoff)
                    if deleted:
                        logger.info("Deleted %d expired log entries", deleted)
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

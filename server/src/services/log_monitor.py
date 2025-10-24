from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List

import aiofiles

from ..config import Settings
from ..database import SessionFactory
from ..repositories.log_entries import LogEntryRepository
from ..schemas import LogEntryCreate

logger = logging.getLogger(__name__)


class LogMonitorService:
    """Stream new lines from configured log files into the persistence layer."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tasks: List[asyncio.Task] = []
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if not self._settings.log_sources:
            logger.warning("Log monitoring started without any log sources configured.")
            return

        for path in self._settings.sanitized_log_sources:
            task = asyncio.create_task(self._watch_file(path), name=f"log-watch:{path}")
            self._tasks.append(task)

    async def stop(self) -> None:
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _watch_file(self, path: Path) -> None:
        buffer: List[LogEntryCreate] = []

        while not self._stopping.is_set():
            try:
                async with aiofiles.open(path, mode="r") as handle:
                    await handle.seek(0, 2)  # jump to end of file

                    while not self._stopping.is_set():
                        line = await handle.readline()
                        if line:
                            # TODO: replace the raw content storage with structured parsing rules.
                            buffer.append(
                                LogEntryCreate(source=str(path), content=line.rstrip("\n"))
                            )
                            if len(buffer) >= self._settings.log_batch_size:
                                await self._flush(buffer)
                        else:
                            if buffer:
                                await self._flush(buffer)
                            await asyncio.wait_for(
                                self._stopping.wait(), timeout=self._settings.log_poll_interval
                            )
            except asyncio.TimeoutError:
                continue
            except FileNotFoundError:
                logger.error("Log file not found: %s", path)
                await asyncio.sleep(self._settings.log_poll_interval)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected error while monitoring log file: %s", path)
                await asyncio.sleep(self._settings.log_poll_interval)

        if buffer:
            await self._flush(buffer)

    async def _flush(self, buffer: List[LogEntryCreate]) -> None:
        if not buffer:
            return

        async with SessionFactory() as session:
            repository = LogEntryRepository(session)
            await repository.create_many(buffer)
        buffer.clear()

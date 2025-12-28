from __future__ import annotations

import asyncio
import contextlib
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List

import httpx

from server.src.core.logging import get_logger
from ..config import Settings, IP24Definition

logger = get_logger(__name__)


@dataclass
class IP24State:
    expected_instances: int
    last_instances: Optional[int] = None
    last_checked_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None


class IP24Service:
    """Poll storjnet.info neighbors API for configured IP targets."""

    def __init__(self, settings: Settings, *, client: Optional[httpx.AsyncClient] = None) -> None:
        self._settings = settings
        self._targets: List[IP24Definition] = settings.parsed_ip24
        self._states: Dict[str, IP24State] = {}
        self._client = client
        self._owns_client = client is None
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if not self._targets:
            logger.info("IP24Service start skipped: no ip24 targets configured")
            return

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)

        async with self._lock:
            for target in self._targets:
                self._states[target.ip] = IP24State(expected_instances=target.expected_instances)

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="ip24-service")
        logger.info("Started IP24Service for %d target(s)", len(self._targets))

    async def stop(self) -> None:
        if not getattr(self, "_task", None):
            return
        self._stop_event.set()
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.info("Stopped IP24Service")

    async def _run(self) -> None:
        interval_seconds = 900  # check roughly every 15 minutes for due targets
        while not self._stop_event.is_set():
            try:
                await self._poll_all()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Unhandled error in IP24Service loop")

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def _poll_all(self) -> None:
        if not self._targets:
            return
        for target in self._targets:
            await self._maybe_poll_target(target)

    async def _maybe_poll_target(self, target: IP24Definition) -> None:
        now = datetime.now(timezone.utc)
        async with self._lock:
            state = self._states.get(target.ip)
            if state is None:
                state = IP24State(expected_instances=target.expected_instances)
                self._states[target.ip] = state

            # Enforce intervals
            if state.last_success_at and now - state.last_success_at < timedelta(hours=24):
                return
            if state.last_error and state.last_checked_at and now - state.last_checked_at < timedelta(hours=1):
                return
            state.last_checked_at = now

        await self._poll_target(target, state)

    async def _poll_target(self, target: IP24Definition, state: IP24State) -> None:
        client = self._client
        if client is None:
            return
        resolved_ip = await self._resolve_ipv4(target.ip)
        if not resolved_ip:
            await self._record_failure(target.ip, "DNS resolution failed")
            logger.error("IP24 DNS resolution failed for %s", target.ip)
            return

        url = f"https://storjnet.info/api/neighbors/{resolved_ip}"
        try:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not payload.get("ok"):
                raise ValueError("storjnet returned not ok")
            result = payload.get("result") or {}
            count = result.get("count") if isinstance(result, dict) else None
            if not isinstance(count, int):
                raise ValueError("storjnet result count missing or invalid")
        except Exception as exc:  # noqa: BLE001
            logger.warning("IP24 poll failed for %s: %s", target.ip, exc, exc_info=True)
            await self._record_failure(target.ip, str(exc))
            return

        async with self._lock:
            state.last_instances = count
            state.last_success_at = datetime.now(timezone.utc)
            state.last_error = None

    async def _record_failure(self, ip: str, error: str) -> None:
        async with self._lock:
            state = self._states.get(ip)
            if state is None:
                return
            state.last_error = error
            state.last_instances = None

    async def _resolve_ipv4(self, host: str) -> Optional[str]:
        try:
            loop = asyncio.get_running_loop()
            infos = await loop.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
            if infos:
                return infos[0][4][0]
        except Exception as exc:  # noqa: BLE001
            logger.error("IPv4 resolution failed for %s: %s", host, exc, exc_info=True)
        return None

    async def get_status(self) -> Dict[str, dict]:
        async with self._lock:
            snapshot = {}
            for ip, state in self._states.items():
                snapshot[ip] = {
                    "valid": state.last_error is None and state.last_instances is not None,
                    "expectedInstances": state.expected_instances,
                    "instances": state.last_instances,
                }
            return snapshot

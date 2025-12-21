from __future__ import annotations

import asyncio
import contextlib
import urllib.parse
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

import httpx

from server.src.core.logging import get_logger

from ..config import Settings, SourceDefinition
from .. import database

from ..repositories.held_amounts import HeldAmountRepository
from ..repositories.paystubs import PaystubRepository
from ..repositories.disk_usage import DiskUsageRepository
from ..models import SatelliteUsage, HeldAmount, Paystub, DiskUsage

logger = get_logger(__name__)

@dataclass
class SatelliteInfo:
    """Runtime satellite information for a node."""

    held_amount: Optional[float] = None


@dataclass
class NodeState:
    """Public per-node state.

    This holds information that consumers may read (joined_at, payout
    estimates, etc.). Runtime-only fields used by the poller are stored in
    the nested `runtime` attribute.
    """
    name: str
    # Private runtime state used by the poller and mutated during processing
    runtime: "NodeRuntime"
    # Public node data (separated into its own structure so callers can
    # safely read a compact representation without touching runtime fields).
    data: "NodeData" = None


@dataclass
class NodeData:
    """Public per-node data that consumers may read.

    This deliberately excludes the node name (it's stored on NodeState) and
    avoids including runtime-only fields.
    """
    joined_at: Optional[datetime] = None
    # Estimated payout related state
    last_estimated_payout_at: Optional[datetime] = None
    estimated_payout: Optional[float] = None
    held_back_payout: Optional[float] = None
    download_payout: Optional[float] = None
    repair_payout: Optional[float] = None
    disk_payout: Optional[float] = None
    # Sum of held amounts across satellites (optional)
    total_held_amount: Optional[float] = None
    # Timestamp of the last successful held-history fetch
    last_held_history_at: Optional[datetime] = None
    # Optional mapping of satellite id -> vettedAt timestamp (or None)
    vetting_date: Optional[dict[str, Optional[datetime]]] = None


@dataclass
class NodeRuntime:
    """Private runtime fields used by the poller (not part of public state)."""
    url: str
    last_fetched_at: Optional[datetime] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    task: Optional[asyncio.Task] = None
    # cached satellite info keyed by satellite id
    satellites: dict[str, SatelliteInfo] = field(default_factory=dict)
    last_paystub_at: Optional[datetime] = None
    last_paystub_period: Optional[str] = None
    last_satellite_details_at: Optional[datetime] = None


class NodeApiService:
    """Background poller that fetches JSON payloads from configured nodeapi endpoints.

    Each configured nodeapi source is polled in its own asyncio.Task so a slow
    or failing endpoint doesn't delay other nodes. Per-node runtime state is
    stored in `self._states` keyed by node name.
    """

    def __init__(self, settings: Settings, *, client: Optional[httpx.AsyncClient] = None) -> None:
        self._settings = settings
        # Map node name -> NodeState
        self._states: Dict[str, NodeState] = {}
        self._stop_event = asyncio.Event()
        self._client = client
        self._owns_client = client is None
        # Protects _states mutations
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        # discover nodeapi sources and ensure we have a task per node
        sources = self._nodeapi_sources()
        if not sources:
            logger.debug("NodeApiService start skipped: no nodeapi endpoints configured")
            return

        if self._client is None:
            # Follow redirects so servers that redirect to a trailing-slash
            # URL (e.g. /api/sno -> /api/sno/) are handled transparently.
            self._client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)

        self._stop_event.clear()

        # Create NodeState entries and spawn tasks for each node
        async with self._lock:
            for src in sources:
                if src.name in self._states:
                    # update URL if it changed
                    self._states[src.name].runtime.url = src.nodeapi or self._states[src.name].runtime.url
                    continue
                assert src.nodeapi is not None
                runtime = NodeRuntime(url=src.nodeapi)
                state = NodeState(name=src.name, runtime=runtime, data=NodeData())
                self._states[src.name] = state
                runtime.task = asyncio.create_task(self._node_task(state), name=f"nodeapi-{src.name}")

        logger.info("Started nodeapi poller for %d endpoint(s)", len(self._states))

    async def stop(self) -> None:
        self._stop_event.set()
        # cancel per-node tasks
        async with self._lock:
            tasks = [s.runtime.task for s in self._states.values() if s.runtime.task]
            for t in tasks:
                if t:
                    t.cancel()

        for t in tasks:
            if t:
                with contextlib.suppress(asyncio.CancelledError):
                    await t

        # clear states
        async with self._lock:
            self._states.clear()

        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.info("Stopped nodeapi poller")

    async def _run(self) -> None:
        # Legacy single-run loop retained for compatibility, but primary
        # operation uses per-node tasks. Keep this as a no-op loop so older
        # callers that expect a background task still function.
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=3600)
            except asyncio.TimeoutError:
                continue

    async def _node_task(self, state: NodeState) -> None:
        """Task loop for an individual node.

        The loop polls the nodeapi endpoint at `nodeapi_poll_interval_seconds`.
        On error it increments `consecutive_failures` and records the last
        error message; on success it resets the failure counter and stores the
        payload and timestamp.
        """
        client = await self._ensure_client()
        if client is None:
            return

        interval = max(1, int(self._settings.nodeapi_poll_interval_seconds))
        while not self._stop_event.is_set():
            try:
                await self._poll_node(client, state)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Unhandled error in node task for %s", state.name)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def _poll_node(self, client: httpx.AsyncClient, state: NodeState) -> None:
        # `state.url` is treated as the base address for the node; callers may
        # extend with a specific API path when invoking `_fetch_node_payload`.
        logger.debug("Polling nodeapi endpoint for node '%s': %s", state.name, state.runtime.url)

        # Process the canonical /api/sno payload which may contain per-satellite
        # information (including satellite ids). This helper mirrors the
        # pattern used by the other processors and may populate the
        # state.runtime.held_amounts cache by reading from the HeldAmount table.
        sno_ok = await self._process_sno(client, state)
        if not sno_ok:
            async with self._lock:
                state.runtime.consecutive_failures += 1
                state.runtime.last_error = "payload processing failed"
            logger.debug(
                "Node '%s' /api/sno processing failed, consecutive failures=%d",
                state.name,
                state.runtime.consecutive_failures,
            )
            return

        # Process sno satellites payload (fetching happens inside the
        # processing helper). The helper returns True on success.
        satellites_ok = await self._process_sno_satellites(client, state)
        if not satellites_ok:
            # Processing decided this payload cannot be used; mark as a
            # failure and return.
            async with self._lock:
                state.runtime.consecutive_failures += 1
                state.runtime.last_error = "payload processing failed"
            logger.debug(
                "Node '%s' payload processing failed, consecutive failures=%d",
                state.name,
                state.runtime.consecutive_failures,
            )
            return

        satellite_details_ok = await self._process_sno_satellite_details(client, state)
        if not satellite_details_ok:
            async with self._lock:
                state.runtime.consecutive_failures += 1
                state.runtime.last_error = "satellite-details processing failed"
            logger.debug(
                "Node '%s' satellite-details processing failed, consecutive failures=%d",
                state.name,
                state.runtime.consecutive_failures,
            )
            return

        # Process held-history endpoint which may provide per-satellite held
        # amounts directly. This mirrors other processing helpers: return
        # early on failure and update runtime state on success.
        held_ok = await self._process_held_history(client, state)
        if not held_ok:
            async with self._lock:
                state.runtime.consecutive_failures += 1
                state.runtime.last_error = "held-history processing failed"
            logger.debug(
                "Node '%s' /api/heldamount/held-history processing failed, consecutive failures=%d",
                state.name,
                state.runtime.consecutive_failures,
            )
            return

        # Optionally refresh estimated payout if stale.
        payout_ok = await self._fetch_estimated_payout(client, state)
        if not payout_ok:
            # Treat payout fetch failures like other node failures: bump the
            # failure counter, record a last_error and skip processing the
            # satellites payload this cycle.
            async with self._lock:
                state.runtime.consecutive_failures += 1
                state.runtime.last_error = "estimated-payout fetch failed"
            logger.debug(
                "Node '%s' estimated-payout fetch failed, consecutive failures=%d",
                state.name,
                state.runtime.consecutive_failures,
            )
            return

        paystubs_ok = await self._fetch_paystubs(client, state)
        if not paystubs_ok:
            async with self._lock:
                state.runtime.consecutive_failures += 1
                state.runtime.last_error = "paystubs fetch failed"
            logger.debug(
                "Node '%s' paystubs fetch failed, consecutive failures=%d",
                state.name,
                state.runtime.consecutive_failures,
            )
            return

        # All good — update node state in a single locked section.
        fetched_at = datetime.now(timezone.utc)
        async with self._lock:
            state.runtime.last_fetched_at = fetched_at
            state.runtime.consecutive_failures = 0
            state.runtime.last_error = None

        logger.debug("Stored nodeapi snapshot for node '%s'", state.name)

    async def _fetch_paystubs(self, client: httpx.AsyncClient, state: NodeState) -> bool:
        """Placeholder paystubs fetch gated by its own refresh interval."""
        interval = max(1, int(self._settings.nodeapi_paystub_interval_seconds))
        now = datetime.now(timezone.utc)
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_month_day = current_month_start - timedelta(days=1)
        expected_period = f"{previous_month_day.year:04d}-{previous_month_day.month:02d}"
        logger.debug("Expected paystub period for node %s is %s", state.name, expected_period)
        async with self._lock:
            last_at = state.runtime.last_paystub_at
            existing_period = state.runtime.last_paystub_period
        if last_at and (now - last_at).total_seconds() < interval:
            return True

        latest_period: Optional[str] = existing_period
        if latest_period is None:
            try:
                async with database.SessionFactory() as session:
                    repo = PaystubRepository(session)
                    db_period = await repo.get_latest_period(state.name)
                    if db_period is not None:
                        latest_period = db_period
            except Exception:
                logger.exception("Failed to read paystub records for node %s", state.name)
                return False

        if latest_period and latest_period >= expected_period:
            async with self._lock:
                state.runtime.last_paystub_at = now
            return True

        if latest_period is None:
            from_period = "2000-01"
        else:
            try:
                latest_year, latest_month = latest_period.split("-")
                year = int(latest_year)
                month = int(latest_month)
                month += 1
                if month > 12:
                    month = 1
                    year += 1
                from_period = f"{year:04d}-{month:02d}"
            except Exception:
                logger.debug("Failed to parse latest paystub period '%s' for node %s", latest_period, state.name)
                from_period = "2000-01"

        path = f"/api/heldamount/paystubs/{from_period}/{expected_period}"
        success, payload = await self._fetch_node_payload(client, state, path)
        if not success:
            return False

        if payload is None:
            logger.debug("No new paystub data for node %s", state.name)
            async with self._lock:
                state.runtime.last_paystub_at = now
            return True

        if not isinstance(payload, list):
            logger.debug("Unexpected paystub payload shape for node %s: %s", state.name, type(payload))
            return False

        records: list[Paystub] = []
        max_processed_period: Optional[str] = None

        for item in payload:
            if not isinstance(item, dict):
                continue

            satellite_id = item.get("satelliteId")
            period_value = item.get("period")
            created_value = item.get("created")
            if not isinstance(satellite_id, str) or not isinstance(period_value, str) or not isinstance(created_value, str):
                continue

            created_str = created_value
            if created_str.endswith("Z"):
                created_str = created_str[:-1] + "+00:00"
            try:
                created_dt = datetime.fromisoformat(created_str)
            except ValueError:
                logger.debug("Failed to parse paystub created timestamp '%s' for node %s", created_value, state.name)
                continue

            def to_float(value: Any) -> float:
                try:
                    return float(value)
                except Exception:
                    return 0.0

            record = Paystub(
                source=state.name,
                satellite_id=satellite_id,
                period=period_value,
                created=created_dt,
                usage_at_rest=to_float(item.get("usageAtRest")),
                usage_get=to_float(item.get("usageGet")),
                usage_put=to_float(item.get("usagePut")),
                usage_get_repair=to_float(item.get("usageGetRepair")),
                usage_put_repair=to_float(item.get("usagePutRepair")),
                usage_get_audit=to_float(item.get("usageGetAudit")),
                comp_at_rest=to_float(item.get("compAtRest")) / 1e6,
                comp_get=to_float(item.get("compGet")) / 1e6,
                comp_put=to_float(item.get("compPut")) / 1e6,
                comp_get_repair=to_float(item.get("compGetRepair")) / 1e6,
                comp_put_repair=to_float(item.get("compPutRepair")) / 1e6,
                comp_get_audit=to_float(item.get("compGetAudit")) / 1e6,
                surge_percent=to_float(item.get("surgePercent")),
                held=to_float(item.get("held")) / 1e6,
                owed=to_float(item.get("owed")) / 1e6,
                disposed=to_float(item.get("disposed")) / 1e6,
                paid=to_float(item.get("paid")) / 1e6,
                distributed=to_float(item.get("distributed")) / 1e6,
            )
            records.append(record)

            if max_processed_period is None or period_value > max_processed_period:
                max_processed_period = period_value

        if not records:
            logger.debug("No valid paystub entries to persist for node %s", state.name)
            async with self._lock:
                state.runtime.last_paystub_at = now
            return True

        try:
            async with database.SessionFactory() as session:
                for rec in records:
                    await session.merge(rec)
                await session.commit()
        except Exception:
            logger.exception("Failed to persist paystub records for node %s", state.name)
            return False

        logger.debug(
            "Persisted %d paystub record(s) for node %s (max period=%s)",
            len(records),
            state.name,
            max_processed_period,
        )

        async with self._lock:
            state.runtime.last_paystub_at = now
            if max_processed_period is not None:
                state.runtime.last_paystub_period = max_processed_period
        return True

    async def _fetch_estimated_payout(self, client: httpx.AsyncClient, state: NodeState) -> bool:
        """Fetch /api/sno/estimated-payout if last fetch is older than configured interval.

        Returns True on successful fetch + processing, False otherwise. Updates
        payout-related fields on the NodeState under lock. Non-fatal on errors:
        leave previous values intact and return False.
        """
        # Decide whether we should query the payout endpoint
        interval = max(1, int(self._settings.nodeapi_estimated_payout_interval_seconds))
        now = datetime.now(timezone.utc)
        if state.data.last_estimated_payout_at and (now - state.data.last_estimated_payout_at).total_seconds() < interval:
            return True

        success, payload = await self._fetch_node_payload(client, state, "/api/sno/estimated-payout")
        if not success or not payload:
            return False

        # Parse expected numeric fields safely. The endpoint uses cents, divide by 100.
        try:
            current_month = payload.get("currentMonth", {}) if isinstance(payload, dict) else {}
            estimated = payload.get("currentMonthExpectations")
            held = current_month.get("held")
            download = current_month.get("egressBandwidthPayout")
            repair = current_month.get("egressRepairAuditPayout")
            disk = current_month.get("diskSpacePayout")

            def to_amount(v: Any) -> Optional[float]:
                if v is None:
                    return None
                try:
                    return float(v) / 100.0
                except Exception:
                    return None

            est_val = to_amount(estimated)
            held_val = to_amount(held)
            download_val = to_amount(download)
            repair_val = to_amount(repair)
            disk_val = to_amount(disk)

            async with self._lock:
                state.data.last_estimated_payout_at = now
                state.data.estimated_payout = est_val
                state.data.held_back_payout = held_val
                state.data.download_payout = download_val
                state.data.repair_payout = repair_val
                state.data.disk_payout = disk_val
            return True
        except Exception:
            logger.debug("Failed to parse estimated-payout response for node %s: %s", state.name, payload)
            return False
        return False

    async def _process_sno_satellites(self, client: httpx.AsyncClient, state: NodeState) -> bool:
        """Fetch and normalize the /api/sno/satellites payload.

        Returns True on success, False on failure. On success `state.joined_at`
        may be updated when the payload contains `earliestJoinedAt`.
        """
        success, payload = await self._fetch_node_payload(client, state, "/api/sno/satellites")
        if not success or not payload:
            return False

        if not isinstance(payload, dict):
            return False

        # If the payload contains an `earliestJoinedAt` property, try to parse
        # it as an ISO-8601 timestamp and store it on the NodeState.
        earliest = payload.get("earliestJoinedAt")
        if earliest:
            try:
                ts = str(earliest)
                if ts.endswith("Z"):
                    ts = ts[:-1] + "+00:00"
                joined_dt = datetime.fromisoformat(ts)
                async with self._lock:
                    state.data.joined_at = joined_dt
            except Exception:
                logger.debug("Failed to parse earliestJoinedAt for node %s: %s", state.name, earliest)

        return True

    async def _process_sno_satellite_details(self, client: httpx.AsyncClient, state: NodeState) -> bool:
        """Fetch /api/sno/satellite/<id> payloads and persist satellite usage records."""

        interval = max(1, int(self._settings.nodeapi_satellite_details_interval_seconds))
        now = datetime.now(timezone.utc)
        async with self._lock:
            last_at = state.runtime.last_satellite_details_at
            satellite_ids = list(state.runtime.satellites.keys())

        if last_at and (now - last_at).total_seconds() < interval:
            return True

        if not satellite_ids:
            async with self._lock:
                state.runtime.last_satellite_details_at = now
            return True

        now = datetime.now(timezone.utc)
        period = now.date().isoformat()
        to_persist: list[SatelliteUsage] = []

        for satellite_id in satellite_ids:
            logger.debug("Processing satellite details for node %s satellite %s", state.name, satellite_id)
            encoded_id = urllib.parse.quote(satellite_id, safe="")
            path = f"/api/sno/satellite/{encoded_id}"
            success, payload = await self._fetch_node_payload(client, state, path)
            if not success or payload is None:
                logger.warning("Satellite details fetch failed for node %s satellite %s", state.name, satellite_id)
                return False
            if not isinstance(payload, dict):
                logger.warning("Satellite details payload was not an object for node %s satellite %s", state.name, satellite_id)
                return False

            bandwidth_daily = payload.get("bandwidthDaily")
            if bandwidth_daily is not None and not isinstance(bandwidth_daily, list):
                logger.warning("Satellite details payload had non-list bandwidthDaily for node %s satellite %s", state.name, satellite_id)
                bandwidth_daily = None

            storage_daily = payload.get("storageDaily")
            if storage_daily is not None and not isinstance(storage_daily, list):
                logger.warning("Satellite details payload had non-list storageDaily for node %s satellite %s", state.name, satellite_id)
                storage_daily = None

            def find_entry(entries: Optional[list[dict[str, Any]]]) -> Optional[dict[str, Any]]:
                if not entries:
                    return None
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    interval_start = entry.get("intervalStart")
                    if isinstance(interval_start, str) and interval_start[:10] == period:
                        return entry
                return None

            bandwidth_entry = find_entry(bandwidth_daily)
            storage_entry = find_entry(storage_daily)

            if bandwidth_entry is None and storage_entry is None:
                continue

            def to_int(value: Any) -> int:
                try:
                    return int(value)
                except Exception:
                    return 0

            egress = {}
            ingress = {}
            delete_value = 0
            if bandwidth_entry is not None:
                egress_raw = bandwidth_entry.get("egress")
                ingress_raw = bandwidth_entry.get("ingress")
                egress = egress_raw if isinstance(egress_raw, dict) else {}
                ingress = ingress_raw if isinstance(ingress_raw, dict) else {}
                delete_value = to_int(bandwidth_entry.get("delete"))

            disk_usage_value: Optional[int]
            if storage_entry is None:
                disk_usage_value = None
            else:
                disk_usage_value = to_int(storage_entry.get("atRestTotalBytes"))

            record = SatelliteUsage(
                source=state.name,
                satellite_id=satellite_id,
                period=period,
                dl_usage=to_int(egress.get("usage")),
                dl_repair=to_int(egress.get("repair")),
                dl_audit=to_int(egress.get("audit")),
                ul_usage=to_int(ingress.get("usage")),
                ul_repair=to_int(ingress.get("repair")),
                delete=delete_value,
                disk_usage=disk_usage_value,
            )
            to_persist.append(record)

        if to_persist:
            try:
                async with database.SessionFactory() as session:
                    for record in to_persist:
                        await session.merge(record)
                    await session.commit()
            except Exception:
                logger.exception("Failed to persist SatelliteUsage records for node %s", state.name)
                return False

        async with self._lock:
            state.runtime.last_satellite_details_at = now

        return True

    async def _process_sno(self, client: httpx.AsyncClient, state: NodeState) -> bool:
        """Fetch and process the canonical /api/sno payload.

        This endpoint may contain per-satellite information. When satellite
        ids are found, populate the runtime.held_amounts cache from the
        HeldAmount table for any missing entries.
        """
        success, payload = await self._fetch_node_payload(client, state, "/api/sno")
        if not success or not payload:
            return False

        if not isinstance(payload, dict):
            return False

        # Attempt to extract satellite identifiers from a mapping or a list
        sat_ids: list[str] = []
        satellites_payload = payload.get("satellites")
        vetting_map: dict[str, Optional[datetime]] = {}
        if isinstance(satellites_payload, list):
            for item in satellites_payload:
                if isinstance(item, dict):
                    sid = item.get("id")
                    if isinstance(sid, str):
                        sat_ids.append(sid)
                        # parse vettedAt which may be null
                        vetted_val = item.get("vettedAt")
                        if vetted_val is None:
                            vetting_map[sid] = None
                        else:
                            try:
                                ts = str(vetted_val)
                                if ts.endswith("Z"):
                                    ts = ts[:-1] + "+00:00"
                                vet_dt = datetime.fromisoformat(ts)
                                vetting_map[sid] = vet_dt
                            except Exception:
                                vetting_map[sid] = None

        if sat_ids:
            # Determine which satellite ids we actually need to query while
            # holding the lock to avoid races with other tasks mutating the
            # runtime satellites mapping.
            async with self._lock:
                existing_info = state.runtime.satellites
                existing_ids = set(existing_info.keys())
                for sid in sat_ids:
                    existing_info.setdefault(sid, SatelliteInfo())
                # Ensure vetting_date mapping exists and update entries
                if state.data.vetting_date is None:
                    state.data.vetting_date = {}
                for sid in sat_ids:
                    if sid in vetting_map:
                        state.data.vetting_date[sid] = vetting_map[sid]
            to_query = [sid for sid in sat_ids if sid not in existing_ids]

            if to_query:
                new_values: dict[str, float] = {}
                async with database.SessionFactory() as session:
                    repo = HeldAmountRepository(session)
                    for sid in to_query:
                        try:
                            rec = await repo.get_latest(state.name, sid)
                            if rec is not None:
                                new_values[sid] = rec.amount
                        except Exception:
                            logger.debug("Failed to query HeldAmount for %s/%s", state.name, sid)

                if new_values:
                    # Update the runtime mapping under the lock and refresh
                    # the public total_held_amount so callers reading
                    # NodeData see an up-to-date aggregated value.
                    async with self._lock:
                        for sid, amount in new_values.items():
                            info = state.runtime.satellites.setdefault(sid, SatelliteInfo())
                            info.held_amount = amount
                        # Compute total across known satellites (ignore None).
                        total = 0.0
                        numeric_count = 0
                        for info in state.runtime.satellites.values():
                            value = info.held_amount
                            if value is None:
                                continue
                            try:
                                total += float(value)
                                numeric_count += 1
                            except Exception:
                                continue
                        state.data.total_held_amount = total if numeric_count > 0 else None
                        # Ensure vetting_date mapping exists
                        if state.data.vetting_date is None:
                            state.data.vetting_date = {}

        # Process disk usage snapshot regardless of presence of satellite ids
        disk_payload = payload.get("diskSpace")
        if isinstance(disk_payload, dict):
            def to_int(v: Any) -> int:
                try:
                    return int(v)
                except Exception:
                    return 0

            used = to_int(disk_payload.get("used"))
            available = to_int(disk_payload.get("available"))
            trash = to_int(disk_payload.get("trash"))
            now = datetime.now(timezone.utc)
            period = now.date().isoformat()

            try:
                async with database.SessionFactory() as session:
                    repo = DiskUsageRepository(session)
                    existing = await repo.get_by_source_period(state.name, period)
                    if existing is None:
                        rec = DiskUsage(
                            source=state.name,
                            period=period,
                            max_usage=used,
                            trash_at_max_usage=trash,
                            max_trash=trash,
                            usage_at_max_trash=used,
                            usage_end=used,
                            trash_end=trash,
                            free_end=available,
                            max_usage_at=now,
                            max_trash_at=now,
                        )
                        # Log the full record values being created
                        logger.debug(
                            "Creating DiskUsage record: %s",
                            {
                                "source": rec.source,
                                "period": rec.period,
                                "max_usage": rec.max_usage,
                                "trash_at_max_usage": rec.trash_at_max_usage,
                                "max_trash": rec.max_trash,
                                "usage_at_max_trash": rec.usage_at_max_trash,
                                "usage_end": rec.usage_end,
                                "trash_end": rec.trash_end,
                                "free_end": rec.free_end,
                                "max_usage_at": rec.max_usage_at.isoformat() if rec.max_usage_at else None,
                                "max_trash_at": rec.max_trash_at.isoformat() if rec.max_trash_at else None,
                            },
                        )
                        session.add(rec)
                        await session.flush()
                        await session.commit()
                    else:
                        rec: DiskUsage = existing
                        changed = False
                        if used > (rec.max_usage or 0):
                            rec.max_usage = used
                            rec.trash_at_max_usage = trash
                            rec.max_usage_at = now
                            changed = True
                        if trash > (rec.max_trash or 0):
                            rec.max_trash = trash
                            rec.usage_at_max_trash = used
                            rec.max_trash_at = now
                            changed = True

                        # Only update end-of-period values if they differ
                        if rec.usage_end != used or rec.trash_end != trash or rec.free_end != available:
                            rec.usage_end = used
                            rec.trash_end = trash
                            rec.free_end = available
                            changed = True

                        if changed:
                            logger.debug(
                                "Updated DiskUsage record: %s",
                                {
                                    "source": rec.source,
                                    "period": rec.period,
                                    "max_usage": rec.max_usage,
                                    "trash_at_max_usage": rec.trash_at_max_usage,
                                    "max_trash": rec.max_trash,
                                    "usage_at_max_trash": rec.usage_at_max_trash,
                                    "usage_end": rec.usage_end,
                                    "trash_end": rec.trash_end,
                                    "free_end": rec.free_end,
                                    "max_usage_at": rec.max_usage_at.isoformat() if rec.max_usage_at else None,
                                    "max_trash_at": rec.max_trash_at.isoformat() if rec.max_trash_at else None,
                                },
                            )
                            session.add(rec)
                            await session.flush()
                            await session.commit()
            except Exception:
                logger.exception("Failed to persist DiskUsage record for node %s", state.name)
                return False

        return True

    async def _process_held_history(self, client: httpx.AsyncClient, state: NodeState) -> bool:
        """Fetch and process /api/heldamount/held-history payload.

        The endpoint is expected to return a JSON object mapping satellite ids
        to numeric held amounts, or a list of objects with satellite id and
        amount. On success updates state.runtime.held_amounts and the
        aggregated state.data.total_held_amount under the service lock.
        """
        # Decide whether we should query the held-history endpoint based on
        # the configured interval to avoid excessive requests.
        interval = max(1, int(self._settings.nodeapi_held_history_interval_seconds))
        now = datetime.now(timezone.utc)
        if state.data.last_held_history_at and (now - state.data.last_held_history_at).total_seconds() < interval:
            return True

        # fetch the held-history payload (may be a list)
        success, payload = await self._fetch_node_payload(client, state, "/api/heldamount/held-history")
        if not success or payload is None:
            return False

        # Normalize into a mapping satellite_id -> amount
        mapping: dict[str, float] = {}

        # This endpoint always returns a list of objects; reject other shapes
        if not isinstance(payload, list):
            return False

        for item in payload:
            if not isinstance(item, dict):
                continue
            sid = item.get("satelliteID")
            amt = item.get("totalHeld")

            if isinstance(sid, str):
                try:
                    val = float(amt) / 1000000.0
                    mapping[sid] = val
                except Exception:
                    logger.warning("Non-numeric held amount for node %s satellite %s: %s", state.name, sid, amt)

        if not mapping:
            # nothing to update but it's still a successful fetch
            return True

        # Snapshot existing runtime values under the lock to determine which
        # satellites changed. We intentionally do NOT hold the lock while
        # performing DB writes to avoid blocking the poller.
        async with self._lock:
            existing_snapshot = {
                sid: info.held_amount for sid, info in state.runtime.satellites.items()
            }

        # Determine which satellite values actually changed (including
        # transitions from None->number or number->None). We only persist
        # numeric values into the HeldAmount table (amount is non-nullable).
        to_persist: dict[str, float] = {}
        for sid, new_val in mapping.items():
            prev_val = existing_snapshot.get(sid)
            changed = prev_val is None or prev_val != float(new_val)

            if changed:
                to_persist[sid] = float(new_val)

        # Persist any changed numeric held amounts to the DB without holding
        # the runtime lock. Use a short-lived session and commit.
        if to_persist:
            now = datetime.now(timezone.utc)
            try:
                async with database.SessionFactory() as session:
                    for sid, val in to_persist.items():
                        rec = HeldAmount(
                            source=state.name,
                            satellite_id=sid,
                            timestamp=now,
                            amount=val,
                        )
                        session.add(rec)
                    await session.flush()
                    await session.commit()
            except Exception:
                logger.exception("Failed to persist HeldAmount records for node %s", state.name)
                return False

        # Update the timestamp of the last successful held-history fetch
        async with self._lock:
            state.data.last_held_history_at = now

        # Update runtime mapping under lock and compute total
        async with self._lock:
            for sid, value in mapping.items():
                info = state.runtime.satellites.setdefault(sid, SatelliteInfo())
                info.held_amount = value
            total = 0.0
            numeric_count = 0
            for info in state.runtime.satellites.values():
                value = info.held_amount
                if value is None:
                    continue
                try:
                    total += float(value)
                    numeric_count += 1
                except Exception:
                    continue
            state.data.total_held_amount = total if numeric_count > 0 else None

        return True

    async def _fetch_node_payload(
        self, client: httpx.AsyncClient, state: NodeState, path: str
    ) -> Tuple[bool, Optional[object]]:
        """Perform the HTTP GET and JSON parsing for a nodeapi URL.

        Returns a tuple: (success, payload). On success payload is a dict.
        On failure success is False and payload is None; the NodeState will
        be updated with failure counters and last_error.
        """
        # Build the full URL by joining the state's base URL and the
        # requested path. `urljoin` handles trailing slashes and absolute
        # paths cleanly.
        full_url = urllib.parse.urljoin(state.runtime.url, path)

        async def _on_fail(msg: str, warn_fmt: str, *warn_args: object) -> Tuple[bool, None]:
            """Local helper to centralize failure handling.

            Logs a warning with the provided format, updates the NodeState
            (increment failures, set last_error) under the lock, emits a
            debug line with the current failure count, and returns the
            standard (False, None) tuple.
            """
            logger.warning(warn_fmt, *warn_args)
            async with self._lock:
                state.runtime.consecutive_failures += 1
                state.runtime.last_error = msg
                logger.debug(
                    "Node '%s' poll failed (%s), consecutive failures=%d",
                    state.name,
                    msg,
                    state.runtime.consecutive_failures,
                )
            return False, None

        try:
            response = await client.get(full_url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            msg = f"HTTP status error: {exc}"
            return await _on_fail(msg, "Nodeapi request failed for %s: %s", full_url, exc)
        except httpx.HTTPError as exc:
            msg = f"HTTP error: {exc}"
            return await _on_fail(msg, "Nodeapi request error for %s: %s", full_url, exc)

        try:
            payload = response.json()
        except ValueError:
            msg = "invalid JSON"
            return await _on_fail(msg, "Nodeapi response for %s was not valid JSON", full_url)

        # Accept either a JSON object or array; callers will validate the
        # structure they expect (dict vs list).
        if payload is None:
            return True, None

        if not isinstance(payload, (dict, list)):
            msg = "response is not a JSON object or array"
            # Log a concise warning (avoid logging raw HTTP body)
            logger.warning("Nodeapi response for %s was not a JSON object/array.", full_url)
            return await _on_fail(msg, "Nodeapi response for %s is not a JSON object/array; skipping", full_url)

        return True, payload

    async def _ensure_client(self) -> Optional[httpx.AsyncClient]:
        if self._client is None:
            # Ensure the client follows redirects by default to avoid
            # unnecessary HTTP status errors when endpoints redirect.
            self._client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
        return self._client

    def _nodeapi_sources(self) -> List[SourceDefinition]:
        try:
            sources = self._settings.parsed_sources
        except ValueError as exc:
            logger.error("Unable to parse node configuration for nodeapi polling: %s", exc)
            return []
        return [source for source in sources if source.nodeapi]

    async def get_node_data(self, names: Optional[List[str]] = None) -> Dict[str, NodeData]:
        """Return a mapping of node name -> NodeData copy for the requested nodes.

        If `names` is None or empty, data for all known nodes is returned.
        The implementation acquires the service lock to produce a consistent
        snapshot and returns shallow copies of each NodeData to avoid callers
        mutating internal state.
        """
        async with self._lock:
            if not names:
                # copy all nodes
                result = {name: replace(state.data or NodeData()) for name, state in self._states.items()}
                return result

            # Filter to the requested names; ignore unknown names
            result: Dict[str, NodeData] = {}
            for name in names:
                st = self._states.get(name)
                if st is None:
                    continue
                result[name] = replace(st.data or NodeData())
            return result


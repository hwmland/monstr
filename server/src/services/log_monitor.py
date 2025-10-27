from __future__ import annotations

import asyncio
import logging
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles

from ..config import Settings
from .. import database
from ..repositories.log_entries import LogEntryRepository
from ..repositories.reputations import ReputationRepository
from ..repositories.transfers import TransferRepository
from ..schemas import LogEntryCreate, ReputationCreate, TransferCreate

logger = logging.getLogger(__name__)

ALLOWED_LEVELS = {"DEBUG", "INFO", "WARN", "ERROR"}


@dataclass(frozen=True)
class FileSignature:
    inode: Optional[int]
    device: Optional[int]
    size: Optional[int]
    modified_ns: Optional[int]

    @classmethod
    def from_stat(cls, stat_result: os.stat_result | None) -> "FileSignature":
        if stat_result is None:
            return cls(None, None, None, None)

        inode = getattr(stat_result, "st_ino", None)
        if inode == 0:
            inode = None
        device = getattr(stat_result, "st_dev", None)
        size = getattr(stat_result, "st_size", None)
        modified_ns = getattr(stat_result, "st_mtime_ns", None)
        return cls(inode, device, size, modified_ns)

    def differs_from(self, other: "FileSignature") -> bool:
        inode_differs = (
            self.inode is not None
            and other.inode is not None
            and self.inode != other.inode
        )
        device_differs = (
            self.device is not None
            and other.device is not None
            and self.device != other.device
        )
        if inode_differs or device_differs:
            return True

        if (
            self.modified_ns is not None
            and other.modified_ns is not None
            and self.modified_ns > other.modified_ns
            and self.size == other.size == 0
        ):
            # Fallback heuristic: file recreated and truncated.
            return True

        return False


class LogMonitorService:
    """Stream new lines from configured log files into the persistence layer."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._tasks: List[asyncio.Task] = []
        self._stopping = asyncio.Event()
        self._unprocessed_dir = settings.unprocessed_log_directory
        self._unprocessed_prefix = "unprocessed"

    async def start(self) -> None:
        if not self._settings.log_sources:
            logger.warning("Log monitoring started without any nodes configured.")
            return

        try:
            nodes = self._settings.parsed_log_sources
        except ValueError as exc:
            logger.error("Failed to parse node configuration: %s", exc)
            return

        if not nodes:
            logger.warning("No valid log nodes resolved from configuration.")
            return

        for node_name, path in nodes:
            logger.info("Starting watcher for node '%s' at %s", node_name, path)
            task = asyncio.create_task(
                self._watch_file(node_name, path), name=f"log-watch:{node_name}"
            )
            self._tasks.append(task)

    async def stop(self) -> None:
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _watch_file(self, node_name: str, path: Path) -> None:
        log_buffer: List[LogEntryCreate] = []
        transfer_buffer: List[TransferCreate] = []
        reputation_buffer: List[ReputationCreate] = []

        while not self._stopping.is_set():
            try:
                async with aiofiles.open(path, mode="r") as handle:
                    logger.info("Opened log file for node '%s': %s", node_name, path)
                    handle_signature = await self._get_handle_signature(handle)
                    await handle.seek(0, 2)  # jump to end of file

                    while not self._stopping.is_set():
                        line = await handle.readline()
                        if line:
                            (
                                processed_entries,
                                transfer_entries,
                                reputation_entries,
                                is_unprocessed,
                            ) = await self._process_line(node_name, line)
                            entry_count = len(processed_entries) if processed_entries else 0
                            logger.debug(
                                (
                                    "Parsed log line; node=%s unprocessed=%s log_entries=%d transfers=%d "
                                    "source_path=%s"
                                ),
                                node_name,
                                is_unprocessed,
                                entry_count,
                                len(transfer_entries),
                                path,
                            )

                            if is_unprocessed:
                                await self._record_unprocessed(node_name, line)
                                continue

                            if processed_entries is None:
                                continue  # handled intentionally (e.g. ignored by filters)

                            if processed_entries:
                                log_buffer.extend(processed_entries)
                            if transfer_entries:
                                transfer_buffer.extend(transfer_entries)
                            if reputation_entries:
                                reputation_buffer.extend(reputation_entries)

                            if (
                                len(log_buffer) >= self._settings.log_batch_size
                                or len(transfer_buffer) >= self._settings.log_batch_size
                                or len(reputation_buffer) >= self._settings.log_batch_size
                            ):
                                await self._flush_buffers(
                                    log_buffer,
                                    transfer_buffer,
                                    reputation_buffer,
                                    node_name=node_name,
                                )
                        else:
                            if log_buffer or transfer_buffer or reputation_buffer:
                                await self._flush_buffers(
                                    log_buffer,
                                    transfer_buffer,
                                    reputation_buffer,
                                    node_name=node_name,
                                )

                            should_reopen, handle_signature = await self._should_reopen_file(
                                handle,
                                path,
                                handle_signature,
                            )
                            if should_reopen:
                                logger.info(
                                    "Detected rotation or truncation for log %s (node %s); reopening",
                                    path,
                                    node_name,
                                )
                                break
                            try:
                                await asyncio.wait_for(
                                    self._stopping.wait(),
                                    timeout=self._settings.log_poll_interval,
                                )
                            except asyncio.TimeoutError:
                                continue
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

        if log_buffer or transfer_buffer or reputation_buffer:
            await self._flush_buffers(
                log_buffer,
                transfer_buffer,
                reputation_buffer,
                node_name=node_name,
            )

    async def _get_loop(self) -> asyncio.AbstractEventLoop:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.get_event_loop()

    async def _stat_path(self, path: Path) -> os.stat_result | None:
        loop = await self._get_loop()
        try:
            return await loop.run_in_executor(None, path.stat)
        except FileNotFoundError:
            return None

    async def _stat_fd(self, handle: aiofiles.threadpool.text.AsyncTextIOWrapper) -> os.stat_result | None:
        try:
            fileno = handle.fileno()
        except (AttributeError, OSError, ValueError):
            return None

        loop = await self._get_loop()
        try:
            return await loop.run_in_executor(None, os.fstat, fileno)
        except OSError:
            return None

    async def _get_handle_signature(
        self, handle: aiofiles.threadpool.text.AsyncTextIOWrapper
    ) -> FileSignature:
        fd_stat = await self._stat_fd(handle)
        return FileSignature.from_stat(fd_stat)

    async def _should_reopen_file(
        self,
        handle: aiofiles.threadpool.text.AsyncTextIOWrapper,
        path: Path,
        original_signature: FileSignature,
    ) -> tuple[bool, FileSignature]:
        current_fd_stat = await self._stat_fd(handle)
        current_fd_signature = FileSignature.from_stat(current_fd_stat)
        if original_signature.differs_from(current_fd_signature):
            return True, current_fd_signature

        path_stat = await self._stat_path(path)
        path_signature = FileSignature.from_stat(path_stat)
        if current_fd_signature.differs_from(path_signature):
            return True, current_fd_signature

        if current_fd_signature.size is not None:
            position = await handle.tell()
            if position > current_fd_signature.size:
                return True, current_fd_signature

        return False, current_fd_signature

    async def _flush_buffers(
        self,
        log_buffer: List[LogEntryCreate],
        transfer_buffer: List[TransferCreate],
        reputation_buffer: List[ReputationCreate],
        *,
        node_name: Optional[str] = None,
    ) -> None:
        if not log_buffer and not transfer_buffer and not reputation_buffer:
            return

        log_count = len(log_buffer)
        transfer_count = len(transfer_buffer)
        reputation_count = len(reputation_buffer)

        async with database.SessionFactory() as session:
            log_repository = LogEntryRepository(session)
            transfer_repository = TransferRepository(session)
            reputation_repository = ReputationRepository(session)

            if log_buffer:
                await log_repository.create_many(log_buffer)
                log_buffer.clear()
            if transfer_buffer:
                await transfer_repository.create_many(transfer_buffer)
                transfer_buffer.clear()
            if reputation_buffer:
                await reputation_repository.upsert_many(reputation_buffer)
                reputation_buffer.clear()

        if node_name:
            logger.info(
                "Persisted %d log entries, %d transfers, %d reputations for node %s",
                log_count,
                transfer_count,
                reputation_count,
                node_name,
            )
        else:
            logger.info(
                "Persisted %d log entries, %d transfers, %d reputations",
                log_count,
                transfer_count,
                reputation_count,
            )

    async def _process_line(
        self, node_name: str, raw_line: str
    ) -> Tuple[
        Optional[List[LogEntryCreate]],
        List[TransferCreate],
        List[ReputationCreate],
        bool,
    ]:
        """Parse Storj-formatted log lines into structured persistence payloads."""
        trimmed = raw_line.rstrip("\n")
        if not trimmed:
            return [], [], [], True

        parts = trimmed.split("\t", 4)
        if len(parts) != 5:
            return [], [], [], True

        timestamp, level, area, action, details_blob = parts
        if level not in ALLOWED_LEVELS:
            return [], [], [], True

        try:
            log_timestamp = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return [], [], [], True

        try:
            details = json.loads(details_blob)
        except json.JSONDecodeError:
            return [], [], [], True

        if not isinstance(details, dict):
            return [], [], [], True

        payload = {
            "source": node_name,
            "timestamp": log_timestamp,
            "level": level,
            "area": area,
            "action": action,
            "details": details,
        }

        if self._should_ignore(payload):
            return None, [], [], False

        processed_payload = self._process_payload(payload)
        if processed_payload is None:
            return [], [], [], True

        log_payload, transfer_payload, reputation_payload = processed_payload

        entries: List[LogEntryCreate] = []
        if log_payload is not None:
            entries.append(LogEntryCreate(**log_payload))

        transfers: List[TransferCreate] = []
        if transfer_payload:
            transfers.append(TransferCreate(**transfer_payload))

        reputations: List[ReputationCreate] = []
        if reputation_payload is not None:
            reputations.append(reputation_payload)

        return entries, transfers, reputations, False

    def _should_ignore(self, payload: Dict[str, Any]) -> bool:
        """Determine whether a parsed entry should be skipped entirely."""
        level = payload.get("level")
        if level == "DEBUG":
            return True

        area = str(payload.get("area") or "")
        action = str(payload.get("action") or "")

        if level == "INFO" and area == "piecemigrate:chore":
            if action == "enqueued for migration":
                return True
            if action.startswith("all enqueued for migration"):
                return True

        if level == "INFO" and area == "orders" and action == "finished":
            return True

        if (
            level == "INFO"
            and area == "bandwidth"
            and action == "Persisting bandwidth usage cache to db"
        ):
            return True

        if level == "INFO" and area == "piecestore" and action == "New bloomfilter is received":
            return True

        if level == "INFO" and area == "trust" and action == "Scheduling next refresh":
            return True

        return False

    def _process_payload(
        self, payload: Dict[str, Any]
    ) -> Optional[
        Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[ReputationCreate]]
    ]:
        """Apply specialized transformations to recognized payload patterns."""
        level = str(payload.get("level") or "")
        area = str(payload.get("area") or "")
        action = str(payload.get("action") or "")

        if level == "INFO":
            if area == "piecestore":
                if action in {"downloaded", "download canceled", "uploaded", "upload canceled"}:
                    result = self._process_piecestore_transfer(payload)
                    if result is None:
                        return None
                    _, transfer_payload = result
                    return None, transfer_payload, None
                return payload, None, None
            if area == "reputation:service":
                result = self._process_reputation_service(payload)
                if result is None:
                    return None
                log_payload, reputation_payload = result
                return log_payload, None, reputation_payload
            if area == "pieces:trash":
                log_payload = self._process_pieces_trash_payload(payload)
                return log_payload, None, None
            if area == "hashstore":
                log_payload = self._process_hashstore_payload(payload)
                return log_payload, None, None
            if area in {
                "lazyfilewalker.trash-cleanup-filewalker",
                "lazyfilewalker.trash-cleanup-filewalker.subprocess",
            }:
                log_payload = self._process_lazyfilewalker_trash_payload(payload)
                return log_payload, None, None
            if area in {
                "lazyfilewalker.gc-filewalker",
                "lazyfilewalker.gc-filewalker.subprocess",
            }:
                log_payload = self._process_lazyfilewalker_gc_payload(payload)
                return log_payload, None, None
            if area == "collector":
                log_payload = self._process_collector_payload(payload)
                return log_payload, None, None
            if area == "retain":
                log_payload, reputation_payload = self._process_retain_payload(payload)
                return log_payload, None, reputation_payload
            return payload, None, None
        if level == "WARN":
            log_payload = self._process_warn_payload(payload)
            return log_payload, None, None
        if level == "ERROR":
            log_payload = self._process_error_payload(payload)
            return log_payload, None, None
        return None

    def _process_piecestore_transfer(
        self, payload: Dict[str, Any]
    ) -> Optional[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]]:
        """Normalize piecestore transfer events for downstream consumers."""
        action_text = str(payload.get("action") or "")
        details_obj = payload.get("details")
        details = details_obj if isinstance(details_obj, dict) else {}
        timestamp_value = payload.get("timestamp")
        normalized_timestamp = (
            timestamp_value.isoformat()
            if isinstance(timestamp_value, datetime)
            else str(timestamp_value)
        )
        monstr_meta = {
            "kind": "piecestore_transfer",
            "timestamp": normalized_timestamp,
            "event": payload.get("action"),
            "transfer_type": details.get("Action"),
            "piece_id": details.get("Piece ID"),
            "satellite_id": details.get("Satellite ID"),
            "size": details.get("Size"),
            "offset": details.get("Offset"),
            "remote_address": details.get("Remote Address"),
            "process": details.get("Process"),
        }
        enriched_details = {**details, "_monstr": monstr_meta}
        log_payload = {**payload, "details": enriched_details}

        action_mappings = {
            "downloaded": ("DL", True),
            "download canceled": ("DL", False),
            "uploaded": ("UL", True),
            "upload canceled": ("UL", False),
        }
        mapping = action_mappings.get(action_text)
        if mapping is None:
            return None

        action_code, is_success = mapping

        transfer_type = details.get("Action")
        is_repair = transfer_type in {"GET_REPAIR", "PUT_REPAIR"}

        size_value = self._coerce_int(details.get("Size"))
        offset_value = self._coerce_int(details.get("Offset"))

        if size_value is None or not details.get("Piece ID") or not details.get("Satellite ID"):
            logger.debug(
                "Skipping transfer record due to missing mandatory data: node=%s action=%s",
                payload.get("source"),
                payload.get("action"),
            )
            transfer_payload = None
        else:
            transfer_payload = {
                "source": payload.get("source"),
                "timestamp": payload.get("timestamp"),
                "action": action_code,
                "is_success": is_success,
                "piece_id": details.get("Piece ID"),
                "satellite_id": details.get("Satellite ID"),
                "is_repair": is_repair,
                "size": size_value,
                "offset": offset_value,
                "remote_address": details.get("Remote Address"),
            }

        return log_payload, transfer_payload

    def _process_error_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist error records as-is for log entry storage."""
        return payload

    def _process_reputation_service(
        self, payload: Dict[str, Any]
    ) -> Optional[Tuple[Dict[str, Any], Optional[ReputationCreate]]]:
        """Persist reputation service info records and extract reputation metrics."""
        details_obj = payload.get("details")
        details = details_obj if isinstance(details_obj, dict) else {}

        timestamp_value = payload.get("timestamp")
        normalized_timestamp = (
            timestamp_value.isoformat()
            if isinstance(timestamp_value, datetime)
            else str(timestamp_value)
        )
        monstr_meta = {
            "kind": "reputation",
            "timestamp": normalized_timestamp,
            "event": payload.get("action"),
        }
        log_payload = {**payload, "details": {**details, "_monstr": monstr_meta}}

        satellite_id = (
            str(details.get("Satellite ID"))
            if details.get("Satellite ID") is not None
            else None
        )
        audits_total = self._coerce_int(details.get("Total Audits"))
        audits_success = self._coerce_int(details.get("Successful Audits"))
        score_audit = self._coerce_float(details.get("Audit Score"))
        score_online = self._coerce_float(details.get("Online Score"))
        score_suspension = self._coerce_float(details.get("Suspension Score"))

        if (
            not satellite_id
            or audits_total is None
            or audits_success is None
            or score_audit is None
            or score_online is None
            or score_suspension is None
            or not isinstance(timestamp_value, datetime)
        ):
            logger.warning(
                "Skipping reputation record due to incomplete data: node=%s action=%s",
                payload.get("source"),
                payload.get("action"),
            )
            return None

        reputation_payload = ReputationCreate(
            source=payload.get("source"),
            satellite_id=satellite_id,
            timestamp=timestamp_value,
            audits_total=audits_total,
            audits_success=audits_success,
            score_audit=score_audit,
            score_online=score_online,
            score_suspension=score_suspension,
        )

        return log_payload, reputation_payload

    def _process_pieces_trash_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist pieces trash info records without additional processing."""
        return payload

    def _process_hashstore_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist hashstore info records without additional processing."""
        return payload

    def _process_lazyfilewalker_trash_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist lazyfilewalker trash cleanup info records without processing."""
        return payload

    def _process_lazyfilewalker_gc_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist lazyfilewalker garbage collection info records without processing."""
        return payload

    def _process_collector_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist collector info records without additional processing."""
        return payload

    def _process_retain_payload(
        self, payload: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Optional[ReputationCreate]]:
        """Persist retain info records."""
        return payload, None

    def _process_warn_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist warning records as-is for log entry storage."""
        return payload

    def _coerce_int(self, value: Any) -> Optional[int]:
        """Attempt to coerce a value into an integer, returning None on failure."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def _coerce_float(self, value: Any) -> Optional[float]:
        """Attempt to coerce a value into a float, returning None on failure."""
        if value is None:
            return None
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return float(value)
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    async def _record_unprocessed(self, node_name: str, raw_line: str) -> None:
        """Append an entry to the per-node unprocessed log file for later analysis."""
        file_path = self._resolve_unprocessed_path(node_name)
        async with aiofiles.open(file_path, mode="a", encoding="utf-8") as handle:
            await handle.write(raw_line if raw_line.endswith("\n") else f"{raw_line}\n")

    def _resolve_unprocessed_path(self, node_name: str) -> Path:
        """Return the output file that should capture unprocessed records for a node."""
        sanitized_name = self._sanitize_node_name(node_name)
        directory = self._unprocessed_dir
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{self._unprocessed_prefix}-{sanitized_name}.log"
        return directory / filename

    def _sanitize_node_name(self, node_name: str) -> str:
        """Produce a filesystem-friendly node identifier for log filenames."""
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", node_name.strip())
        return sanitized or "unknown"

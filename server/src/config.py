from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import Field, PrivateAttr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    kind: Literal["file", "tcp"]
    path: Optional[Path] = None
    host: Optional[str] = None
    port: Optional[int] = None
    nodeapi: Optional[str] = None


@dataclass(frozen=True)
class IP24Definition:
    alias: str
    ip: str
    expected_instances: int


@dataclass(frozen=True)
class DisqualDefinition:
    """A configured disqualification event for a node/satellite at a period.

    An empty ``satellite_id`` means "all satellites" for that source.
    ``period`` is in ``yyyy-mm`` format.
    """

    source: str
    satellite_id: str
    period: str


@dataclass(frozen=True)
class NodeDisqualification:
    satellite_id: Optional[str]
    period: str


@dataclass(frozen=True)
class NodeDefinition:
    name: str
    kind: Literal["file", "tcp"]
    path: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    nodeapi: Optional[str] = None
    disqualifications: Tuple[NodeDisqualification, ...] = ()


@dataclass(frozen=True)
class NodeLocationDefinition:
    alias: str
    ip: str
    nodes: Tuple[NodeDefinition, ...]


@dataclass(frozen=True)
class NodeGroupDefinition:
    name: str
    locations: Tuple[NodeLocationDefinition, ...]
    icon: Optional[str] = None


class Settings(BaseSettings):
    """Application configuration sourced from environment variables or overrides."""

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_reload: bool = False
    api_log_level: str = "info"

    database_url: str = "sqlite+aiosqlite:///./data/monstr.db"
    sql_echo: bool = False

    log_poll_interval: float = 1.0
    # Unified ordered sources. Each entry may be NAME:PATH (file) or
    # NAME:HOST:PORT (remote). This is the single canonical place to declare
    # configured nodes and preserves the declared sequence.
    # Accept either a raw string (from env like "a:b,c:d") or a list; the
    # validator below will coerce into a List[str]. Declaring the union with
    # `str | List[str]` prevents pydantic-settings from attempting JSON
    # decoding on simple comma-separated env strings.
    sources: str | List[str] = []
    # Expected node instances per IP. Entries may be "1.2.3.4:2" or
    # "alias|node.example.com:3". Allow multiple or none; JSON list accepted via env.
    ip24: str | List[str] = []
    # Disqualification declarations.  Each entry is SOURCE:SATELLITE_ID:PERIOD
    # where SATELLITE_ID may be empty (meaning all satellites) and PERIOD is
    # yyyy-mm.  Example: "Node1::2025-06" or "Node1:1wFTAgs...@:2025-06".
    # Accepts comma/newline separated strings, JSON arrays, or a Python list.
    disqual: str | List[str] = []
    nodegroups: List[NodeGroupDefinition] = Field(default_factory=list)
    log_batch_size: int = 32
    nodeapi_poll_interval_seconds: int = 60
    # Interval (seconds) after which the estimated-payout endpoint should be
    # re-queried for fresh payout estimates. Default: 5 minutes.
    nodeapi_estimated_payout_interval_seconds: int = 300
    # Interval (seconds) after which the held-history endpoint should be
    # re-queried for fresh per-satellite held amounts. Default: 5 minutes.
    nodeapi_held_history_interval_seconds: int = 300
    # Interval (seconds) for processing /api/sno satellite details payloads.
    # Default: 5 minutes.
    nodeapi_satellite_details_interval_seconds: int = 300
    # Interval (seconds) after which the paystubs endpoint should be
    # re-queried. Default: 10 minutes.
    nodeapi_paystub_interval_seconds: int = 600

    cleanup_interval_seconds: int = 300
    grouping_interval_seconds: int = 120
    # If the database cannot be written to (e.g., during external backups),
    # suspend attempts for this many seconds to allow external operations to finish.
    # During suspension the in-memory buffers will be retained.
    db_write_suspend_seconds: int = 60
    # Global default retention (used as a fallback)
    retention_minutes: int = 1440 * 7 * 4  # 4 weeks in minutes
    # Per-table retention overrides (in minutes)
    retention_transfers_minutes: int = 1440  # 1 day in minutes
    retention_log_entries_minutes: int = 1440 * 7 * 4  # 4 weeks in minutes
    retention_transfer_grouped_minutes: int = -1  # unlimited retention
    retention_hashstore_compaction_minutes: int = 1440 * 365 * 5  # 5 years in minutes
    frontend_dist_dir: Optional[str] = "../client/dist"
    unprocessed_log_dir: str = "../data/"
    cors_allow_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    logging_overrides: Dict[str, str] = Field(default_factory=dict)
    config_file: Optional[str] = Field(default=None, exclude=True, repr=False)
    config_json: Optional[str] = Field(default=None, exclude=True, repr=False)

    _nodegroups_sources_active: bool = PrivateAttr(default=False)
    _nodegroups_ip24_active: bool = PrivateAttr(default=False)
    _nodegroups_disqual_active: bool = PrivateAttr(default=False)

    model_config = SettingsConfigDict(
        env_prefix="MONSTR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("sources", mode="before")
    @classmethod
    def _coerce_sources(cls, value):
        """Allow comma or newline separated env strings for mixed sources."""
        if value in (None, ""):
            return []
        if isinstance(value, str):
            v = value.strip()
            # If the string is a JSON array (e.g. '["a","b"]'), decode it
            # first so callers can set MONSTR_SOURCES to a JSON array in envs.
            if v.startswith("[") or v.startswith("{"):
                try:
                    decoded = json.loads(v)
                    if isinstance(decoded, (list, tuple, set)):
                        return [str(item).strip() for item in decoded if str(item).strip()]
                except Exception:
                    # fall back to comma/newline splitting below
                    pass
            cleaned = value.replace("\n", ",")
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        if isinstance(value, (tuple, set, list)):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @field_validator("ip24", mode="before")
    @classmethod
    def _coerce_ip24(cls, value):
        """Allow comma/newline separated or JSON list env strings for ip24."""
        if value in (None, ""):
            return []
        if isinstance(value, str):
            v = value.strip()
            if v.startswith("[") or v.startswith("{"):
                try:
                    decoded = json.loads(v)
                    if isinstance(decoded, (list, tuple, set)):
                        return [str(item).strip() for item in decoded if str(item).strip()]
                except Exception:
                    pass
            cleaned = value.replace("\n", ",")
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        if isinstance(value, (tuple, set, list)):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @field_validator("disqual", mode="before")
    @classmethod
    def _coerce_disqual(cls, value):
        """Allow comma/newline separated or JSON list env strings for disqual."""
        if value in (None, ""):
            return []
        if isinstance(value, str):
            v = value.strip()
            if v.startswith("[") or v.startswith("{"):
                try:
                    decoded = json.loads(v)
                    if isinstance(decoded, (list, tuple, set)):
                        return [str(item).strip() for item in decoded if str(item).strip()]
                except Exception:
                    pass
            cleaned = value.replace("\n", ",")
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        if isinstance(value, (tuple, set, list)):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @property
    def database_path(self) -> Path:
        """Return the on-disk path for the SQLite database when applicable."""
        if self.database_url.startswith("sqlite"):
            raw_path = self.database_url.split("///", maxsplit=1)[-1]
            return Path(raw_path).expanduser().resolve()
        raise ValueError("Database URL is not pointing to a SQLite database")

    @property
    def has_active_nodegroups(self) -> bool:
        """Return whether nodegroups define the active log-source list."""
        return self._nodegroups_sources_active

    def get_retention_minutes(self, table_name: str) -> int:
        """Return retention in minutes for a given database table.

        Looks for a per-table override attribute on the Settings instance. If no
        specific override exists, falls back to `retention_minutes`.
        """
        key_map = {
            "transfers": "retention_transfers_minutes",
            "log_entries": "retention_log_entries_minutes",
            "transfer_grouped": "retention_transfer_grouped_minutes",
            "hashstore_compaction": "retention_hashstore_compaction_minutes",
        }

        attr = key_map.get(table_name)
        if attr and hasattr(self, attr):
            value = getattr(self, attr)
            try:
                return int(value)
            except (TypeError, ValueError):
                # Fall through to global fallback if override is invalid
                pass
        return int(self.retention_minutes)

    @property
    def frontend_path(self) -> Optional[Path]:
        """Return the resolved path to the built frontend assets if configured."""
        if not self.frontend_dist_dir:
            return None

        candidate = Path(self.frontend_dist_dir)
        if not candidate.is_absolute():
            base_dir = Path(__file__).resolve().parent.parent
            candidate = (base_dir / candidate).resolve()
        return candidate

    @property
    def parsed_sources(self) -> List[SourceDefinition]:
        """Return structured source definitions from nodegroups or legacy declarations."""
        if self._nodegroups_sources_active:
            parsed: List[SourceDefinition] = []
            for group in self.nodegroups:
                for location in group.locations:
                    for node in location.nodes:
                        path = (
                            Path(node.path).expanduser().resolve()
                            if node.kind == "file" and node.path is not None
                            else None
                        )
                        parsed.append(
                            SourceDefinition(
                                name=node.name,
                                kind=node.kind,
                                path=path,
                                host=node.host,
                                port=node.port,
                                nodeapi=node.nodeapi,
                            )
                        )
            return parsed

        parsed: List[SourceDefinition] = []
        for raw in self.sources or []:
            if not raw:
                continue

            nodeapi: Optional[str] = None
            base = raw
            if "|" in raw:
                base, nodeapi = raw.split("|", 1)
                nodeapi = nodeapi.strip() or None

            if ":" not in base:
                raise ValueError(f"Invalid source declaration '{raw}'; expected NAME:SPEC")

            name, spec = base.split(":", 1)
            name = name.strip()
            spec = spec.strip()

            if not name:
                raise ValueError(f"Source '{raw}' is missing a node name")

            if self._looks_like_host_port(spec):
                host, port = self._parse_host_port(spec)
                parsed.append(
                    SourceDefinition(name=name, kind="tcp", host=host, port=port, nodeapi=nodeapi)
                )
            else:
                path = Path(spec).expanduser().resolve()
                parsed.append(SourceDefinition(name=name, kind="file", path=path, nodeapi=nodeapi))
        return parsed

    @property
    def parsed_ip24(self) -> List[IP24Definition]:
        """Return location-derived IP24 definitions or legacy `ip24` entries."""
        if self._nodegroups_ip24_active:
            return [
                IP24Definition(
                    alias=location.alias,
                    ip=location.ip,
                    expected_instances=len(location.nodes),
                )
                for group in self.nodegroups
                for location in group.locations
            ]

        parsed: List[IP24Definition] = []
        for raw in self.ip24 or []:
            entry = str(raw).strip()
            if not entry:
                continue
            alias = ""
            base = entry
            if "|" in entry:
                alias, base = entry.split("|", 1)
                alias = alias.strip()
                base = base.strip()
                if not alias:
                    raise ValueError(f"Invalid ip24 declaration '{entry}'; alias cannot be empty")
            if ":" not in base:
                raise ValueError(
                    f"Invalid ip24 declaration '{entry}'; expected [ALIAS|]IP:INSTANCES"
                )
            ip_part, count_part = base.split(":", 1)
            ip_part = ip_part.strip()
            count_part = count_part.strip()
            if not ip_part or not count_part:
                raise ValueError(
                    f"Invalid ip24 declaration '{entry}'; expected [ALIAS|]IP:INSTANCES"
                )
            try:
                expected = int(count_part)
            except ValueError as exc:  # noqa: PERF203
                raise ValueError(f"Invalid ip24 instances value in '{entry}'") from exc
            if expected < 0:
                raise ValueError(f"Invalid ip24 instances value in '{entry}'; must be non-negative")
            parsed.append(
                IP24Definition(alias=alias or ip_part, ip=ip_part, expected_instances=expected)
            )
        return parsed

    @property
    def parsed_disqual(self) -> List[DisqualDefinition]:
        """Return nodegroup-derived disqualifications or legacy ``disqual`` declarations.

        Legacy entries have the form ``SOURCE:SATELLITE_ID:PERIOD`` where an
        empty ``SATELLITE_ID`` means all satellites and ``PERIOD`` is ``yyyy-mm``.
        """
        if self._nodegroups_disqual_active:
            return [
                DisqualDefinition(
                    source=node.name,
                    satellite_id=disqualification.satellite_id or "",
                    period=disqualification.period,
                )
                for group in self.nodegroups
                for location in group.locations
                for node in location.nodes
                for disqualification in node.disqualifications
            ]

        period_re = re.compile(r"^\d{4}-\d{2}$")
        parsed: List[DisqualDefinition] = []
        for raw in self.disqual or []:
            entry = str(raw).strip()
            if not entry:
                continue
            parts = entry.split(":")
            if len(parts) < 3:
                raise ValueError(
                    f"Invalid disqual declaration '{entry}'; "
                    "expected SOURCE:SATELLITE_ID:PERIOD (satellite_id may be empty)"
                )
            source = parts[0].strip()
            # Everything except the first and last segment constitutes
            # the satellite_id (which itself may contain ':'
            # characters in base58-encoded Storj IDs).
            period = parts[-1].strip()
            satellite_id = ":".join(parts[1:-1]).strip()
            if not source:
                raise ValueError(f"Disqual entry '{entry}' is missing a source name")
            if not period_re.match(period):
                raise ValueError(
                    f"Invalid disqual period '{period}' in '{entry}'; expected yyyy-mm"
                )
            parsed.append(
                DisqualDefinition(source=source, satellite_id=satellite_id, period=period)
            )
        return parsed

    @staticmethod
    def _looks_like_host_port(spec: str) -> bool:
        spec = spec.strip()
        if not spec:
            return False
        # IPv6 literal: [addr]:port
        if spec.startswith("[") and "]" in spec:
            host_part, _, port_part = spec.partition("]:")
            return bool(port_part and port_part.isdigit())
        # Simple host:port, ensure no path separators to avoid mis-detecting file paths
        if ":" not in spec:
            return False
        host, port = spec.rsplit(":", 1)
        if not port.isdigit():
            return False
        if "/" in host or "\\" in host:
            return False
        return bool(host)

    @staticmethod
    def _parse_host_port(spec: str) -> Tuple[str, int]:
        spec = spec.strip()
        if spec.startswith("[") and "]" in spec:
            host_part, _, port_part = spec.partition("]:")
            host = host_part.lstrip("[")
            port = int(port_part)
            return host, port
        host, port = spec.rsplit(":", 1)
        return host.strip(), int(port.strip())

    @property
    def unprocessed_log_directory(self) -> Path:
        """Directory where unprocessed log lines will be recorded."""
        candidate = Path(self.unprocessed_log_dir)
        if not candidate.is_absolute():
            base_dir = Path(__file__).resolve().parent.parent
            candidate = (base_dir / candidate).resolve()
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Literal
import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    kind: Literal["file", "tcp"]
    path: Optional[Path] = None
    host: Optional[str] = None
    port: Optional[int] = None
    nodeapi: Optional[str] = None


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
    log_batch_size: int = 32
    nodeapi_poll_interval_seconds: int = 60
    # Interval (seconds) after which the estimated-payout endpoint should be
    # re-queried for fresh payout estimates. Default: 5 minutes.
    nodeapi_estimated_payout_interval_seconds: int = 300
    # Interval (seconds) after which the held-history endpoint should be
    # re-queried for fresh per-satellite held amounts. Default: 5 minutes.
    nodeapi_held_history_interval_seconds: int = 300

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
    retention_transfer_grouped_minutes: int = -1 # unlimited retention
    frontend_dist_dir: Optional[str] = "../client/dist"
    unprocessed_log_dir: str = "../data/"
    cors_allow_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

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

    @property
    def database_path(self) -> Path:
        """Return the on-disk path for the SQLite database when applicable."""
        if self.database_url.startswith("sqlite"):
            raw_path = self.database_url.split("///", maxsplit=1)[-1]
            return Path(raw_path).expanduser().resolve()
        raise ValueError("Database URL is not pointing to a SQLite database")

    def get_retention_minutes(self, table_name: str) -> int:
        """Return retention in minutes for a given database table.

        Looks for a per-table override attribute on the Settings instance. If no
        specific override exists, falls back to `retention_minutes`.
        """
        key_map = {
            "transfers": "retention_transfers_minutes",
            "log_entries": "retention_log_entries_minutes",
            "transfer_grouped": "retention_transfer_grouped_minutes",
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
        """Return structured source definitions parsed from `sources`."""
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
                parsed.append(SourceDefinition(name=name, kind="tcp", host=host, port=port, nodeapi=nodeapi))
            else:
                path = Path(spec).expanduser().resolve()
                parsed.append(SourceDefinition(name=name, kind="file", path=path, nodeapi=nodeapi))
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

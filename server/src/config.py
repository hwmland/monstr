from pathlib import Path
from typing import List, Optional, Tuple
import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    cleanup_interval_seconds: int = 300
    grouping_interval_seconds: int = 120
    # Global default retention (used as a fallback)
    retention_minutes: int = 1440 * 7 * 4  # 4 weeks in minutes
    # Per-table retention overrides (in minutes)
    retention_transfers_minutes: int = 1440  # 1 day in minutes
    retention_log_entries_minutes: int = 1440 * 7 * 4  # 4 weeks in minutes
    retention_transfer_grouped_minutes: int = 1440 * 7  # 7 days in minutes
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
    def unprocessed_log_directory(self) -> Path:
        """Directory where unprocessed log lines will be recorded."""
        candidate = Path(self.unprocessed_log_dir)
        if not candidate.is_absolute():
            base_dir = Path(__file__).resolve().parent.parent
            candidate = (base_dir / candidate).resolve()
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate

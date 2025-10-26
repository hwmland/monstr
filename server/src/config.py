from pathlib import Path
from typing import List, Optional, Tuple

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
    log_sources: List[str] = []
    log_batch_size: int = 32

    cleanup_interval_seconds: int = 300
    retention_minutes: int = 1440 * 7 * 4 # 4 weeks in minutes
    frontend_dist_dir: Optional[str] = "../client/dist"
    unprocessed_log_dir: str = "../data/"
    cors_allow_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_prefix="MONSTR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("log_sources", mode="before")
    @classmethod
    def _coerce_log_sources(cls, value):
        """Allow comma or newline separated env strings for log sources."""
        if value in (None, ""):
            return []
        if isinstance(value, str):
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
    def parsed_log_sources(self) -> List[Tuple[str, Path]]:
        """Normalize declared log node specifications into name/path tuples."""
        parsed: List[Tuple[str, Path]] = []
        for raw in self.log_sources:
            try:
                node_name, path_spec = raw.split(":", 1)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid node specification '{raw}'. Expected format NAME:PATH."
                ) from exc

            node_name = node_name.strip()
            path_spec = path_spec.strip()

            if not node_name:
                raise ValueError(f"Node specification '{raw}' is missing a node name.")
            if not path_spec:
                raise ValueError(f"Node specification '{raw}' is missing a log path.")

            path = Path(path_spec).expanduser().resolve()
            parsed.append((node_name, path))

        return parsed

    @property
    def sanitized_log_sources(self) -> List[Path]:
        """Normalize declared log source paths."""
        return [path for _, path in self.parsed_log_sources]

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

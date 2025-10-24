from pathlib import Path
from typing import List, Optional

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
    retention_minutes: int = 1440
    frontend_dist_dir: Optional[str] = "../client/dist"

    model_config = SettingsConfigDict(
        env_prefix="MONSTR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_path(self) -> Path:
        """Return the on-disk path for the SQLite database when applicable."""
        if self.database_url.startswith("sqlite"):
            raw_path = self.database_url.split("///", maxsplit=1)[-1]
            return Path(raw_path).expanduser().resolve()
        raise ValueError("Database URL is not pointing to a SQLite database")

    @property
    def sanitized_log_sources(self) -> List[Path]:
        """Normalize declared log source paths."""
        return [Path(source).expanduser().resolve() for source in self.log_sources]

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

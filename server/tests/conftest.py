from __future__ import annotations

import pytest

from server.src.config import Settings
from server.src.database import configure_database


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Ensure each test uses an isolated SQLite database file."""
    db_file = tmp_path / "test.db"
    database_url = f"sqlite+aiosqlite:///{db_file}"

    monkeypatch.setenv("MONSTR_DATABASE_URL", database_url)

    test_settings = Settings(
        database_url=database_url,
        sources=[],
        unprocessed_log_dir=str(tmp_path / "unprocessed"),
    )
    configure_database(test_settings)

    yield

    monkeypatch.delenv("MONSTR_DATABASE_URL", raising=False)
    configure_database(Settings())

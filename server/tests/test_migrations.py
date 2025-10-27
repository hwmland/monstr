from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from server.src import database, migrations
from server.src.config import Settings


@pytest.mark.asyncio
async def test_schema_version_initialized(tmp_path: Path) -> None:
    db_file = tmp_path / "schema_version.db"
    settings = Settings(database_url=f"sqlite+aiosqlite:///{db_file}")

    database.configure_database(settings)
    await database.init_database(settings)

    with sqlite3.connect(db_file) as connection:
        cursor = connection.execute("SELECT version FROM schema_version WHERE id = 1")
        version = cursor.fetchone()[0]

    assert version == migrations.LATEST_SCHEMA_VERSION

    # Reset the database configuration back to defaults to avoid side effects for other tests.
    database.configure_database(Settings())


@pytest.mark.asyncio
async def test_migrates_source_and_satellite_columns(tmp_path: Path) -> None:
    db_file = tmp_path / "legacy.db"
    settings = Settings(database_url=f"sqlite+aiosqlite:///{db_file}")

    # Create a legacy schema without schema_version and with unconstrained source columns.
    db_file.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_file) as connection:
        connection.execute(
            """
            CREATE TABLE logentry (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                level TEXT,
                area TEXT,
                action TEXT,
                details TEXT
            )
            """
        )
        connection.execute("CREATE INDEX ix_logentry_source ON logentry (source)")
        connection.execute(
            "INSERT INTO logentry (id, source, timestamp, level, area, action, details) "
            "VALUES (1, ?, '2024-01-01T00:00:00Z', 'info', 'area', 'action', '{}')",
            ("l" * 50,),
        )
        connection.execute(
            """
            CREATE TABLE transfer (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                action TEXT,
                is_success INTEGER,
                piece_id TEXT,
                satellite_id TEXT,
                is_repair INTEGER,
                size INTEGER,
                offset INTEGER,
                remote_address TEXT
            )
            """
        )
        connection.execute("CREATE INDEX ix_transfer_source ON transfer (source)")
        connection.execute(
            "INSERT INTO transfer (id, source, timestamp, action, is_success, piece_id, "
            "satellite_id, is_repair, size) VALUES (1, ?, '2024-01-01T00:00:00Z', 'DL', 1, 'piece', ?, 0, 100)",
            ("x" * 50, "s" * 100),
        )

    database.configure_database(settings)
    await database.init_database(settings)

    with sqlite3.connect(db_file) as connection:
        cursor = connection.execute("SELECT version FROM schema_version WHERE id = 1")
        version = cursor.fetchone()[0]
        assert version == migrations.LATEST_SCHEMA_VERSION

    logentry_columns = connection.execute("PRAGMA table_info(logentry)").fetchall()
    logentry_source = next(col for col in logentry_columns if col[1] == "source")
    assert "32" in logentry_source[2]

    transfer_columns = connection.execute("PRAGMA table_info(transfer)").fetchall()
    source_column = next(col for col in transfer_columns if col[1] == "source")
    assert "32" in source_column[2]
    satellite_column = next(col for col in transfer_columns if col[1] == "satellite_id")
    assert "64" in satellite_column[2]

    log_row = connection.execute("SELECT source FROM logentry WHERE id = 1").fetchone()
    assert log_row[0] == "l" * 32

    row = connection.execute("SELECT source, satellite_id FROM transfer WHERE id = 1").fetchone()
    assert row[0] == "x" * 32
    assert row[1] == "s" * 64

    database.configure_database(Settings())

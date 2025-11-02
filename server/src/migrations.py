from __future__ import annotations

import logging
from server.src.core.logging import get_logger

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection

from . import models

logger = get_logger(__name__)

def _create_schema_version_table(conn: Connection) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL
            )
            """
        )
    )
    conn.execute(
        text("INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 0)")
    )


def _get_schema_version(conn: Connection) -> int:
    result = conn.execute(text("SELECT version FROM schema_version WHERE id = 1"))
    value = result.scalar()
    return int(value or 0)


def _set_schema_version(conn: Connection, version: int) -> None:
    conn.execute(
        text("UPDATE schema_version SET version = :version WHERE id = 1"),
        {"version": version},
    )


def _quote_identifier(identifier: str) -> str:
    return f'"{identifier}"'


def _rebuild_table_with_capped_columns(
    conn: Connection, table, capped_columns: dict[str, int]
) -> None:
    inspector = inspect(conn)
    table_name = table.name
    if not inspector.has_table(table_name):
        logger.info("Skipping rebuild for table %s (table missing)", table_name)
        return
    existing_indexes = inspector.get_indexes(table_name)

    logger.info(
        "Rebuilding table %s with capped columns: %s",
        table_name,
        ", ".join(f"{column}({length})" for column, length in capped_columns.items()),
    )
    temp_table = f"{table_name}__old"
    conn.execute(text(f"ALTER TABLE {_quote_identifier(table_name)} RENAME TO {_quote_identifier(temp_table)}"))

    for index in existing_indexes:
        index_name = index["name"]
        if index_name:
            conn.execute(text(f"DROP INDEX IF EXISTS {_quote_identifier(index_name)}"))

    table.create(conn)

    column_names = [column.name for column in table.columns]
    quoted_columns = ", ".join(_quote_identifier(column) for column in column_names)

    select_columns = []
    for column in column_names:
        if column in capped_columns:
            length = capped_columns[column]
            select_columns.append(
                f"substr({_quote_identifier(column)}, 1, {length}) AS {_quote_identifier(column)}"
            )
        else:
            select_columns.append(_quote_identifier(column))
    select_clause = ", ".join(select_columns)

    conn.execute(
        text(
            f"INSERT INTO {_quote_identifier(table_name)} ({quoted_columns}) "
            f"SELECT {select_clause} FROM {_quote_identifier(temp_table)}"
        )
    )
    conn.execute(text(f"DROP TABLE {_quote_identifier(temp_table)}"))
    logger.info("Finished rebuild for table %s", table_name)


def _migrate_0_to_1(conn: Connection) -> None:
    logger.info("Starting migration 0 -> 1")
    for table, capped_columns in (
        (models.LogEntry.__table__, {"source": 32}),
        (models.Transfer.__table__, {"source": 32, "satellite_id": 64}),
        (models.Reputation.__table__, {"source": 32, "satellite_id": 64}),
    ):
        _rebuild_table_with_capped_columns(conn, table, capped_columns)
    logger.info("Ensuring transfer_grouped table exists")
    models.TransferGrouped.__table__.create(conn, checkfirst=True)
    # inspector is used below for schema checks
    inspector = inspect(conn)
    # Ensure column 'is_processed' exists on existing transfer tables.
    transfer_table_name = models.Transfer.__table__.name
    if inspector.has_table(transfer_table_name):
        cols = {col['name'] for col in inspector.get_columns(transfer_table_name)}
        if 'is_processed' not in cols:
            # SQLite supports adding a column with a default value.
            conn.execute(
                text(
                    f'ALTER TABLE "{transfer_table_name}" ADD COLUMN "is_processed" INTEGER NOT NULL DEFAULT 0'
                )
            )
    logger.info("Completed migration 0 -> 1")


MigrationFunc = type(_migrate_0_to_1)

MIGRATIONS = (_migrate_0_to_1,)
LATEST_SCHEMA_VERSION = len(MIGRATIONS)


def apply_migrations(conn: Connection) -> None:
    _create_schema_version_table(conn)
    current_version = _get_schema_version(conn)

    target_version = LATEST_SCHEMA_VERSION
    if current_version > target_version:
        raise RuntimeError(
            f"Database schema version {current_version} is newer than supported version {target_version}."
        )

    for index, migration in enumerate(MIGRATIONS, start=1):
        if current_version < index:
            logger.info("Applying migration step %d", index)
            migration(conn)
            _set_schema_version(conn, index)
            current_version = index

    if current_version == 0 and target_version == 0:
        # Ensure the schema_version row is initialized even when there are no migrations.
        _set_schema_version(conn, 0)


async def run_migrations(connection: AsyncConnection) -> None:
    await connection.run_sync(apply_migrations)

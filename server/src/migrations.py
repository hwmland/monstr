from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection

from server.src.core.logging import get_logger

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


def _migrate_1_to_2(conn: Connection) -> None:
    """Add an index on the transfer.is_processed column to speed up scans.

    This migration creates an index if it does not already exist. It is safe to
    run multiple times (uses IF NOT EXISTS) and checks the table exists first.
    """
    logger.info("Starting migration 1 -> 2: add index on transfer.is_processed")

    inspector = inspect(conn)
    transfer_table_name = models.Transfer.__table__.name
    if not inspector.has_table(transfer_table_name):
        logger.info("Skipping index creation: table %s does not exist", transfer_table_name)
        return

    # Use a deterministic index name
    index_name = f"ix_{transfer_table_name}_is_processed"
    # Create index if it does not exist. SQLite supports IF NOT EXISTS.
    conn.execute(
        text(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{transfer_table_name}" ("is_processed")')
    )

    logger.info("Completed migration 1 -> 2")


def _migrate_2_to_3(conn: Connection) -> None:
    """Create HeldAmount table to store per-node held payout records."""
    logger.info("Starting migration 2 -> 3: create HeldAmount table")
    models.HeldAmount.__table__.create(conn, checkfirst=True)
    logger.info("Completed migration 2 -> 3")


def _migrate_3_to_4(conn: Connection) -> None:
    """Create Paystub table for monthly payout snapshots."""
    logger.info("Starting migration 3 -> 4: create Paystub table")
    models.Paystub.__table__.create(conn, checkfirst=True)
    logger.info("Completed migration 3 -> 4")


def _migrate_4_to_5(conn: Connection) -> None:
    """Create DiskUsage table for disk usage snapshots."""
    logger.info("Starting migration 4 -> 5: create DiskUsage table")
    models.DiskUsage.__table__.create(conn, checkfirst=True)
    logger.info("Completed migration 4 -> 5")


def _migrate_5_to_6(conn: Connection) -> None:
    """Create SatelliteUsage table for per-satellite bandwidth snapshots."""
    logger.info("Starting migration 5 -> 6: create SatelliteUsage table")
    models.SatelliteUsage.__table__.create(conn, checkfirst=True)
    logger.info("Completed migration 5 -> 6")


def _migrate_6_to_7(conn: Connection) -> None:
    """Add indexes on transfer_grouped.interval_end and transfer_grouped.granularity."""
    logger.info("Starting migration 6 -> 7: add indexes on transfer_grouped.interval_end and granularity")

    inspector = inspect(conn)
    table_name = models.TransferGrouped.__table__.name
    if not inspector.has_table(table_name):
        logger.info("Skipping index creation: table %s does not exist", table_name)
        return

    # deterministic index names
    index_interval_end = f"ix_{table_name}_interval_end"
    index_granularity = f"ix_{table_name}_granularity"

    conn.execute(text(f'CREATE INDEX IF NOT EXISTS "{index_interval_end}" ON "{table_name}" ("interval_end")'))
    conn.execute(text(f'CREATE INDEX IF NOT EXISTS "{index_granularity}" ON "{table_name}" ("granularity")'))

    logger.info("Completed migration 6 -> 7")



MigrationFunc = type(_migrate_0_to_1)

MIGRATIONS = (
    _migrate_0_to_1,
    _migrate_1_to_2,
    _migrate_2_to_3,
    _migrate_3_to_4,
    _migrate_4_to_5,
    _migrate_5_to_6,
    _migrate_6_to_7,
)
LATEST_SCHEMA_VERSION = len(MIGRATIONS)


def apply_migrations(conn: Connection) -> None:
    _create_schema_version_table(conn)
    current_version = _get_schema_version(conn)
    target_version = LATEST_SCHEMA_VERSION
    if current_version > target_version:
        raise RuntimeError(
            f"Database schema version {current_version} is newer than supported version {target_version}."
        )

    # If the database is brand-new (only the schema_version table exists),
    # initialize it immediately to the target version and skip running
    # migrations — there is nothing to migrate on a fresh DB.
    inspector = inspect(conn)
    existing_tables = [t for t in inspector.get_table_names()]
    # Consider DB new when only schema_version exists (or no user tables)
    user_tables = [t for t in existing_tables if t != "schema_version"]
    if current_version == 0 and not user_tables:
        logger.info("New database detected: initializing schema_version to %d and skipping migrations", target_version)
        _set_schema_version(conn, target_version)
        return
    logger.info(
        "Database schema version at start: current=%d, target=%d",
        current_version,
        target_version,
    )

    for index, migration in enumerate(MIGRATIONS, start=1):
        if current_version < index:
            logger.info("Applying migration step %d", index)
            migration(conn)
            _set_schema_version(conn, index)
            current_version = index
    # Ensure the schema_version row reflects the actual (target) version after migrations.
    _set_schema_version(conn, target_version)


async def run_migrations(connection: AsyncConnection) -> None:
    await connection.run_sync(apply_migrations)

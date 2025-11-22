from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from .config import Settings
from .migrations import run_migrations

settings = Settings()
engine: AsyncEngine | None = None
SessionFactory: async_sessionmaker[AsyncSession]


def configure_database(config: Settings | None = None) -> None:
    """(Re)Initialize the async engine and session factory for the specified settings."""
    global settings, engine, SessionFactory

    settings = config or Settings()

    if engine is not None:
        engine.sync_engine.dispose()

    engine = create_async_engine(settings.database_url, echo=settings.sql_echo, future=True)
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


configure_database()

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a scoped async session for request handlers."""
    async with SessionFactory() as session:
        yield session


async def init_database(config: Settings | None = None) -> None:
    """Create the database directory and tables if they do not exist."""
    cfg = config or settings

    if cfg.database_url.startswith("sqlite"):
        db_path = cfg.database_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure the file exists and is writable. If the file cannot be opened
        # for appending the application would otherwise raise an obscure
        # OperationalError later; detect and provide a clearer diagnostic.
        try:
            # Create the file if it does not exist and ensure we can open it
            # for appending. On Windows this will succeed even if the file is
            # marked read-only for some APIs, but attempting to write later
            # will fail; we attempt to flip the writable bit when possible.
            try:
                with open(db_path, "a", encoding="utf-8"):
                    pass
            except PermissionError:
                # If the file exists and we're on Windows, try clearing the
                # read-only attribute to be helpful for local development.
                import os
                import stat

                if os.name == "nt" and db_path.exists():
                    try:
                        current_mode = db_path.stat().st_mode
                        # Remove read-only bit for owner
                        db_path.chmod(current_mode | stat.S_IWRITE)
                        with open(db_path, "a", encoding="utf-8"):
                            pass
                    except Exception:
                        # fall through to outer PermissionError handling
                        raise
                else:
                    raise
        except PermissionError as exc:
            raise RuntimeError(
                f"Cannot write to database file {db_path!s}: permission denied. "
                "Ensure the file is writable and not marked read-only, or run the "
                "process with sufficient privileges."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"Unable to create or access database file {db_path!s}: {exc!s}"
            ) from exc

    if engine is None:
        raise RuntimeError("Database engine is not configured")

    async with engine.begin() as connection:
        await run_migrations(connection)
        await connection.run_sync(SQLModel.metadata.create_all)

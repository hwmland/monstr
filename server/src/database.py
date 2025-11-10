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

    if engine is None:
        raise RuntimeError("Database engine is not configured")

    async with engine.begin() as connection:
        await run_migrations(connection)
        await connection.run_sync(SQLModel.metadata.create_all)

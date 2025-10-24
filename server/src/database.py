from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from .config import Settings

settings = Settings()

engine = create_async_engine(settings.database_url, echo=settings.sql_echo, future=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a scoped async session for request handlers."""
    async with SessionFactory() as session:
        yield session


async def init_database() -> None:
    """Create the database directory and tables if they do not exist."""
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

    from . import models  # noqa: F401 - ensure models are registered with SQLModel metadata

    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

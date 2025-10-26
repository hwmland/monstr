from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from server.src.config import Settings
from server.src.core.app import create_app
from server.src import database
from server.src.models import LogEntry
from server.src.repositories.log_entries import LogEntryRepository
from server.src.schemas import LogEntryCreate


@pytest.mark.asyncio
async def test_list_logs_supports_additional_filters(tmp_path) -> None:
    settings = Settings(log_sources=[], unprocessed_log_dir=str(tmp_path))
    app = create_app(settings)

    await database.init_database()
    transport = ASGITransport(app=app)

    entries = [
        LogEntryCreate(
            source="node-a",
            timestamp=datetime(2025, 10, 25, 12, 0, tzinfo=timezone.utc),
            level="INFO",
            area="collector",
            action="status",
            details={"duration": "5s"},
        ),
        LogEntryCreate(
            source="node-a",
            timestamp=datetime(2025, 10, 25, 12, 1, tzinfo=timezone.utc),
            level="WARN",
            area="reputation:service",
            action="node scores worsened",
            details={"satellite": "123"},
        ),
        LogEntryCreate(
            source="node-b",
            timestamp=datetime(2025, 10, 25, 12, 2, tzinfo=timezone.utc),
            level="ERROR",
            area="hashstore",
            action="failed",
            details={"reason": "boom"},
        ),
    ]

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with database.SessionFactory() as session:
            await session.execute(delete(LogEntry))
            await session.commit()

            repository = LogEntryRepository(session)
            await repository.create_many(entries)

        response = await client.get(
            "/api/logs/",
            params={
                "source": "node-a",
                "level": "WARN",
                "area": "reputation:service",
                "action": "node scores worsened",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["source"] == "node-a"
        assert body[0]["level"] == "WARN"
        assert body[0]["area"] == "reputation:service"
        assert body[0]["action"] == "node scores worsened"

        response = await client.get(
            "/api/logs/",
            params={
                "source": "node-a",
                "level": "WARN",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["area"] == "reputation:service"

        response = await client.get(
            "/api/logs/",
            params={
                "area": "hashstore",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["source"] == "node-b"
        assert body[0]["level"] == "ERROR"

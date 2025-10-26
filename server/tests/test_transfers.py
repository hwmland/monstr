from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from server.src.config import Settings
from server.src.core.app import create_app
from server.src import database
from server.src.models import Transfer
from server.src.repositories.transfers import TransferRepository
from server.src.schemas import TransferCreate


@pytest.mark.asyncio
async def test_list_transfers_empty() -> None:
    app = create_app(Settings(log_sources=[]))
    await database.init_database()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with database.SessionFactory() as session:
            await session.execute(delete(Transfer))
            await session.commit()

        response = await client.get("/api/transfers")

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
async def test_list_transfers_filters() -> None:
    app = create_app(Settings(log_sources=[]))
    payload = TransferCreate(
        source="node-a",
        timestamp=datetime.now(timezone.utc),
        action="DL",
        is_success=True,
        piece_id="piece-123",
        satellite_id="sat-1",
        is_repair=False,
        size=2048,
        offset=0,
        remote_address="1.2.3.4:7777",
    )

    await database.init_database()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with database.SessionFactory() as session:
            await session.execute(delete(Transfer))
            await session.commit()

            repository = TransferRepository(session)
            await repository.create_many([payload])

        response = await client.get(
            "/api/transfers",
            params={"source": "node-a", "action": "DL"},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["piece_id"] == payload.piece_id
    assert body[0]["satellite_id"] == payload.satellite_id
    assert body[0]["is_success"] is True
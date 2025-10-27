from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


@pytest.mark.asyncio
async def test_transfer_actuals_aggregates_recent_activity() -> None:
    app = create_app(Settings(log_sources=[]))
    await database.init_database()
    transport = ASGITransport(app=app)

    now = datetime.now(timezone.utc)
    within_window = now - timedelta(days=3, minutes=10)
    outside_window = now - timedelta(days=3, hours=2)

    entries = [
        TransferCreate(
            source="node-a",
            timestamp=within_window,
            action="DL",
            is_success=True,
            piece_id="piece-success",
            satellite_id="sat-1",
            is_repair=False,
            size=2048,
            offset=0,
            remote_address="1.2.3.4:7777",
        ),
        TransferCreate(
            source="node-a",
            timestamp=within_window,
            action="DL",
            is_success=False,
            piece_id="piece-failure",
            satellite_id="sat-1",
            is_repair=False,
            size=4096,
            offset=0,
            remote_address="1.2.3.4:7778",
        ),
        TransferCreate(
            source="node-a",
            timestamp=within_window,
            action="DL",
            is_success=True,
            piece_id="piece-repair",
            satellite_id="sat-1",
            is_repair=True,
            size=1024,
            offset=0,
            remote_address="1.2.3.4:7776",
        ),
        TransferCreate(
            source="node-b",
            timestamp=within_window,
            action="UL",
            is_success=True,
            piece_id="piece-upload",
            satellite_id="sat-2",
            is_repair=False,
            size=512,
            offset=0,
            remote_address="1.2.3.4:7779",
        ),
        TransferCreate(
            source="node-b",
            timestamp=within_window,
            action="UL",
            is_success=True,
            piece_id="piece-upload-repair",
            satellite_id="sat-2",
            is_repair=True,
            size=256,
            offset=0,
            remote_address="1.2.3.4:7775",
        ),
        TransferCreate(
            source="node-b",
            timestamp=outside_window,
            action="UL",
            is_success=True,
            piece_id="piece-old",
            satellite_id="sat-2",
            is_repair=False,
            size=9999,
            offset=0,
            remote_address="1.2.3.4:7780",
        ),
    ]

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with database.SessionFactory() as session:
            repository = TransferRepository(session)
            await repository.create_many(entries)

        response = await client.post(
            "/api/transfers/actual",
            json={"nodes": ["node-a", "node-b"]},
        )

    assert response.status_code == 200
    body = response.json()
    assert "startTime" in body and "endTime" in body

    download = body["download"]
    upload = body["upload"]

    assert download["normal"]["operationsTotal"] == 2
    assert download["normal"]["operationsSuccess"] == 1
    assert download["normal"]["dataBytes"] == 2048
    assert download["normal"]["rate"] == pytest.approx(2048 / 3600)

    assert download["repair"]["operationsTotal"] == 1
    assert download["repair"]["operationsSuccess"] == 1
    assert download["repair"]["dataBytes"] == 1024
    assert download["repair"]["rate"] == pytest.approx(1024 / 3600)

    assert upload["normal"]["operationsTotal"] == 1
    assert upload["normal"]["operationsSuccess"] == 1
    assert upload["normal"]["dataBytes"] == 512
    assert upload["normal"]["rate"] == pytest.approx(512 / 3600)

    assert upload["repair"]["operationsTotal"] == 1
    assert upload["repair"]["operationsSuccess"] == 1
    assert upload["repair"]["dataBytes"] == 256
    assert upload["repair"]["rate"] == pytest.approx(256 / 3600)

    satellites = sorted(body["satellites"], key=lambda item: item["satelliteId"])
    assert len(satellites) == 2

    sat1 = satellites[0]
    assert sat1["satelliteId"] == "sat-1"
    assert sat1["download"]["normal"]["operationsTotal"] == 2
    assert sat1["download"]["repair"]["operationsTotal"] == 1
    assert sat1["upload"]["normal"]["operationsTotal"] == 0
    assert sat1["download"]["normal"]["dataBytes"] == 2048
    assert sat1["download"]["repair"]["dataBytes"] == 1024

    sat2 = satellites[1]
    assert sat2["satelliteId"] == "sat-2"
    assert sat2["download"]["normal"]["operationsTotal"] == 0
    assert sat2["upload"]["normal"]["operationsTotal"] == 1
    assert sat2["upload"]["repair"]["operationsTotal"] == 1
    assert sat2["upload"]["normal"]["dataBytes"] == 512
    assert sat2["upload"]["repair"]["dataBytes"] == 256

    # Ensure node filtering works
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response_filtered = await client.post(
            "/api/transfers/actual",
            json={"nodes": ["node-b"]},
        )

    assert response_filtered.status_code == 200
    filtered_body = response_filtered.json()
    assert filtered_body["download"]["normal"]["operationsTotal"] == 0
    assert filtered_body["download"]["repair"]["operationsTotal"] == 0
    assert filtered_body["upload"]["normal"]["operationsTotal"] == 1
    assert filtered_body["upload"]["repair"]["operationsTotal"] == 1
    assert filtered_body["upload"]["normal"]["dataBytes"] == 512
    assert filtered_body["upload"]["repair"]["dataBytes"] == 256

    filtered_satellites = filtered_body["satellites"]
    assert len(filtered_satellites) == 1
    assert filtered_satellites[0]["satelliteId"] == "sat-2"
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from server.src import database
from server.src.config import Settings
from server.src.core.app import create_app
from server.src.repositories.transfer_grouped import TransferGroupedRepository
from server.src.schemas import TransferGroupedCreate


@pytest.mark.asyncio
async def test_list_transfer_grouped_filters() -> None:
    app_settings = Settings(sources=[])
    app = create_app(app_settings)
    await database.init_database(app_settings)
    transport = ASGITransport(app=app)

    interval_start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    interval_end = interval_start + timedelta(hours=1)

    entries = [
        TransferGroupedCreate(
            source="node-a",
            satellite_id="sat-1",
            interval_start=interval_start,
            interval_end=interval_end,
            size_class="1K",
            size_dl_succ_nor=1024,
            count_dl_succ_nor=1,
        ),
        TransferGroupedCreate(
            source="node-b",
            satellite_id="sat-2",
            interval_start=interval_start,
            interval_end=interval_end,
            size_class="4K",
            size_ul_succ_nor=2048,
            count_ul_succ_nor=2,
        ),
    ]

    async with database.SessionFactory() as session:
        repository = TransferGroupedRepository(session)
        await repository.create_many(entries)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/transfer-grouped",
            params={"source": "node-a"},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["source"] == "node-a"
    assert item["satelliteId"] == "sat-1"
    assert item["sizeClass"] == "1K"
    assert item["sizeDlSuccNor"] == 1024
    assert item["countDlSuccNor"] == 1

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response_class = await client.get(
            "/api/transfer-grouped",
            params={"sizeClass": "4K"},
        )

    assert response_class.status_code == 200
    body_class = response_class.json()
    assert len(body_class) == 1
    assert body_class[0]["source"] == "node-b"
    assert body_class[0]["sizeClass"] == "4K"

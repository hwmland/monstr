from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from server.src import database
from server.src.config import Settings
from server.src.core.app import create_app
from server.src.models import DiskUsage


@pytest.mark.asyncio
async def test_list_disk_usage() -> None:
    app_settings = Settings(sources=[])
    app = create_app(app_settings)
    await database.init_database(app_settings)
    transport = ASGITransport(app=app)

    now = datetime.now(timezone.utc)

    test_record = DiskUsage(
        source="node-a",
        period="2025-11",
        max_usage=1000000000,
        trash_at_max_usage=50000000,
        max_trash=60000000,
        usage_at_max_trash=950000000,
        usage_end=980000000,
        free_end=200000000,
        trash_end=55000000,
        max_usage_at=now,
        max_trash_at=now,
    )

    async with database.SessionFactory() as session:
        session.add(test_record)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/diskusage")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["source"] == "node-a"
    assert item["period"] == "2025-11"
    assert item["maxUsage"] == 1000000000
    assert item["trashAtMaxUsage"] == 50000000
    assert item["maxTrash"] == 60000000
    assert item["usageEnd"] == 980000000
    assert item["freeEnd"] == 200000000


@pytest.mark.asyncio
async def test_filter_disk_usage_by_source() -> None:
    app_settings = Settings(sources=[])
    app = create_app(app_settings)
    await database.init_database(app_settings)
    transport = ASGITransport(app=app)

    now = datetime.now(timezone.utc)

    records = [
        DiskUsage(
            source="node-a",
            period="2025-11",
            max_usage=1000000000,
            trash_at_max_usage=50000000,
            max_trash=60000000,
            usage_at_max_trash=950000000,
            usage_end=980000000,
            free_end=200000000,
            trash_end=55000000,
            max_usage_at=now,
            max_trash_at=now,
        ),
        DiskUsage(
            source="node-b",
            period="2025-11",
            max_usage=2000000000,
            trash_at_max_usage=100000000,
            max_trash=120000000,
            usage_at_max_trash=1950000000,
            usage_end=1980000000,
            free_end=300000000,
            trash_end=110000000,
            max_usage_at=now,
            max_trash_at=now,
        ),
    ]

    async with database.SessionFactory() as session:
        session.add_all(records)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/diskusage", params={"source": "node-a"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["source"] == "node-a"

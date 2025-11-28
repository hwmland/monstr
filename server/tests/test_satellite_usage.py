from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from server.src import database
from server.src.config import Settings
from server.src.core.app import create_app
from server.src.models import SatelliteUsage


@pytest.mark.asyncio
async def test_list_satellite_usage() -> None:
    settings = Settings(sources=[])
    app = create_app(settings)
    await database.init_database(settings)
    transport = ASGITransport(app=app)

    record = SatelliteUsage(
        source="node-a",
        satellite_id="sat-1",
        period="2025-11-24",
        dl_usage=100,
        dl_repair=10,
        dl_audit=5,
        ul_usage=80,
        ul_repair=8,
        delete=2,
        disk_usage=500,
    )

    async with database.SessionFactory() as session:
        session.add(record)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/satelliteusage")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["source"] == "node-a"
    assert item["satelliteId"] == "sat-1"
    assert item["period"] == "2025-11-24"
    assert item["dlUsage"] == 100
    assert item["dlRepair"] == 10
    assert item["dlAudit"] == 5
    assert item["ulUsage"] == 80
    assert item["ulRepair"] == 8
    assert item["delete"] == 2
    assert item["diskUsage"] == 500


@pytest.mark.asyncio
async def test_filter_satellite_usage_by_satellite() -> None:
    settings = Settings(sources=[])
    app = create_app(settings)
    await database.init_database(settings)
    transport = ASGITransport(app=app)

    records = [
        SatelliteUsage(
            source="node-a",
            satellite_id="sat-1",
            period="2025-11-24",
            dl_usage=100,
            dl_repair=10,
            dl_audit=5,
            ul_usage=80,
            ul_repair=8,
            delete=2,
            disk_usage=400,
        ),
        SatelliteUsage(
            source="node-a",
            satellite_id="sat-2",
            period="2025-11-24",
            dl_usage=200,
            dl_repair=20,
            dl_audit=15,
            ul_usage=180,
            ul_repair=18,
            delete=5,
            disk_usage=None,
        ),
    ]

    async with database.SessionFactory() as session:
        session.add_all(records)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/satelliteusage", params={"satelliteId": "sat-1"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["satelliteId"] == "sat-1"

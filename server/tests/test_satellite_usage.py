from __future__ import annotations

from datetime import date, timedelta

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


@pytest.mark.asyncio
async def test_satellite_usage_usage_endpoint() -> None:
    settings = Settings(sources=[])
    app = create_app(settings)
    await database.init_database(settings)
    transport = ASGITransport(app=app)

    today = date.today()
    p1 = (today - timedelta(days=3)).isoformat()
    p2 = (today - timedelta(days=2)).isoformat()
    p3 = (today - timedelta(days=1)).isoformat()

    records = [
        SatelliteUsage(
            source="node-a", satellite_id="sat-1", period=p1,
            dl_usage=10, dl_repair=1, dl_audit=0, ul_usage=5, ul_repair=0, delete=0,
        ),
        SatelliteUsage(
            source="node-a", satellite_id="sat-1", period=p2,
            dl_usage=20, dl_repair=2, dl_audit=1, ul_usage=10, ul_repair=1, delete=0,
        ),
        SatelliteUsage(
            source="node-b", satellite_id="sat-1", period=p2,
            dl_usage=30, dl_repair=3, dl_audit=2, ul_usage=15, ul_repair=2, delete=1,
        ),
        SatelliteUsage(
            source="node-a", satellite_id="sat-1", period=p3,
            dl_usage=40, dl_repair=4, dl_audit=3, ul_usage=20, ul_repair=3, delete=2,
        ),
    ]

    async with database.SessionFactory() as session:
        session.add_all(records)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/satelliteusage/usage",
            json={"numberOfPeriods": 30},
        )

    assert response.status_code == 200
    body = response.json()
    assert "periods" in body
    assert len(body["periods"]) == 3
    assert p3 in body["periods"]
    assert p2 in body["periods"]
    assert p1 in body["periods"]
    # period p2 has 2 records (node-a and node-b)
    assert len(body["periods"][p2]) == 2


@pytest.mark.asyncio
async def test_satellite_usage_usage_filter_by_nodes() -> None:
    settings = Settings(sources=[])
    app = create_app(settings)
    await database.init_database(settings)
    transport = ASGITransport(app=app)

    today = date.today()
    p1 = (today - timedelta(days=1)).isoformat()

    records = [
        SatelliteUsage(
            source="node-a", satellite_id="sat-1", period=p1,
            dl_usage=20, dl_repair=2, dl_audit=1, ul_usage=10, ul_repair=1, delete=0,
        ),
        SatelliteUsage(
            source="node-b", satellite_id="sat-1", period=p1,
            dl_usage=30, dl_repair=3, dl_audit=2, ul_usage=15, ul_repair=2, delete=1,
        ),
    ]

    async with database.SessionFactory() as session:
        session.add_all(records)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/satelliteusage/usage",
            json={"nodes": ["node-a"], "numberOfPeriods": 30},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["periods"]) == 1
    items = body["periods"][p1]
    assert len(items) == 1
    assert items[0]["source"] == "node-a"
    assert items[0]["dlUsage"] == 20


@pytest.mark.asyncio
async def test_satellite_usage_usage_filters_by_date() -> None:
    settings = Settings(sources=[])
    app = create_app(settings)
    await database.init_database(settings)
    transport = ASGITransport(app=app)

    today = date.today()
    recent_period = (today - timedelta(days=1)).isoformat()
    old_period = (today - timedelta(days=10)).isoformat()

    records = [
        SatelliteUsage(
            source="node-a", satellite_id="sat-1", period=recent_period,
            dl_usage=10, dl_repair=1, dl_audit=0, ul_usage=5, ul_repair=0, delete=0,
        ),
        SatelliteUsage(
            source="node-a", satellite_id="sat-1", period=old_period,
            dl_usage=20, dl_repair=2, dl_audit=1, ul_usage=10, ul_repair=1, delete=0,
        ),
    ]

    async with database.SessionFactory() as session:
        session.add_all(records)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # numberOfPeriods=5 means start_period = today - 5 days; old_period (today-10) is excluded
        response = await client.post(
            "/api/satelliteusage/usage",
            json={"numberOfPeriods": 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["periods"]) == 1
    assert recent_period in body["periods"]

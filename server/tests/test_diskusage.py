from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


@pytest.mark.asyncio
async def test_disk_usage_usage_change_with_nodes() -> None:
    app_settings = Settings(sources=[])
    app = create_app(app_settings)
    await database.init_database(app_settings)
    transport = ASGITransport(app=app)

    now = datetime.now(timezone.utc)
    today = now.date()
    yesterday = today - timedelta(days=1)

    today_period = today.isoformat()
    yesterday_period = yesterday.isoformat()

    records = [
        DiskUsage(
            source="node-a",
            period=yesterday_period,
            max_usage=1000,
            trash_at_max_usage=100,
            max_trash=120,
            usage_at_max_trash=900,
            usage_end=900,
            free_end=100,
            trash_end=80,
            max_usage_at=now,
            max_trash_at=now,
        ),
        DiskUsage(
            source="node-a",
            period=today_period,
            max_usage=1200,
            trash_at_max_usage=110,
            max_trash=150,
            usage_at_max_trash=1000,
            usage_end=1100,
            free_end=150,
            trash_end=90,
            max_usage_at=now,
            max_trash_at=now,
        ),
        DiskUsage(
            source="node-b",
            period=today_period,
            max_usage=500,
            trash_at_max_usage=50,
            max_trash=75,
            usage_at_max_trash=450,
            usage_end=400,
            free_end=600,
            trash_end=70,
            max_usage_at=now,
            max_trash_at=now,
        ),
    ]

    async with database.SessionFactory() as session:
        session.add_all(records)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/diskusage/usage-change",
            json={"nodes": ["node-a", "node-b"], "intervalDays": 1},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["currentPeriod"] == today_period
    assert body["referencePeriod"] == yesterday_period

    nodes = body["nodes"]
    assert set(nodes.keys()) == {"node-a", "node-b"}

    node_a = nodes["node-a"]
    assert node_a["usageEnd"] == 1100
    assert node_a["usageChange"] == 200
    assert node_a["freeEnd"] == 150
    assert node_a["freeChange"] == 50
    assert node_a["trashEnd"] == 90
    assert node_a["trashChange"] == 10

    node_b = nodes["node-b"]
    assert node_b["usageEnd"] == 400
    assert node_b["usageChange"] == 400
    assert node_b["freeEnd"] == 600
    assert node_b["freeChange"] == 600
    assert node_b["trashEnd"] == 70
    assert node_b["trashChange"] == 70


@pytest.mark.asyncio
async def test_disk_usage_usage_change_all_nodes() -> None:
    app_settings = Settings(sources=[])
    app = create_app(app_settings)
    await database.init_database(app_settings)
    transport = ASGITransport(app=app)

    now = datetime.now(timezone.utc)
    today = now.date()
    yesterday = today - timedelta(days=1)

    today_period = today.isoformat()
    yesterday_period = yesterday.isoformat()

    records = [
        DiskUsage(
            source="node-a",
            period=yesterday_period,
            max_usage=700,
            trash_at_max_usage=70,
            max_trash=90,
            usage_at_max_trash=650,
            usage_end=650,
            free_end=350,
            trash_end=60,
            max_usage_at=now,
            max_trash_at=now,
        ),
        DiskUsage(
            source="node-c",
            period=today_period,
            max_usage=800,
            trash_at_max_usage=80,
            max_trash=100,
            usage_at_max_trash=750,
            usage_end=750,
            free_end=250,
            trash_end=70,
            max_usage_at=now,
            max_trash_at=now,
        ),
    ]

    async with database.SessionFactory() as session:
        session.add_all(records)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/diskusage/usage-change",
            json={"intervalDays": 1},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["currentPeriod"] == today_period
    assert body["referencePeriod"] == yesterday_period

    nodes = body["nodes"]
    assert list(nodes.keys()) == ["node-a", "node-c"]

    node_a = nodes["node-a"]
    assert node_a["usageEnd"] == 0
    assert node_a["usageChange"] == -650
    assert node_a["trashChange"] == -60
    assert node_a["freeChange"] == -350

    node_c = nodes["node-c"]
    assert node_c["usageEnd"] == 750
    assert node_c["usageChange"] == 750
    assert node_c["trashEnd"] == 70
    assert node_c["trashChange"] == 70


@pytest.mark.asyncio
async def test_disk_usage_usage_endpoint_returns_periods_and_nodes() -> None:
    app_settings = Settings(sources=[])
    app = create_app(app_settings)
    await database.init_database(app_settings)
    transport = ASGITransport(app=app)

    now = datetime.now(timezone.utc)
    today = now.date()
    yesterday = today - timedelta(days=1)

    today_period = today.isoformat()
    yesterday_period = yesterday.isoformat()

    records = [
        DiskUsage(
            source="node-a",
            period=yesterday_period,
            max_usage=800,
            trash_at_max_usage=80,
            max_trash=90,
            usage_at_max_trash=720,
            usage_end=700,
            free_end=300,
            trash_end=60,
            max_usage_at=now - timedelta(hours=12),
            max_trash_at=now - timedelta(hours=11),
        ),
        DiskUsage(
            source="node-a",
            period=today_period,
            max_usage=900,
            trash_at_max_usage=95,
            max_trash=110,
            usage_at_max_trash=810,
            usage_end=830,
            free_end=270,
            trash_end=70,
            max_usage_at=now - timedelta(hours=1),
            max_trash_at=now - timedelta(hours=2),
        ),
        DiskUsage(
            source="node-b",
            period=today_period,
            max_usage=1000,
            trash_at_max_usage=120,
            max_trash=130,
            usage_at_max_trash=860,
            usage_end=840,
            free_end=200,
            trash_end=80,
            max_usage_at=now - timedelta(minutes=30),
            max_trash_at=now - timedelta(minutes=25),
        ),
    ]

    async with database.SessionFactory() as session:
        session.add_all(records)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/diskusage/usage",
            json={"nodes": ["node-a"], "intervalDays": 1, "mode": "end"},
        )

        assert response.status_code == 200
        payload = response.json()
        periods = payload["periods"]
        assert set(periods.keys()) == {yesterday_period, today_period}
        yesterday_node = periods[yesterday_period]["node-a"]
        assert yesterday_node["capacity"] == 300
        assert yesterday_node["usage"] == 700
        assert yesterday_node["trash"] == 60
        yesterday_at = yesterday_node["at"].replace("Z", "+00:00")
        assert yesterday_at == f"{yesterday_period}T00:00:00+00:00"

        response_max = await client.post(
            "/api/diskusage/usage",
            json={"intervalDays": 0, "mode": "maxUsage"},
        )

        assert response_max.status_code == 200
        payload_max = response_max.json()
        today_nodes = payload_max["periods"][today_period]
        assert today_nodes["node-b"]["usage"] == 1000
        assert today_nodes["node-b"]["trash"] == 120
        assert today_nodes["node-b"]["capacity"] == 200
        node_b_at = today_nodes["node-b"]["at"].replace("Z", "+00:00")
        assert node_b_at == (now - timedelta(minutes=30)).isoformat()
        assert "node-a" in today_nodes

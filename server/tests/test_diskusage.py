from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from server.src import database
from server.src.config import Settings
from server.src.core.app import create_app
from server.src.models import DiskUsage


def _make_disk_usage(
    source: str,
    period: str,
    capacity_end: int = 1_000_000_000,
    usefull_end: int = 500_000_000,
    trash_end: int = 50_000_000,
    reclaimable_end: int = 0,
) -> DiskUsage:
    """Helper to build a DiskUsage record with derived usage_end."""
    return DiskUsage(
        source=source,
        period=period,
        capacity_end=capacity_end,
        usefull_end=usefull_end,
        trash_end=trash_end,
        usage_end=usefull_end + trash_end,
        reclaimable_end=reclaimable_end,
    )


@pytest.mark.asyncio
async def test_list_disk_usage() -> None:
    app_settings = Settings(sources=[])
    app = create_app(app_settings)
    await database.init_database(app_settings)
    transport = ASGITransport(app=app)

    test_record = _make_disk_usage(
        source="node-a",
        period="2025-11-01",
        capacity_end=2_000_000_000,
        usefull_end=980_000_000,
        trash_end=55_000_000,
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
    assert item["period"] == "2025-11-01"
    assert item["capacityEnd"] == 2_000_000_000
    assert item["usefullEnd"] == 980_000_000
    assert item["trashEnd"] == 55_000_000
    assert item["usageEnd"] == 980_000_000 + 55_000_000
    assert item["reclaimableEnd"] == 0


@pytest.mark.asyncio
async def test_filter_disk_usage_by_source() -> None:
    app_settings = Settings(sources=[])
    app = create_app(app_settings)
    await database.init_database(app_settings)
    transport = ASGITransport(app=app)

    records = [
        _make_disk_usage(source="node-a", period="2025-11-01"),
        _make_disk_usage(source="node-b", period="2025-11-01"),
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

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    today_period = today.isoformat()
    yesterday_period = yesterday.isoformat()

    records = [
        DiskUsage(
            source="node-a",
            period=yesterday_period,
            capacity_end=1_000,
            usefull_end=900,
            trash_end=80,
            usage_end=980,
            reclaimable_end=0,
        ),
        DiskUsage(
            source="node-a",
            period=today_period,
            capacity_end=1_500,
            usefull_end=1_100,
            trash_end=90,
            usage_end=1_190,
            reclaimable_end=0,
        ),
        DiskUsage(
            source="node-b",
            period=today_period,
            capacity_end=600,
            usefull_end=400,
            trash_end=70,
            usage_end=470,
            reclaimable_end=0,
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
    assert node_a["capacityEnd"] == 1_500
    assert node_a["usefullEnd"] == 1_100
    assert node_a["trashEnd"] == 90
    assert node_a["usageEnd"] == 1_190
    assert node_a["reclaimableEnd"] == 0
    assert node_a["capacityChange"] == 1_500 - 1_000
    assert node_a["usefullChange"] == 1_100 - 900
    assert node_a["trashChange"] == 90 - 80
    assert node_a["usageChange"] == 1_190 - 980
    assert node_a["reclaimableChange"] == 0

    node_b = nodes["node-b"]
    assert node_b["usageEnd"] == 470
    assert node_b["usageChange"] == 470
    assert node_b["trashEnd"] == 70
    assert node_b["trashChange"] == 70
    assert node_b["capacityEnd"] == 600
    assert node_b["capacityChange"] == 600


@pytest.mark.asyncio
async def test_disk_usage_usage_change_all_nodes() -> None:
    app_settings = Settings(sources=[])
    app = create_app(app_settings)
    await database.init_database(app_settings)
    transport = ASGITransport(app=app)

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    today_period = today.isoformat()
    yesterday_period = yesterday.isoformat()

    records = [
        DiskUsage(
            source="node-a",
            period=yesterday_period,
            capacity_end=1_000,
            usefull_end=650,
            trash_end=60,
            usage_end=710,
            reclaimable_end=0,
        ),
        DiskUsage(
            source="node-c",
            period=today_period,
            capacity_end=800,
            usefull_end=750,
            trash_end=70,
            usage_end=820,
            reclaimable_end=0,
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
    assert node_a["usageChange"] == -710
    assert node_a["trashChange"] == -60
    assert node_a["capacityChange"] == -1_000

    node_c = nodes["node-c"]
    assert node_c["usageEnd"] == 820
    assert node_c["usageChange"] == 820
    assert node_c["trashEnd"] == 70
    assert node_c["trashChange"] == 70


@pytest.mark.asyncio
async def test_disk_usage_usage_endpoint_returns_periods_and_nodes() -> None:
    app_settings = Settings(sources=[])
    app = create_app(app_settings)
    await database.init_database(app_settings)
    transport = ASGITransport(app=app)

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    today_period = today.isoformat()
    yesterday_period = yesterday.isoformat()

    records = [
        DiskUsage(
            source="node-a",
            period=yesterday_period,
            capacity_end=1_000,
            usefull_end=700,
            trash_end=60,
            usage_end=760,
            reclaimable_end=0,
        ),
        DiskUsage(
            source="node-a",
            period=today_period,
            capacity_end=1_000,
            usefull_end=830,
            trash_end=70,
            usage_end=900,
            reclaimable_end=0,
        ),
        DiskUsage(
            source="node-b",
            period=today_period,
            capacity_end=2_000,
            usefull_end=840,
            trash_end=80,
            usage_end=920,
            reclaimable_end=0,
        ),
    ]

    async with database.SessionFactory() as session:
        session.add_all(records)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/diskusage/usage",
            json={"nodes": ["node-a"], "intervalDays": 1},
        )

    assert response.status_code == 200
    payload = response.json()
    periods = payload["periods"]
    assert set(periods.keys()) == {yesterday_period, today_period}

    yesterday_node = periods[yesterday_period]["node-a"]
    assert yesterday_node["capacity"] == 1_000
    assert yesterday_node["usage"] == 760   # total = usefull + trash
    assert yesterday_node["trash"] == 60
    yesterday_at = yesterday_node["at"].replace("Z", "+00:00")
    assert yesterday_at == f"{yesterday_period}T00:00:00+00:00"

    today_node_a = periods[today_period]["node-a"]
    assert today_node_a["capacity"] == 1_000
    assert today_node_a["usage"] == 900
    assert today_node_a["trash"] == 70
    assert "node-b" not in periods[today_period]

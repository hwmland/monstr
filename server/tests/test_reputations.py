from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from server.src.config import Settings
from server.src.core.app import create_app
from server.src import database
from server.src.models import Reputation
from server.src.repositories.reputations import ReputationRepository
from server.src.schemas import ReputationCreate


@pytest.mark.asyncio
async def test_list_reputations_empty() -> None:
    app = create_app(Settings(log_sources=[]))
    await database.init_database()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with database.SessionFactory() as session:
            await session.execute(delete(Reputation))
            await session.commit()

        response = await client.get("/api/reputations")

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
async def test_list_reputations_filters() -> None:
    app = create_app(Settings(log_sources=[]))
    payload = ReputationCreate(
        source="node-a",
        satellite_id="sat-1",
        timestamp=datetime.now(timezone.utc),
        audits_total=200,
        audits_success=199,
        score_audit=0.995,
        score_online=0.99,
        score_suspension=1.0,
    )

    await database.init_database()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with database.SessionFactory() as session:
            await session.execute(delete(Reputation))
            await session.commit()

            repository = ReputationRepository(session)
            await repository.upsert_many([payload])

        response = await client.get(
            "/api/reputations",
            params={"source": "node-a", "satellite_id": "sat-1"},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    record = body[0]
    assert record["source"] == payload.source
    assert record["satellite_id"] == payload.satellite_id
    assert record["audits_total"] == payload.audits_total
    assert record["audits_success"] == payload.audits_success
    assert record["score_audit"] == pytest.approx(payload.score_audit)
    assert record["score_online"] == pytest.approx(payload.score_online)
    assert record["score_suspension"] == pytest.approx(payload.score_suspension)


@pytest.mark.asyncio
async def test_list_reputations_panel_grouped_by_node() -> None:
    app = create_app(Settings(log_sources=[]))
    timestamp = datetime.now(timezone.utc)

    records = [
        ReputationCreate(
            source="node-a",
            satellite_id="sat-1",
            timestamp=timestamp,
            audits_total=200,
            audits_success=199,
            score_audit=0.995,
            score_online=0.99,
            score_suspension=1.0,
        ),
        ReputationCreate(
            source="node-a",
            satellite_id="sat-2",
            timestamp=timestamp,
            audits_total=150,
            audits_success=150,
            score_audit=1.0,
            score_online=1.0,
            score_suspension=1.0,
        ),
        ReputationCreate(
            source="node-b",
            satellite_id="sat-3",
            timestamp=timestamp,
            audits_total=90,
            audits_success=88,
            score_audit=0.977,
            score_online=0.96,
            score_suspension=0.99,
        ),
    ]

    await database.init_database()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with database.SessionFactory() as session:
            await session.execute(delete(Reputation))
            await session.commit()

            repository = ReputationRepository(session)
            await repository.upsert_many(records)

        response = await client.post(
            "/api/reputations/panel",
            json={"nodes": ["node-a", "node-b"]},
        )

    assert response.status_code == 200
    body = response.json()
    assert [item["node"] for item in body] == ["node-a", "node-b"]

    node_a = body[0]
    assert len(node_a["satellites"]) == 2
    assert [sat["satellite_id"] for sat in node_a["satellites"]] == ["sat-1", "sat-2"]

    node_b = body[1]
    assert len(node_b["satellites"]) == 1
    assert node_b["satellites"][0]["satellite_id"] == "sat-3"


@pytest.mark.asyncio
async def test_list_reputations_panel_includes_empty_nodes() -> None:
    app = create_app(Settings(log_sources=[]))
    timestamp = datetime.now(timezone.utc)

    record = ReputationCreate(
        source="node-a",
        satellite_id="sat-1",
        timestamp=timestamp,
        audits_total=10,
        audits_success=10,
        score_audit=1.0,
        score_online=1.0,
        score_suspension=1.0,
    )

    await database.init_database()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with database.SessionFactory() as session:
            await session.execute(delete(Reputation))
            await session.commit()

            repository = ReputationRepository(session)
            await repository.upsert_many([record])

        response = await client.post(
            "/api/reputations/panel",
            json={"nodes": ["node-a", "node-b"]},
        )

    assert response.status_code == 200
    body = response.json()
    assert [item["node"] for item in body] == ["node-a", "node-b"]
    node_b = body[1]
    assert node_b["satellites"] == []


@pytest.mark.asyncio
async def test_list_reputations_panel_fetch_all_when_empty_request() -> None:
    app = create_app(Settings(log_sources=[]))
    timestamp = datetime.now(timezone.utc)

    records = [
        ReputationCreate(
            source="node-a",
            satellite_id="sat-1",
            timestamp=timestamp,
            audits_total=50,
            audits_success=50,
            score_audit=1.0,
            score_online=1.0,
            score_suspension=1.0,
        ),
        ReputationCreate(
            source="node-b",
            satellite_id="sat-2",
            timestamp=timestamp,
            audits_total=75,
            audits_success=70,
            score_audit=0.933,
            score_online=0.95,
            score_suspension=0.98,
        ),
    ]

    await database.init_database()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with database.SessionFactory() as session:
            await session.execute(delete(Reputation))
            await session.commit()

            repository = ReputationRepository(session)
            await repository.upsert_many(records)

        response = await client.post(
            "/api/reputations/panel",
            json={"nodes": []},
        )

    assert response.status_code == 200
    body = response.json()
    assert [item["node"] for item in body] == ["node-a", "node-b"]
    assert len(body[0]["satellites"]) == 1
    assert len(body[1]["satellites"]) == 1
